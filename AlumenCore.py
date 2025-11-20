# --- START OF FILE AlumenCore.py ---
import time
import google.generativeai as genai
import google.api_core.exceptions
import csv
import os
import re
import argparse
import sys
import json
import polib
import threading
import textwrap
import requests
from packaging import version
from threading import Lock, Event
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
from collections import deque

# Moduli Opzionali
try: import openpyxl
except ImportError: openpyxl = None

try: import telegram_bot
except ImportError: telegram_bot = None

# Modulo per Fuzzy Matching
try: from thefuzz import fuzz
except ImportError: fuzz = None


from rich.console import Console
from rich.table import Table

# ----- CONFIGURAZIONE VERSIONE 2.2.1 -----
CURRENT_SCRIPT_VERSION = "2.2.1"
GITHUB_REPO = "zSavT/Alumen"
DEFAULT_MODEL_NAME = "gemini-2.5-flash"
DEFAULT_CACHE_FILE = "alumen_cache.json"
LOG_FILE_NAME = "log.txt"
ESTIMATED_CHARS_PER_TOKEN = 3.5
FILE_CONTEXT_SAMPLE_SIZE = 15

# ----- GLOBALI -----
console = Console()
translation_cache = {}
available_api_keys = []
api_call_counts = {} 
blacklisted_keys = set()
current_api_key_index = 0
model = None
glossary_terms = {}
BLACKLIST_TERMS = set(["Dummy", "dummy", "null", "NULL", "None"]) 
total_files_translated = 0
total_entries_translated = 0
cache_hit_count = 0
rpm_limit = None
rpm_request_timestamps = []
rpm_lock = Lock()
last_cache_save_time = 0
gui_log_queue = None 
active_cache_file = DEFAULT_CACHE_FILE
context_window_deque = deque()
script_args_global = None 

# Eventi flusso
global_stop_event = None
global_pause_event = None
global_skip_event = None
global_skip_api_event = None
interactive_commands_thread = None

def log_msg(message, style=""):
    timestamp = datetime.now().strftime('%H:%M:%S')
    full_msg = f"[{timestamp}] {message}"
    console.print(message, style=style)
    
    if script_args_global and hasattr(script_args_global, 'enable_file_log') and script_args_global.enable_file_log:
        try:
            with open(LOG_FILE_NAME, 'a', encoding='utf-8') as f:
                f.write(full_msg + "\n")
        except: pass

    if gui_log_queue:
        gui_log_queue.put(full_msg)
    
    if telegram_bot and ("🛑" in message or "✅" in message):
        try: telegram_bot.send_telegram_notification(message)
        except: pass

def clean_api_key(key):
    if not key: return ""
    return key.strip().replace('\n', '').replace('\r', '').replace('\t', '')

def check_for_updates():
    try:
        url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/version.txt"
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            remote_ver = version.parse(r.text.strip())
            local_ver = version.parse(CURRENT_SCRIPT_VERSION)
            if remote_ver > local_ver:
                return str(remote_ver)
    except: pass
    return None

def fetch_available_models(api_key):
    try:
        clean_key = clean_api_key(api_key)
        if not clean_key: return ["Errore: Key vuota"]
        genai.configure(api_key=clean_key)
        models_list = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                name = m.name.replace('models/', '')
                lower = name.lower()
                if "preview" in lower or "exp" in lower: desc = "Sperimentale"
                elif "pro" in lower: desc = "Alta Precisione"
                elif "flash" in lower: desc = "Veloce & Economico"
                else: desc = "Standard"
                models_list.append(f"{name} | {desc}")
        models_list.sort(reverse=True)
        return models_list
    except Exception as e:
        return [f"Errore connessione: {e}"]

# --- CORE UTILS ---
def determine_if_translatable(text):
    if not isinstance(text, str): return False
    t = text.strip()
    if not t or t.isdigit() or re.match(r'^[\W_]+$', t): return False
    if re.match(r'^\{[\w\.]+\}$', t): return False
    return True

def should_translate_msgctxt(context_string):
    """Determina se un campo msgctxt di un file PO è testo discorsivo da tradurre."""
    if not context_string or not isinstance(context_string, str): return False
    # Escludi se sembra un ID (es. NPC_Guard_01)
    if '_' in context_string and ' ' not in context_string: return False
    # Escludi se contiene solo caratteri non alfanumerici o numeri
    if not any(c.isalpha() for c in context_string): return False
    # Escludi se è una singola parola in PascalCase o camelCase (probabile ID)
    if ' ' not in context_string and (context_string[0].isupper() or any(c.isupper() for c in context_string[1:])):
        if not context_string.islower() and not context_string.isupper(): return False
    return True

def normalize_text_for_fuzzy(text):
    """Normalizza il testo per matching fuzzy (strip, lower, no punteggiatura finale)."""
    if not text: return ""
    t = text.strip().lower()
    if t and t[-1] in ".,;!?'\"": t = t[:-1]
    return t

def _excel_col_to_index(col_str):
    """Converte una lettera di colonna Excel (es. 'A', 'B', 'AA') in un indice 0-based."""
    index = 0
    for char in col_str.upper():
        index = index * 26 + (ord(char) - ord('A') + 1)
    return index - 1

def _load_glossary_dict(filepath):
    g_dict = {}
    if filepath and os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for row in csv.reader(f):
                    if len(row) >= 2: g_dict[row[0].strip()] = row[1].strip()
        except: pass
    return g_dict

def _build_system_instruction_text(args, glossary_dict):
    blacklist_str = ", ".join(BLACKLIST_TERMS)
    parts = [
        f"Il tuo compito è tradurre testo ESCLUSIVAMENTE da {args.source_lang} a {args.target_lang}.",
        f"Contesto: Stai traducendo i file del videogioco '{args.game_name}'.",
        "Usa uno stile adatto al contesto, includendo slang o espressioni colloquiali se appropriato.",
        "",
        "--- ISTRUZIONI CRITICHE ---",
        f"1. Se il testo originale NON è in {args.source_lang}, DEVI restituire il testo originale IDENTICO.",
        "2. PRESERVA ESATTAMENTE tutti gli a capo, le tabulazioni e gli spazi iniziali/finali.",
        "3. PRESERVA i tag HTML, i placeholder (es. [p], {{player_name}}) e i codici speciali.",
        f"4. MANTIENI IDENTICI i seguenti termini: {blacklist_str}.",
        "5. In caso di dubbi sul genere, utilizza il maschile neutro.",
        "",
        "--- GLOSSARIO ---"
    ]
    if glossary_dict:
        parts.append(f"Usa TASSATIVAMENTE il seguente glossario:\n{json.dumps(glossary_dict, ensure_ascii=False, indent=2)}")
    else:
        parts.append("Nessun glossario specifico fornito.")

    if args.prompt_context: parts.append(f"\n--- CONTESTO EXTRA ---\n{args.prompt_context}")
    
    if args.style_guide and os.path.exists(args.style_guide):
        with open(args.style_guide, 'r', encoding='utf-8') as f:
            parts.append(f"\n--- GUIDA DI STILE ---\n{f.read()}")

    if args.custom_prompt: parts.append(f"\n--- ISTRUZIONI UTENTE ---\n{args.custom_prompt}")

    parts.append("\n--- FORMATO OUTPUT ---")
    parts.append("Rispondi ESCLUSIVAMENTE con un ARRAY JSON di stringhe tradotte. Stessa lunghezza dell'input.")
    return "\n".join(parts)

def generate_prompt_preview(args):
    real_glossary = _load_glossary_dict(args.glossary)
    system_instr = _build_system_instruction_text(args, real_glossary)
    mock_input = ["Start Game", "Options", "Variable {x} test."]
    user_msg = f"Traduci il seguente array JSON da {args.source_lang} a {args.target_lang}.\nINPUT:\n{json.dumps(mock_input, ensure_ascii=False, indent=2)}"
    est_tokens = int(len(system_instr + user_msg) / ESTIMATED_CHARS_PER_TOKEN)
    return f"=== SYSTEM ===\n{system_instr}\n\n=== USER ===\n{user_msg}\n\n📊 Token Stimati: ~{est_tokens}"

# --- SETUP ENGINE ---
def setup_engine(args):
    global available_api_keys, model, glossary_terms, translation_cache, rpm_limit, active_cache_file, context_window_deque, script_args_global, api_call_counts
    script_args_global = args 
    active_cache_file = args.cache_file if args.cache_file else DEFAULT_CACHE_FILE
    
    if args.full_context_sample and not args.enable_file_context:
        args.full_context_sample = False
    if args.context_window:
        context_window_deque = deque(maxlen=args.context_window)

    if args.persistent_cache and os.path.exists(active_cache_file):
        try:
            with open(active_cache_file, 'r', encoding='utf-8') as f:
                translation_cache = json.load(f)
            log_msg(f"💾 Cache caricata ({len(translation_cache)} voci)", style="dim")
        except: pass

    glossary_terms = _load_glossary_dict(args.glossary)
    if glossary_terms: log_msg(f"📚 Glossario caricato: {len(glossary_terms)} termini.", style="green")

    keys = []
    if args.api_file and os.path.exists(args.api_file):
        with open(args.api_file, "r", encoding="utf-8") as f: keys.extend([clean_api_key(l) for l in f if l.strip()])
    elif args.api:
        keys.extend([clean_api_key(k) for k in args.api.split(',') if k.strip()])
    elif os.path.exists("api_key.txt"):
        with open("api_key.txt", "r", encoding="utf-8") as f: keys.extend([clean_api_key(l) for l in f if l.strip()])
    
    available_api_keys = list(dict.fromkeys([k for k in keys if k]))
    if not available_api_keys:
        log_msg("🛑 ERRORE: Nessuna API Key valida trovata.", style="bold red")
        return False

    for k in available_api_keys: api_call_counts[k] = 0
    full_system_instruction = _build_system_instruction_text(args, glossary_terms)

    try:
        genai.configure(api_key=available_api_keys[0])
        clean_model_name = args.model_name.split(' |')[0].strip()
        model = genai.GenerativeModel(clean_model_name, system_instruction=full_system_instruction)
        log_msg(f"✅ Motore Alumen Inizializzato ({clean_model_name})", style="bold cyan")
    except Exception as e:
        log_msg(f"🛑 Errore Init AI: {e}", style="bold red")
        return False
    
    if args.rpm and args.rpm > 0: rpm_limit = args.rpm
    return True

# --- RUNTIME LOGIC ---
def check_and_save_cache(args, force=False):
    global last_cache_save_time
    if not args.persistent_cache: return
    now = time.time()
    if force or (now - last_cache_save_time > 300):
        try:
            with open(active_cache_file, 'w', encoding='utf-8') as f:
                json.dump(translation_cache, f, ensure_ascii=False, indent=4)
            last_cache_save_time = now
            if force: log_msg("💾 Cache salvata.", style="dim")
        except: pass

def rotate_key(args):
    global current_api_key_index, model
    if not available_api_keys: return
    blacklisted_keys.add(available_api_keys[current_api_key_index])
    current_api_key_index = (current_api_key_index + 1) % len(available_api_keys)
    new_key = available_api_keys[current_api_key_index]
    log_msg(f"🔄 Rotazione API Key -> ...{new_key[-4:]}", style="yellow")
    try:
        genai.configure(api_key=new_key)
        sys_instr = model._system_instruction if hasattr(model, '_system_instruction') else None
        clean_model_name = args.model_name.split(' |')[0].strip()
        model = genai.GenerativeModel(clean_model_name, system_instruction=sys_instr)
    except: pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_ai_raw(prompt, args):
    if global_pause_event and not global_pause_event.is_set():
        log_msg("⏳ Pausa. Attendo...", style="yellow")
        global_pause_event.wait()

    if global_skip_api_event and global_skip_api_event.is_set():
        log_msg("🔄 Rotazione API Key richiesta dall'utente...", style="yellow")
        rotate_key(args)
        global_skip_api_event.clear()

    if rpm_limit:
        while True:
            with rpm_lock:
                now = time.time()
                global rpm_request_timestamps
                rpm_request_timestamps = [t for t in rpm_request_timestamps if t > now - 60]
                if len(rpm_request_timestamps) < rpm_limit:
                    rpm_request_timestamps.append(now)
                    break
            time.sleep(1)
    
    time.sleep(0.5)
    current_key = available_api_keys[current_api_key_index]
    try:
        log_msg(f"[dim]➡️  INPUT AI:\n{prompt}[/dim]", style="dim")
        api_call_counts[current_key] += 1
        response_text = model.generate_content(prompt).text.strip()
        if args.reflect:
            log_msg("[dim]🤔 Riflessione AI in corso...[/dim]", style="dim")
            response_text = model.generate_content(f"Sei un revisore di traduzioni esperto. Rivedi, correggi e migliora la seguente traduzione, mantenendo il formato JSON array:\n{response_text}").text.strip()
        log_msg(f"[dim]⬅️  OUTPUT AI:\n{response_text}[/dim]", style="dim")
        return response_text
    except Exception as e:
        if args.server and ("429" in str(e) or "500" in str(e)):
             time.sleep(60); raise e
        if "header" in str(e).lower() or "metadata" in str(e).lower() or "400" in str(e):
            if len(available_api_keys) > 1: rotate_key(args); raise e 
            else: return "ERROR_API_KEY"
        if args.rotate_on_limit_or_error and not args.server:
            rotate_key(args); raise e
        raise e

def generate_file_context(sample_texts, file_name, args):
    try:
        prompt = f"Analizza queste frasi dal file '{file_name}' ({args.game_name}). Descrivi il contesto in una frase.\nCAMPIONE:\n" + "\n".join(sample_texts)
        ctx = call_ai_raw(prompt, args)
        log_msg(f"  📝 Contesto: {ctx}", style="italic cyan")
        return ctx
    except: return None

def apply_wrapping(text, args):
    if args.wrap_at and args.wrap_at > 0:
        newline = args.newline_char.replace('\\n', '\n').replace('\\r', '\r')
        return newline.join(textwrap.wrap(text, width=args.wrap_at, break_long_words=False, replace_whitespace=False))
    return text

def _translate_single_entry_legacy(entry, args, file_context=None):
    """
    Replica esatta della vecchia logica di traduzione singola da AlumenOld.py.
    Usa un prompt semplice e una gestione degli errori/cache dedicata.
    """
    global total_entries_translated, cache_hit_count
    text = entry['text']

    if text.strip() in BLACKLIST_TERMS:
        entry['callback'](text)
        return

    # Costruzione contesto dinamico (identico a AlumenOld)
    context_parts = []
    if file_context:
        context_parts.append(f"Contesto generale del file: '{file_context}'")
    if args.context_window and context_window_deque:
        context_lines = [f"Ecco le {len(context_window_deque)} traduzioni più recenti. Usale per coerenza:"]
        for src, trans in context_window_deque:
            context_lines.append(f'- "{src}" -> "{trans}"')
        context_parts.append("\n".join(context_lines))
    dynamic_context_str = "\n".join(context_parts)

    # Logica di cache a 2 passi (identica a AlumenOld)
    context_key = json.dumps((text, args.source_lang, args.target_lang, dynamic_context_str), ensure_ascii=False)
    if context_key in translation_cache:
        cached_translation = translation_cache[context_key]
        entry['callback'](apply_wrapping(cached_translation, args))
        total_entries_translated += 1
        cache_hit_count += 1
        return

    if dynamic_context_str:
        generic_key = json.dumps((text, args.source_lang, args.target_lang, ""), ensure_ascii=False)
        if generic_key in translation_cache:
            cached_translation = translation_cache[generic_key]
            translation_cache[context_key] = cached_translation # Promozione cache
            entry['callback'](apply_wrapping(cached_translation, args))
            total_entries_translated += 1
            cache_hit_count += 1
            return

    # Costruzione del prompt (identico a AlumenOld)
    blacklist_str_prompt = ", ".join(BLACKLIST_TERMS)
    prompt_lines = [
        f"Il tuo compito è tradurre testo ESCLUSIVAMENTE da {args.source_lang} a {args.target_lang}.",
        f"ISTRUZIONE CRITICA: Se il 'Testo originale' fornito di seguito NON è in {args.source_lang}, DEVI restituire il testo originale identico.",
        f"Solo se il testo è in {args.source_lang}, traducilo tenendo conto del contesto del gioco '{args.game_name}'.",
        "ISTRUZIONE CRITICA 2: Preserva sempre esattamente tutti gli a capo originali.",
        "Preserva eventuali tag HTML, placeholder (es. {{player_name}}), o codici speciali.",
        f"Assicurati di mantenere identici i seguenti termini: {blacklist_str_prompt}.",
        "In caso di dubbi sul genere, utilizza il maschile neutro."
    ]
    prompt_base = " ".join(prompt_lines)
    if args.prompt_context: prompt_base += f"\nIstruzione aggiuntiva: {args.prompt_context}."
    if dynamic_context_str: prompt_base += f"\n{dynamic_context_str}"
    prompt_base += "\nRispondi solo con la traduzione diretta."
    prompt_text = f"{prompt_base}\nTesto originale:\n{text}\n\nTraduzione in {args.target_lang}:"

    # Ciclo di chiamata API (identico a AlumenOld, ma con nuove funzioni)
    try:
        translated_text = call_ai_raw(prompt_text, args)
        if translated_text == "ERROR_API_KEY":
            if global_stop_event: global_stop_event.set()
            return

        final_text = apply_wrapping(translated_text, args)
        entry['callback'](final_text)
        total_entries_translated += 1
        translation_cache[context_key] = translated_text
        if args.context_window: context_window_deque.append((text, translated_text))
        check_and_save_cache(args)
    except Exception as e:
        log_msg(f"    ❌ Errore riga (legacy mode): {e}", style="red")

def _translate_single_entry(entry, args, file_context=None):
    """
    Logica per tradurre una singola entry, costruendo il contesto.
    Usato sia come fallback che per la modalità batch_size=0.
    """
    global total_entries_translated
    text = entry['text']
    
    # Costruzione contesto per la singola chiamata
    context_parts = []
    if file_context:
        context_parts.append(f"Contesto generale del file: '{file_context}'")
    if args.context_window and context_window_deque:
        context_lines = [f"Ecco le {len(context_window_deque)} traduzioni più recenti. Usale per coerenza:"]
        for src, trans in context_window_deque:
            context_lines.append(f'- "{src}" -> "{trans}"')
        context_parts.append("\n".join(context_lines))
    ctx_str = "\n".join(context_parts)
    
    prompt = f"{ctx_str}\nTraduci da {args.source_lang} a {args.target_lang}: {text}"
    translated_text = call_ai_raw(prompt, args)
    
    entry['callback'](apply_wrapping(translated_text, args))
    total_entries_translated += 1
    if args.context_window: context_window_deque.append((text, translated_text))
    exact_ck = json.dumps((text, args.source_lang, args.target_lang), ensure_ascii=False)
    translation_cache[exact_ck] = translated_text

def translate_batch(entries, args, stop_event, file_context=None):
    global total_entries_translated, context_window_deque
    batches = []
    current_batch = []
    current_tokens = 0

    # Pulisce la deque per ogni nuovo file
    if args.context_window: context_window_deque.clear()

    # --- LOGICA PER BATCH_SIZE = 0 ---
    if args.batch_size == 0:
        log_msg("ℹ️ Batch size è 0. Uso la logica di traduzione singola (una chiamata API per riga).", style="yellow")
        
        untranslated_entries = []
        for entry in entries:
            # La logica di cache viene gestita prima di chiamare questa funzione
            untranslated_entries.append(entry)

        for i, entry in enumerate(untranslated_entries):
            if stop_event.is_set(): return
            log_msg(f"    ☁️  Riga {i+1}/{len(untranslated_entries)}...", style="dim")
            # Chiama la nuova funzione legacy
            _translate_single_entry_legacy(entry, args, file_context)
        return
    
    for entry in entries:
        text = entry['text']
        
        cached_translation = None
        exact_cache_key = json.dumps((text, args.source_lang, args.target_lang), ensure_ascii=False)
        
        # 1. Controllo cache esatta
        if exact_cache_key in translation_cache:
            cached_translation = translation_cache[exact_cache_key]
        
        # 2. Controllo cache fuzzy (se abilitato e libreria presente)
        elif args.fuzzy_match and fuzz:
            lang_tuple_part = f', "{args.source_lang}", "{args.target_lang}"]'
            for key, value in translation_cache.items():
                if key.endswith(lang_tuple_part):
                    try:
                        cached_text = json.loads(key)[0]
                        similarity = fuzz.ratio(text, cached_text)
                        if similarity >= args.fuzzy_threshold:
                            cached_translation = value
                            log_msg(f"    [dim]Fuzzy match ({similarity}%): '{text[:30]}...' -> '{cached_text[:30]}...'[/]", style="dim")
                            break
                    except: continue
        
        if cached_translation is not None:
            final_txt = apply_wrapping(cached_translation, args)
            entry['callback'](final_txt)
            total_entries_translated += 1
            continue

        toks = len(text) // ESTIMATED_CHARS_PER_TOKEN
        if (len(current_batch) >= args.batch_size) or (current_tokens + toks > 3000):
            batches.append(current_batch); current_batch = []; current_tokens = 0
        current_batch.append(entry); current_tokens += toks
    if current_batch: batches.append(current_batch)

    for i, batch in enumerate(batches):
        if stop_event.is_set(): return
        if global_skip_event and global_skip_event.is_set(): return
        
        texts = [entry['text'] for entry in batch]
        log_msg(f"    ☁️  Batch {i+1}/{len(batches)} ({len(texts)} righe)...", style="dim")
        
        # --- COSTRUZIONE CONTESTO DINAMICO (Logica migrata da AlumenOld) ---
        context_parts = []
        if file_context:
            context_parts.append(f"Contesto generale del file: '{file_context}'")
        
        if args.context_window and context_window_deque:
            context_lines = [f"Ecco le {len(context_window_deque)} traduzioni più recenti. Usale per coerenza:"]
            for src, trans in context_window_deque:
                context_lines.append(f'- "{src}" -> "{trans}"')
            context_parts.append("\n".join(context_lines))
        ctx_str = "\n".join(context_parts)
        
        prompt = f"{ctx_str}TRADUZIONE JSON ARRAY.\nDa: {args.source_lang} | A: {args.target_lang}\nINPUT:\n{json.dumps(texts, ensure_ascii=False)}"
        
        try:
            resp = call_ai_raw(prompt, args)
            if resp == "ERROR_API_KEY": stop_event.set(); return
            if args.reflect:
                resp = call_ai_raw(f"Sei un revisore. Correggi la traduzione seguente:\n{resp}", args)
            clean = re.sub(r'^```json\s*|\s*```$', '', resp, flags=re.MULTILINE)
            trads = json.loads(clean)
            if len(trads) != len(texts): raise ValueError("Length mismatch")
            
            for idx, t in enumerate(trads):
                orig = texts[idx]
                if args.context_window: context_window_deque.append((orig, t))
                exact_ck = json.dumps((orig, args.source_lang, args.target_lang), ensure_ascii=False)
                translation_cache[exact_ck] = t
                batch[idx]['callback'](apply_wrapping(t, args))
                total_entries_translated += 1
            check_and_save_cache(args)
        except Exception as e:
            log_msg(f"⚠️ Batch fallito. Fallback a traduzione singola per questo batch.", style="yellow")
            for entry in batch:
                try: _translate_single_entry(entry, args, file_context)
                except Exception as ex: log_msg(f"    ❌ Errore riga (fallback): {ex}", style="red")

def do_dry_run(files, args):
    log_msg("🔎 DRY RUN...", style="bold yellow")
    total_chars = 0
    for f in files:
        try:
            with open(f, 'r', encoding=args.encoding, errors='ignore') as fp: total_chars += len(fp.read())
        except: pass
    toks = int(total_chars / ESTIMATED_CHARS_PER_TOKEN)
    cost = (toks / 1_000_000) * 0.35 
    log_msg(f"📊 File: {len(files)} | Caratteri: {total_chars:,} | Token: {toks:,} | Costo: ~${cost:.4f}")

# --- HANDLERS ---
def process_csv(fpath, outpath, args, stop_event):
    try:
        with open(fpath, 'r', encoding=args.encoding, newline='') as f:
            rows = list(csv.reader(f, delimiter=args.delimiter))
    except Exception as e:
        log_msg(f"❌ Errore lettura CSV {fpath}: {e}", style="red")
        return

    entries = []
    output_rows = [r[:] for r in rows]
    header = output_rows[0] if output_rows else None
    data_rows = output_rows[1:] if header else output_rows

    # Logica di Resume (allineata a AlumenOld)
    if args.resume and os.path.exists(outpath):
        try:
            with open(outpath, 'r', encoding=args.encoding, newline='') as f_resume:
                resumed_rows = list(csv.reader(f_resume, delimiter=args.delimiter))
                if len(resumed_rows) == len(output_rows):
                    output_rows = resumed_rows
                    data_rows = output_rows[1:] if header else output_rows
                    log_msg(f"  ↳ Resume: Caricate {len(output_rows)} righe da file esistente.", style="cyan")
        except Exception as e:
            log_msg(f"  ⚠️ Errore lettura file CSV per resume: {e}", style="yellow")

    # Costruisci la lista di entry da tradurre
    rows_to_translate_indices = []
    for i, row in enumerate(data_rows):
        # Controllo max_cols (da AlumenOld)
        if args.max_cols and len(row) > args.max_cols:
            continue

        # Logica di resume granulare (da AlumenOld)
        is_already_translated = args.resume and len(row) > args.output_col and row[args.output_col].strip() and \
                                (args.output_col != args.translate_col or row[args.output_col] != rows[i+1 if header else i][args.translate_col])

        needs_translation = len(row) > args.translate_col and determine_if_translatable(row[args.translate_col])

        if needs_translation and not is_already_translated:
            rows_to_translate_indices.append(i)

    if args.max_entries and len(rows_to_translate_indices) > args.max_entries:
        log_msg(f"⏭️ SKIP: File ha troppe entry da tradurre ({len(rows_to_translate_indices)} > {args.max_entries})", style="yellow")
        return

    file_ctx = None
    if args.enable_file_context:
        # Campionamento migliorato (da AlumenOld)
        samples = [data_rows[i][args.translate_col] for i in rows_to_translate_indices[:FILE_CONTEXT_SAMPLE_SIZE]]
        if samples: file_ctx = generate_file_context(samples, os.path.basename(fpath), args)

    for i in rows_to_translate_indices:
        row = data_rows[i]
        txt = row[args.translate_col]
        def cb(t, r=row, c=args.output_col):
            while len(r) <= c: r.append('')
            r[c] = t
        entries.append({'text': txt, 'callback': cb})

    translate_batch(entries, args, stop_event, file_ctx)
    
    if args.translation_only_output:
        translated_texts = [row[args.output_col] for i, row in enumerate(data_rows) if i in rows_to_translate_indices and len(row) > args.output_col]
        with open(outpath + ".txt", 'w', encoding=args.encoding) as f: f.write("\n".join(translated_texts))
    else:
        with open(outpath, 'w', encoding=args.encoding, newline='') as f: csv.writer(f, delimiter=args.delimiter).writerows(output_rows)

def process_json(fpath, outpath, args, stop_event):
    if args.resume and os.path.exists(outpath):
        log_msg(f"⏭️ Resume: File JSON esistente. Salto.", style="yellow")
        return
    with open(fpath, 'r', encoding=args.encoding) as f: data = json.load(f)
    entries = []
    keys = set(args.json_keys.split(',')) if args.json_keys else set()
    def traverse(obj, path=""):
        if global_stop_event and global_stop_event.is_set(): return
        if len(entries) > (args.max_entries or float('inf')): return

        if isinstance(obj, dict):
            for k, v in obj.items():
                curr = f"{path}.{k}" if path else k
                match = (curr in keys) if args.match_full_json_path else (k in keys)
                if match and isinstance(v, str) and determine_if_translatable(v):
                     entries.append({'text': v, 'callback': lambda t, o=obj, key=k: o.__setitem__(key, t)})
                traverse(v, curr)
        elif isinstance(obj, list):
            for i, x in enumerate(obj): traverse(x, f"{path}[{i}]")
    traverse(data)
    if args.max_entries and len(entries) > args.max_entries:
        log_msg(f"⏭️ SKIP: File '{os.path.basename(fpath)}' ha troppe entry ({len(entries)} > {args.max_entries})", style="yellow")
        return

    file_ctx = None
    if args.enable_file_context:
        samples = [e['text'] for e in entries[:FILE_CONTEXT_SAMPLE_SIZE]]
        file_ctx = generate_file_context(samples, os.path.basename(fpath), args)
    translate_batch(entries, args, stop_event, file_ctx)
    with open(outpath, 'w', encoding=args.encoding) as f: json.dump(data, f, indent=4, ensure_ascii=False)

def process_po(fpath, outpath, args, stop_event):
    try:
        po = polib.pofile(fpath, encoding=args.encoding)
    except Exception as e:
        log_msg(f"❌ Errore lettura file PO {fpath}: {e}", style="red")
        return

    entries = []
    
    # Logica di Resume granulare (allineata a AlumenOld)
    entries_to_process = []
    if args.resume and os.path.exists(outpath):
        try:
            out_po = polib.pofile(outpath, encoding=args.encoding)
            existing_translations = {(e.msgid, e.msgctxt): e.msgstr for e in out_po if e.msgstr}
            log_msg(f"  ↳ Resume: Trovate {len(existing_translations)} traduzioni esistenti.", style="cyan")
            for entry in po:
                if (entry.msgid, entry.msgctxt) in existing_translations:
                    entry.msgstr = existing_translations[(entry.msgid, entry.msgctxt)]
                else:
                    entries_to_process.append(entry)
        except Exception as e:
            log_msg(f"  ⚠️  Errore lettura file PO per resume: {e}", style="yellow")
            entries_to_process = list(po)
    else:
        entries_to_process = list(po)

    for entry in entries_to_process:
        # Se il msgctxt è testo traducibile, lo aggiunge alla coda
        if should_translate_msgctxt(entry.msgctxt):
            entries.append({'text': entry.msgctxt, 'callback': lambda t, e=entry: setattr(e, 'msgctxt', t)})
        
        # Aggiunge il msgid se è traducibile
        if determine_if_translatable(entry.msgid):
            entries.append({'text': entry.msgid, 'callback': lambda t, e=entry: setattr(e, 'msgstr', t)})
        elif entry.msgid:
            # Se non è traducibile, copia l'originale per non lasciare il campo vuoto
            entry.msgstr = entry.msgid

    if args.max_entries and len(entries) > args.max_entries:
        log_msg(f"⏭️ SKIP: File '{os.path.basename(fpath)}' ha troppe entry ({len(entries)} > {args.max_entries})", style="yellow")
        return
    translate_batch(entries, args, stop_event)
    po.save(outpath)

def process_xlsx(fpath, outpath, args, stop_event):
    if not openpyxl: return
    if args.resume and os.path.exists(outpath): return
    wb = openpyxl.load_workbook(fpath)
    ws = wb.active
    entries = []
    src_col_idx = _excel_col_to_index(args.xlsx_source_col)
    tgt_col_idx = _excel_col_to_index(args.xlsx_target_col)
    for row in ws.iter_rows():
        if len(row) > src_col_idx:
            c = row[src_col_idx]
            if c.value and isinstance(c.value, str) and determine_if_translatable(c.value):
                tgt = ws.cell(row=c.row, column=tgt_col_idx + 1)
                entries.append({'text': c.value, 'callback': lambda t, cell=tgt: setattr(cell, 'value', t)})
    
    if args.max_entries and len(entries) > args.max_entries:
        log_msg(f"⏭️ SKIP: File '{os.path.basename(fpath)}' ha troppe entry ({len(entries)} > {args.max_entries})", style="yellow")
        return

    translate_batch(entries, args, stop_event)
    wb.save(outpath)

def process_srt(fpath, outpath, args, stop_event):
    if args.resume and os.path.exists(outpath): return
    with open(fpath, 'r', encoding=args.encoding) as f: content = f.read()
    pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\s*\n|\Z)', re.DOTALL)
    matches = list(pattern.finditer(content))
    entries = []
    blocks = []
    for m in matches:
        b = {'i': m.group(1), 't': m.group(2), 'txt': m.group(3)}
        blocks.append(b)
        if determine_if_translatable(b['txt']):
            entries.append({'text': b['txt'], 'callback': lambda t, blk=b: blk.update({'txt': t})})
    
    if args.max_entries and len(entries) > args.max_entries:
        log_msg(f"⏭️ SKIP: File '{os.path.basename(fpath)}' ha troppe entry ({len(entries)} > {args.max_entries})", style="yellow")
        return

    translate_batch(entries, args, stop_event)
    with open(outpath, 'w', encoding=args.encoding) as f:
        for b in blocks:
            f.write(f"{b['i']}\n{b['t']}\n{b['txt']}\n\n")

def process_srt(fpath, outpath, args, stop_event):
    if args.resume and os.path.exists(outpath): return
    with open(fpath, 'r', encoding=args.encoding) as f: content = f.read()
    pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\s*\n|\Z)', re.DOTALL)
    matches = list(pattern.finditer(content))
    entries = []
    blocks = []
    for m in matches:
        b = {'i': m.group(1), 't': m.group(2), 'txt': m.group(3)}
        blocks.append(b)
        if determine_if_translatable(b['txt']):
            entries.append({'text': b['txt'], 'callback': lambda t, blk=b: blk.update({'txt': t})})
    
    if args.max_entries and len(entries) > args.max_entries:
        log_msg(f"⏭️ SKIP: File '{os.path.basename(fpath)}' ha troppe entry ({len(entries)} > {args.max_entries})", style="yellow")
        return

    translate_batch(entries, args, stop_event)
    with open(outpath, 'w', encoding=args.encoding) as f:
        for b in blocks:
            f.write(f"{b['i']}\n{b['t']}\n{b['txt']}\n\n")

# --- TOOLS UTILITY FUNCTIONS (NEW - Integrated) ---
def run_cache_extractor(source_dir, target_dir, file_type, src_col, tgt_col, encoding, json_keys=None):
    log_msg(f"🛠️ Avvio Estrazione Cache da {source_dir}...", style="bold cyan")
    extracted = {}
    count = 0
    
    for root, _, files in os.walk(source_dir):
        rel = os.path.relpath(root, source_dir)
        tgt_root = os.path.join(target_dir, rel)
        
        for fname in files:
            if not fname.endswith(f".{file_type}"): continue
            src_path = os.path.join(root, fname)
            tgt_path = os.path.join(tgt_root, fname)
            
            if not os.path.exists(tgt_path): continue
            log_msg(f"  Analizzo: {fname}...")

            added_count = 0
            try:
                if file_type == 'csv':
                    with open(src_path, 'r', encoding=encoding) as f1, open(tgt_path, 'r', encoding=encoding) as f2:
                        r1 = list(csv.reader(f1, delimiter=',')) # Delimiter hardcoded per semplicità
                        r2 = list(csv.reader(f2))
                        for i in range(min(len(r1), len(r2))):
                            s = r1[i][src_col] if len(r1[i]) > src_col else ""
                            t = r2[i][tgt_col] if len(r2[i]) > tgt_col else ""
                            if s and t and determine_if_translatable(s):
                                # Key format standard
                                key = json.dumps((s, "inglese", "italiano"), ensure_ascii=False) 
                                extracted[key] = t
                                added_count += 1
                
                elif file_type == 'json' and json_keys:
                    with open(src_path, 'r', encoding=encoding) as f1, open(tgt_path, 'r', encoding=encoding) as f2:
                        s_data, t_data = json.load(f1), json.load(f2)
                    
                    keys_to_find = set(k.strip() for k in json_keys.split(','))
                    
                    def traverse(s_obj, t_obj):
                        nonlocal added_count
                        if isinstance(s_obj, dict) and isinstance(t_obj, dict):
                            for k, v in s_obj.items():
                                if k in keys_to_find and k in t_obj and determine_if_translatable(v) and t_obj[k]:
                                    key = json.dumps((v, "inglese", "italiano"), ensure_ascii=False)
                                    extracted[key] = t_obj[k]
                                    added_count += 1
                                if k in t_obj: traverse(v, t_obj.get(k))
                        elif isinstance(s_obj, list) and isinstance(t_obj, list):
                            for i in range(min(len(s_obj), len(t_obj))): traverse(s_obj[i], t_obj[i])
                    
                    traverse(s_data, t_data)

                elif file_type == 'po':
                    po = polib.pofile(tgt_path, encoding=encoding)
                    for entry in po:
                        if entry.msgid and entry.msgstr and determine_if_translatable(entry.msgid):
                            key = json.dumps((entry.msgid, "inglese", "italiano"), ensure_ascii=False)
                            extracted[key] = entry.msgstr
                            added_count += 1

            except Exception as e:
                log_msg(f"    ❌ Errore durante l'analisi di {fname}: {e}", style="red")
            
            if added_count > 0:
                log_msg(f"    -> {added_count} voci aggiunte.", style="green")
    
    if extracted:
        try:
            with open(DEFAULT_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(extracted, f, ensure_ascii=False, indent=4)
            log_msg(f"✅ Estrazione completata. {count} voci salvate in '{DEFAULT_CACHE_FILE}'.", style="bold green")
        except Exception as e:
            log_msg(f"❌ Errore salvataggio: {e}", style="bold red")
    else:
        log_msg("⚠️ Nessuna voce trovata.", style="yellow")

def run_term_scanner(input_dir, file_type, encoding):
    log_msg("🕵️ Avvio Scansione Termini...", style="bold yellow")
    text_blob = ""
    # Collect samples
    for root, _, files in os.walk(input_dir):
        for f in files:
            if f.endswith(f".{file_type}"):
                try:
                    with open(os.path.join(root, f), 'r', encoding=encoding) as fp:
                        text_blob += fp.read(5000) 
                except: pass
            if len(text_blob) > 50000: break
            
    if not text_blob: return "Nessun testo trovato."
    
    try:
        prompt = f"Estrai una lista di Nomi Propri, Luoghi e Oggetti Unici da questo testo. Restituisci JSON array.\nTESTO:\n{text_blob[:30000]}"
        if not available_api_keys: return "Errore: Manca API Key"
        
        genai.configure(api_key=available_api_keys[0]) 
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content(prompt).text
        clean = re.sub(r'^```json\s*|\s*```$', '', resp, flags=re.MULTILINE)
        return clean
    except Exception as e:
        return f"Errore: {e}"

# --- RUNNER ---
def run_core_process(args, log_queue=None, stop_event=None, pause_event=None, skip_event=None, skip_api_event=None):
    global gui_log_queue, total_files_translated, total_entries_translated, context_window_deque, global_stop_event, global_pause_event, global_skip_event, global_skip_api_event, interactive_commands_thread
    gui_log_queue = log_queue
    global_stop_event, global_pause_event, global_skip_event, global_skip_api_event = stop_event, pause_event, skip_event, skip_api_event
    
    if stop_event is None: stop_event = Event()
    if pause_event is None: pause_event = Event(); pause_event.set()
    
    tg_app = None
    if args.telegram and telegram_bot: tg_app = telegram_bot.start_bot()

    # Avvio del thread per i comandi interattivi se richiesto
    if args.interactive:
        interactive_commands_thread = threading.Thread(target=command_input_thread, daemon=True)
        interactive_commands_thread.start()

    if args.dry_run:
        files = [os.path.join(r, f) for r, _, fs in os.walk(args.input) for f in fs if f.lower().endswith(f".{args.file_type}")]
        do_dry_run(files, args)
        if tg_app: telegram_bot.stop_bot()
        return

    if not setup_engine(args): 
        if tg_app: telegram_bot.stop_bot()
        return

    files = [os.path.join(r, f) for r, _, fs in os.walk(args.input) for f in fs if f.lower().endswith(f".{args.file_type}")]
    base_out = args.output_dir if args.output_dir else "output"
    if not os.path.exists(base_out): os.makedirs(base_out)
    
    log_msg(f"🚀 Avvio Alumen (Mode: {args.model_name})", style="bold green")
    
    for i, fpath in enumerate(files):
        if stop_event.is_set(): log_msg("🛑 Stop.", style="red"); break
        if global_skip_event: global_skip_event.clear()
        
        fname = os.path.basename(fpath)
        log_msg(f"📄 [{i+1}/{len(files)}] {fname}")
        rel = os.path.relpath(fpath, args.input)
        out = os.path.join(base_out, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        
        try:
            if args.file_type == 'csv': process_csv(fpath, out, args, stop_event)
            elif args.file_type == 'json': process_json(fpath, out, args, stop_event)
            elif args.file_type == 'po': process_po(fpath, out, args, stop_event)
            elif args.file_type == 'xlsx': process_xlsx(fpath, out, args, stop_event)
            elif args.file_type == 'srt': process_srt(fpath, out, args, stop_event)
            
            if not (global_skip_event and global_skip_event.is_set()):
                total_files_translated += 1
            check_and_save_cache(args, force=True)
        except Exception as e:
            log_msg(f"❌ Errore {fname}: {e}", style="bold red")

    log_msg(f"✅ Finito. {total_files_translated} file tradotti.", style="bold green")
    if tg_app: telegram_bot.stop_bot()

def _get_full_stats_text(is_telegram=False, for_gui=False):
    """Genera il testo o la tabella per le statistiche complete."""
    end_time = time.time()
    global cache_hit_count # Dichiarazione mancante
    total_time = end_time - (script_args_global.start_time if hasattr(script_args_global, 'start_time') else end_time)
    total_api_calls = sum(api_call_counts.values())
    avg_time_per_file = (total_time / total_files_translated) if total_files_translated > 0 else 0

    if is_telegram:
        lines = ["*📊 STATISTICHE COMPLETE*"]
        lines.append(f"⏳ *Tempo trascorso:* `{datetime.fromtimestamp(total_time).strftime('%H:%M:%S')}`")
        lines.append(f"✅ *File tradotti:* `{total_files_translated}`")
        lines.append(f"✅ *Voci tradotte:* `{total_entries_translated}`")
        lines.append(f"💾 *Cache Hits:* `{cache_hit_count}`")
        lines.append(f"📞 *Chiamate API totali:* `{total_api_calls}`")
        lines.append("\n*🔑 Stato Chiavi API:*")
        for i, key in enumerate(available_api_keys):
            status = "✅ ATTIVA" if i == current_api_key_index else ("❌ BLACKLIST" if key in blacklisted_keys else " standby")
            lines.append(f"`...{key[-4:]}`: `{api_call_counts.get(key, 0)}` chiamate ({status})")
        return "\n".join(lines)
    else:
        from io import StringIO
        
        main_table = Table(title="📊 STATISTICHE DI ESECUZIONE", show_header=False, header_style="bold magenta")
        main_table.add_column("Parametro", style="cyan")
        main_table.add_column("Valore", style="bold")
        main_table.add_row("⏳ Tempo trascorso", datetime.fromtimestamp(total_time).strftime('%H:%M:%S'))
        main_table.add_row("✅ File tradotti", str(total_files_translated))
        main_table.add_row("✅ Voci tradotte", str(total_entries_translated))
        if total_files_translated > 0: main_table.add_row("⏱️ Tempo medio per file", datetime.fromtimestamp(avg_time_per_file).strftime('%H:%M:%S'))
        main_table.add_section()
        main_table.add_row("💾 Traduzioni da cache", str(cache_hit_count))
        main_table.add_row("📞 Chiamate API totali", str(total_api_calls))

        keys_table = Table(title="🔑 Stato Chiavi API", show_header=True, header_style="bold magenta")
        keys_table.add_column("Chiave", style="green"); keys_table.add_column("Stato", justify="right"); keys_table.add_column("Chiamate", justify="right")
        for key in available_api_keys:
            status_text = "✅ ATTIVA" if key == available_api_keys[current_api_key_index] else ("❌ BLACKLIST" if key in blacklisted_keys else "standby")
            keys_table.add_row(f"...{key[-4:]}", status_text, str(api_call_counts.get(key, 0)))

        capture = StringIO()
        temp_console = Console(file=capture, force_terminal=not for_gui)
        temp_console.print(main_table)
        temp_console.print(keys_table)
        return capture.getvalue()

# --- Interactive Mode Logic (from AlumenOld) ---
def process_command(command_line):
    cmd_parts = command_line.split(maxsplit=1)
    cmd = cmd_parts[0].lower() if cmd_parts else ""
    
    if cmd == "stop":
        if global_stop_event: global_stop_event.set()
        log_msg("🛑 Stop richiesto. Uscita in corso...")
    elif cmd == "pause":
        if global_pause_event: global_pause_event.clear()
        log_msg("⏸️ Pausa.")
    elif cmd == "resume":
        if global_pause_event: global_pause_event.set()
        log_msg("▶️ Ripresa.")
    elif cmd == "skip":
        sub_cmd = cmd_parts[1].lower() if len(cmd_parts) > 1 else ""
        if sub_cmd == "file":
            if global_skip_event: global_skip_event.set()
            log_msg("⏭️ Salto del file corrente richiesto...")
        elif sub_cmd == "api":
            log_msg("🔄 Rotazione API Key richiesta dall'utente...")
            rotate_key(script_args_global)
        else:
            log_msg("Comando non riconosciuto: usa 'skip file' o 'skip api'")
    elif cmd == "stats":
        # Mostra statistiche complete
        end_time = time.time()
        total_time = end_time - script_args_global.start_time
        console.print(_get_full_stats_text(is_telegram=False)) # Placeholder, la logica completa è complessa
        log_msg(f"File: {total_files_translated}, Voci: {total_entries_translated}, Cache: {len(translation_cache)}, Chiamate API: {sum(api_call_counts.values())}")
    else:
        log_msg(f"Comando non riconosciuto: {cmd}")

def command_input_thread():
    log_msg("ℹ️ Modalità interattiva. Comandi: stop, pause, resume, skip, stats", style="yellow")
    while not (global_stop_event and global_stop_event.is_set()):
        process_command(input())

def get_cli_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="input")
    p.add_argument("--output-dir", default="output")
    p.add_argument("--api")
    p.add_argument("--api-file")
    p.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    p.add_argument("--file-type", default="csv")
    p.add_argument("--encoding", default="utf-8")
    p.add_argument("--delimiter", default=",")
    p.add_argument("--translate-col", type=int, default=3)
    p.add_argument("--output-col", type=int, default=3)
    p.add_argument("--max-cols", type=int)
    p.add_argument("--json-keys")
    p.add_argument("--xlsx-source-col", default="A")
    p.add_argument("--xlsx-target-col", default="B")
    p.add_argument("--match-full-json-path", action="store_true")
    p.add_argument("--game-name", default="un videogioco generico")
    p.add_argument("--source-lang", default="inglese")
    p.add_argument("--target-lang", default="italiano")
    p.add_argument("--prompt-context")
    p.add_argument("--custom-prompt")
    p.add_argument("--translation-only-output", action="store_true")
    p.add_argument("--style-guide")
    p.add_argument("--rpm", type=int)
    p.add_argument("--enable-file-context", action="store_true")
    p.add_argument("--full-context-sample", action="store_true")
    p.add_argument("--context-window", type=int, default=0)
    p.add_argument("--wrap-at", type=int)
    p.add_argument("--newline-char", default="\\n")
    p.add_argument("--enable-file-log", action="store_true")
    p.add_argument("--telegram", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--rotate-on-limit-or-error", action="store_true")
    p.add_argument("--persistent-cache", action="store_true")
    p.add_argument("--cache-file")
    p.add_argument("--glossary")
    p.add_argument("--server", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-entries", type=int)
    p.add_argument("--reflect", action="store_true")
    p.add_argument("--interactive", action="store_true") 
    p.add_argument("--fuzzy-match", action="store_true")
    p.add_argument("--fuzzy-threshold", type=int, default=90)
    return p.parse_args()

if __name__ == "__main__":
    args = get_cli_args()
    args.start_time = time.time() # Aggiungi start_time per il calcolo
    run_core_process(args)