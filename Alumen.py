import time
import google.generativeai as genai
import csv
import os
import re
import argparse
import itertools
import sys
import threading
from threading import Thread, Event, Lock
import textwrap
from datetime import datetime
from argparse_color_formatter import ColorHelpFormatter
import json 

# ----- Costanti Globali -----
MAX_RETRIES_PER_API_CALL = 3            # Tentativi per ogni richiesta con API
MAX_MAJOR_FAILURES_THRESHOLD = 6        # Numero massimo di fallimenti prima del passaggio ad nuova API
DEFAULT_MODEL_NAME = "gemini-2.5-flash" # Modello Gemini predefinito
LOG_FILE_NAME = "log.txt"               # Nome file log
DEFAULT_API_ERROR_RETRY_SECONDS = 10    # Numero di secondi di attesa tra una chiamata all'API se non impostato RPM o l'errore dell'api non suggerisce un delay
BASE_API_CALL_INTERVAL_SECONDS = 0.2    # Pausa minima tra chiamate API, l'RPM gestisce il resto

# ----- Variabili Globali -----
available_api_keys = []      # Lista API CaricateI
current_api_key_index = 0    # Indice api attiva
major_failure_count = 0      # Contatore per fallimenti API con la stessa chiave
model = None                 # Modello Gemini
script_args = None           # Oggetto per gli argomenti passati allo script
log_file_path = None         # Path file log

# Gestione RPM (Richieste Per Minuto)
rpm_limit = None             # Limite massimo RPM (Valorizzato solo nell'arg)
rpm_request_timestamps = []  # Richieste effettuate
rpm_lock = Lock()            # Per la gestione del RPM quando si utilizza la modalità interattiva

# Gestione Comandi Interattivi
user_command_skip_api = False   # Comando per saltare la api attualmente in utilizzo
user_command_skip_file = False  # Comando per saltare il file attualmente aperto
script_is_paused = Event()      # Segnala se lo script è in pausa
command_lock = Lock()           # Lock per l'accesso ai comandi condivisi

ALUMEN_ASCII_ART = """

 ░▒▓██████▓▒░░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓██████████████▓▒░░▒▓████████▓▒░▒▓███████▓▒░
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓████████▓▒░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░░▒▓█▓▒░▒▓████████▓▒░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░
   Traduttore Automatico Multilingua potenziato da Gemini
"""

def get_script_args_updated():
    global script_args
    parser = argparse.ArgumentParser(
        description="Alumen - Script per tradurre file CSV o JSON utilizzando Google Gemini.",
        formatter_class=ColorHelpFormatter
    )

    api_group = parser.add_argument_group('\033[96mConfigurazione API e Modello\033[0m') 
    file_format_group = parser.add_argument_group('\033[96mConfigurazione File e Formato\033[0m')
    csv_options_group = parser.add_argument_group('\033[96mOpzioni Specifiche per CSV\033[0m')
    json_options_group = parser.add_argument_group('\033[96mOpzioni Specifiche per JSON\033[0m')
    translation_group = parser.add_argument_group('\033[96mParametri di Traduzione\033[0m')
    wrapping_group = parser.add_argument_group('\033[96mOpzioni A Capo Automatico (Word Wrapping)\033[0m')
    utility_group = parser.add_argument_group('\033[96mUtilità e Modalità Interattiva\033[0m')

    # Configurazione API
    api_group.add_argument("--api", type=str, help="\033[97mSpecifica una o più chiavi API Google Gemini, separate da virgola.\033[0m")
    api_group.add_argument("--model-name", type=str, default=DEFAULT_MODEL_NAME, help=f"\033[97mNome del modello Gemini da utilizzare. Default: '{DEFAULT_MODEL_NAME}'\033[0m")

    # Configurazione File
    file_format_group.add_argument("--input", type=str, default="input", help="\033[97mPercorso della cartella base contenente i file da tradurre. Default: 'input'\033[0m")
    file_format_group.add_argument("--file-type", type=str, default="csv", choices=['csv', 'json'], help="\033[97mTipo di file da elaborare: 'csv' o 'json'. Default: 'csv'\033[0m")
    file_format_group.add_argument("--encoding", type=str, default="utf-8", help="\033[97mCodifica caratteri dei file. Default: 'utf-8'\033[0m")

    # Opzioni CSV
    csv_options_group.add_argument("--delimiter", type=str, default=",", help="\033[97m[Solo CSV] Carattere delimitatore. Default: ','\033[0m")
    csv_options_group.add_argument("--translate-col", type=int, default=3, help="\033[97m[Solo CSV] Indice (0-based) della colonna da tradurre. Default: 3\033[0m")
    csv_options_group.add_argument("--output-col", type=int, default=3, help="\033[97m[Solo CSV] Indice (0-based) della colonna per il testo tradotto. Default: 3\033[0m")
    csv_options_group.add_argument("--max-cols", type=int, default=None, help="\033[97m[Solo CSV] Numero massimo di colonne attese per riga. Default: Nessun controllo.\033[0m")
    
    # Opzioni JSON
    json_options_group.add_argument("--json-keys", type=str, default=None, help="\033[97m[Solo JSON, Obbligatorio] Elenco di chiavi (separate da virgola) da tradurre. Supporta notazione a punto per chiavi annidate (es. 'key1,path.to.key2').\033[0m")

    # Parametri Traduzione
    translation_group.add_argument("--game-name", type=str, default="un videogioco generico", help="\033[97mNome del gioco per contestualizzare la traduzione.\033[0m")
    translation_group.add_argument("--source-lang", type=str, default="inglese", help="\033[97mLingua originale del testo.\033[0m")
    translation_group.add_argument("--target-lang", type=str, default="italiano", help="\033[97mLingua di destinazione.\033[0m")
    translation_group.add_argument("--prompt-context", type=str, default=None, help="\033[97mAggiunge un'informazione contestuale extra al prompt.\033[0m")
    translation_group.add_argument("--custom-prompt", type=str, default=None, help="\033[97mUsa un prompt personalizzato. OBBLIGATORIO: includere '{text_to_translate}'.\033[0m")
    translation_group.add_argument("--translation-only-output", action="store_true", help="\033[97mL'output conterrà solo i testi tradotti, uno per riga.\033[0m")
    translation_group.add_argument("--rpm", type=int, default=None, help="\033[97mNumero massimo di richieste API a Gemini per minuto.\033[0m")

    # A Capo Automatico
    wrapping_group.add_argument("--wrap-at", type=int, default=None, help="\033[97mLunghezza massima della riga per a capo automatico.\033[0m")
    wrapping_group.add_argument("--newline-char", type=str, default='\\n', help="\033[97mCarattere da usare per l'a capo automatico.\033[0m")

    # Utilità
    utility_group.add_argument("--oneThread", action="store_true", help="\033[97mDisabilita l'animazione di caricamento.\033[0m")
    utility_group.add_argument("--enable-file-log", action="store_true", help=f"\033[97mAttiva la scrittura di un log ('{LOG_FILE_NAME}').\033[0m")
    utility_group.add_argument("--interactive", action="store_true", help="\033[97mAbilita comandi interattivi.\033[0m")
    utility_group.add_argument("--resume", action="store_true", help="\033[97mTenta di riprendere la traduzione da file parziali.\033[0m")
    utility_group.add_argument("--rotate-on-limit-or-error", action="store_true", help="\033[97mPassa alla API key successiva in caso di errore o limite RPM.\033[0m")

    parsed_args = parser.parse_args()
    if parsed_args.delimiter == '\\t':
        parsed_args.delimiter = '\t'
    if parsed_args.newline_char == '\\n':
        parsed_args.newline_char = '\n'
    elif parsed_args.newline_char == '\\r\\n':
        parsed_args.newline_char = '\r\n'
    script_args = parsed_args
    return parsed_args

def format_time_delta(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"

def count_lines_in_file(filepath, encoding='utf-8'):
    try:
        with open(filepath, 'r', encoding=encoding, newline='') as f:
            return sum(1 for _ in f)
    except FileNotFoundError: return 0
    except Exception as e:
        print(f"⚠️  Attenzione: Impossibile contare le righe nel file '{filepath}': {e}")
        if script_args and script_args.enable_file_log: write_to_log(f"AVVISO: Impossibile contare le righe nel file '{filepath}': {e}")
        return 0

def setup_log_file():
    global log_file_path, script_args
    if not script_args.enable_file_log: return
    try:
        try: script_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError: script_dir = os.getcwd()
        log_file_path = os.path.join(script_dir, LOG_FILE_NAME)
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(ALUMEN_ASCII_ART + "\n")
            f.write(f"--- Nuova Sessione di Log Avviata: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            config_to_log = {k: (v if k != 'api' or not v or len(v) < 15 else f"{v[:5]}...{v[-4:]}(nascosta)") for k, v in vars(script_args).items()}
            f.write(f"Configurazione Applicata: {config_to_log}\n")
            f.write("-" * 70 + "\n")
        print(f"Logging su file abilitato. Output in: '{log_file_path}'")
    except Exception as e:
        print(f"⚠️  Attenzione: Impossibile inizializzare il file di log '{LOG_FILE_NAME}': {e}")
        log_file_path = None

def write_to_log(message):
    global script_args, log_file_path
    if script_args and script_args.enable_file_log and log_file_path:
        try:
            with open(log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        except Exception: pass

def log_critical_error_and_exit(message):
    print(f"🛑 ERRORE CRITICO: {message}")
    write_to_log(f"ERRORE CRITICO: {message}")
    sys.exit(1)

def initialize_api_keys_and_model():
    global available_api_keys, current_api_key_index, model, rpm_limit
    print("\n--- Inizializzazione API e Modello ---")
    if script_args.api:
        keys_from_arg = [key.strip() for key in script_args.api.split(',') if key.strip()]
        if keys_from_arg:
            available_api_keys.extend(keys_from_arg)
            print(f"{len(keys_from_arg)} API key(s) fornite tramite argomento --api.")
    api_key_file_path = "api_key.txt"
    if os.path.exists(api_key_file_path):
        with open(api_key_file_path, "r") as f:
            keys_from_file = [line.strip() for line in f if line.strip()]
            if keys_from_file:
                available_api_keys.extend(keys_from_file)
                print(f"{len(keys_from_file)} API key(s) caricate da '{api_key_file_path}'.")
    seen = set()
    available_api_keys = [x for x in available_api_keys if not (x in seen or seen.add(x))]
    if not available_api_keys:
        log_critical_error_and_exit("Nessuna API key trovata. Specificare tramite --api o nel file 'api_key.txt'.")
    
    print(f"ℹ️  Totale API keys uniche disponibili: {len(available_api_keys)}.")
    current_api_key_index = 0
    try:
        current_key = available_api_keys[current_api_key_index]
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel(script_args.model_name)
        print(f"✅ Modello '{script_args.model_name}' inizializzato con API Key: ...{current_key[-4:]}")
    except Exception as e:
        log_critical_error_and_exit(f"Errore durante l'inizializzazione del modello '{script_args.model_name}': {e}")
    if script_args.rpm and script_args.rpm > 0:
        rpm_limit = script_args.rpm
        print(f"INFO: Limite RPM impostato a: {rpm_limit} richieste/minuto.")
    print("-" * 50)


def rotate_api_key(triggered_by_user=False, reason_override=None):
    global current_api_key_index, major_failure_count, model
    if len(available_api_keys) <= 1:
        print("⚠️  Solo una API key disponibile. Impossibile ruotare.")
        return False
    previous_key_index = current_api_key_index
    current_api_key_index = (current_api_key_index + 1) % len(available_api_keys)
    new_api_key = available_api_keys[current_api_key_index]
    trigger_reason = reason_override if reason_override else ("Comando utente." if triggered_by_user else f"Soglia fallimenti raggiunta.")
    print(f"INFO: Rotazione API key ({trigger_reason})...")
    try:
        genai.configure(api_key=new_api_key)
        model = genai.GenerativeModel(script_args.model_name)
        print(f"✅ API key ruotata e modello '{script_args.model_name}' riconfigurato.")
        major_failure_count = 0
        return True
    except Exception as e:
        print(f"❌ ERRORE: Configurazione nuova API Key fallita: {e}")
        current_api_key_index = previous_key_index
        try:
            genai.configure(api_key=available_api_keys[previous_key_index])
            model = genai.GenerativeModel(script_args.model_name)
            print("✅ API Key precedente ripristinata.")
        except Exception as e_revert:
             log_critical_error_and_exit(f"Errore nel ripristino della API Key precedente: {e_revert}.")
        return False

def animazione_caricamento(stop_event):
    for simbolo in itertools.cycle(['|', '/', '-', '\\']):
        if stop_event.is_set(): break
        sys.stdout.write(f"\rTraduzione in corso {simbolo} ")
        sys.stdout.flush()
        time.sleep(0.2)
    sys.stdout.write("\r" + " " * 40 + "\r")

def command_input_thread_func():
    global user_command_skip_api, user_command_skip_file, script_is_paused
    print("\n\n============================================")
    print("    Alumen - Console Interattiva")
    print("============================================")
    print("ℹ️  Digita 'help' per i comandi, 'exit' o 'quit' per chiudere.")
    while True:
        try:
            prompt_indicator = "(In Pausa) " if not script_is_paused.is_set() else ""
            command = input(f"Alumen Interattivo {prompt_indicator}> ").strip().lower()
            with command_lock:
                if command == "skip api": user_command_skip_api = True; print("   COMANDO RICEVUTO: 'skip api'.")
                elif command == "skip file": user_command_skip_file = True; print("   COMANDO RICEVUTO: 'skip file'.")
                elif command == "pause": script_is_paused.clear(); print("   COMANDO RICEVUTO: 'pause'.")
                elif command == "resume": script_is_paused.set(); print("   COMANDO RICEVUTO: 'resume'.")
                elif command == "help": print("\n   Comandi: pause, resume, skip api, skip file, exit/quit\n")
                elif command in ["exit", "quit"]: print("   INFO: Thread input comandi terminato."); break
                elif command: print(f"   Comando non riconosciuto: '{command}'. Digita 'help'.")
        except (EOFError, KeyboardInterrupt): print("\nINFO: Chiusura console interattiva."); break
        except Exception as e: print(f"🛑 Errore nel thread input comandi: {e}"); break
        
def check_and_wait_if_paused(file_context=""):
    global script_is_paused
    if script_args.interactive and not script_is_paused.is_set():
        sys.stdout.write("\r" + " " * 40 + "\r")
        print(f"\n\n⏳ Script in PAUSA (Contesto: {file_context}). Digita 'resume' per continuare...\n")
        script_is_paused.wait()
        print(f"▶️  Script RIPRESO (Contesto: {file_context}).\n")

def wait_for_rpm_limit():
    global rpm_limit, rpm_request_timestamps
    if not rpm_limit or rpm_limit <= 0: return
    while True:
        if script_args.interactive: check_and_wait_if_paused("Attesa RPM")
        with rpm_lock:
            current_time = time.time()
            rpm_request_timestamps[:] = [ts for ts in rpm_request_timestamps if ts > current_time - 60.0]
            if len(rpm_request_timestamps) < rpm_limit:
                rpm_request_timestamps.append(current_time)
                break
            else:
                if script_args.rotate_on_limit_or_error and rotate_api_key(reason_override="Limite RPM raggiunto"): break
                wait_duration = (rpm_request_timestamps[0] + 60.0) - current_time
        if wait_duration > 0:
            print(f"    INFO: Limite RPM ({rpm_limit}/min). Attesa: {wait_duration:.1f}s...")
            time.sleep(wait_duration)

def determine_if_translatable(text_value):
    if not isinstance(text_value, str): return False
    text_value_stripped = text_value.strip()
    if not text_value_stripped or text_value_stripped.isdigit() or re.match(r'^[\W_]+$', text_value_stripped) or "\\u" in text_value_stripped:
        return False
    return True

def handle_api_error(e, context_for_log, active_key_display, attempt_num):
    error_message_str = str(e)
    print(f"    - Tentativo {attempt_num + 1}/{MAX_RETRIES_PER_API_CALL} (Key ...{active_key_display}) Errore API: {error_message_str}")
    write_to_log(f"ERRORE API: {context_for_log}, Tentativo {attempt_num + 1}, Key ...{active_key_display}. Errore: {error_message_str}")
    retry_delay_seconds = DEFAULT_API_ERROR_RETRY_SECONDS
    match = re.search(r"retry_delay\s*{\s*seconds:\s*(\d+)\s*}", error_message_str, re.IGNORECASE)
    if match: retry_delay_seconds = int(match.group(1)) + 1
    return retry_delay_seconds

def get_translation_from_api(text_to_translate, context_for_log, args):
    """
    Funzione centralizzata per ottenere la traduzione. Gestisce i tentativi, la rotazione delle API,
    i limiti RPM e la costruzione del prompt.
    """
    global major_failure_count, user_command_skip_api, model

    if not determine_if_translatable(text_to_translate):
        return text_to_translate

    while True: # Ciclo per gestire la rotazione delle API in caso di fallimento totale
        if args.interactive: check_and_wait_if_paused(context_for_log)
        
        with command_lock:
            if user_command_skip_api:
                rotate_api_key(triggered_by_user=True)
                user_command_skip_api = False

        active_key_short = available_api_keys[current_api_key_index][-4:]
        
        for attempt_idx in range(MAX_RETRIES_PER_API_CALL):
            try:
                wait_for_rpm_limit()
                
                if args.custom_prompt:
                    if "{text_to_translate}" not in args.custom_prompt:
                        print(f"    - ❌ ERRORE: Il prompt personalizzato non include '{{text_to_translate}}'. Salto.")
                        return text_to_translate # Ritorna il testo originale se il prompt è invalido
                    prompt_text = args.custom_prompt.format(text_to_translate=text_to_translate)
                else:
                    prompt_base = f"""Traduci il seguente testo da {args.source_lang} a {args.target_lang}, mantenendo il contesto del gioco '{args.game_name}' e preservando eventuali tag HTML, placeholder (come [p], {{player_name}}), o codici speciali. In caso di dubbi sul genere (Femminile o Maschile), utilizza il maschile."""
                    if args.prompt_context: prompt_base += f"\nIstruzione aggiuntiva: {args.prompt_context}."
                    prompt_base += "\nRispondi solo con la traduzione diretta."
                    prompt_text = f"{prompt_base}\nTesto originale:\n{text_to_translate}\n\nTraduzione in {args.target_lang}:"
                
                time.sleep(BASE_API_CALL_INTERVAL_SECONDS)
                response_obj = model.generate_content(prompt_text)
                translated_text = response_obj.text.strip()

                if args.wrap_at and args.wrap_at > 0:
                    translated_text = textwrap.fill(translated_text, width=args.wrap_at, newline=args.newline_char, replace_whitespace=False)
                
                major_failure_count = 0 # Resetta i fallimenti in caso di successo
                return translated_text

            except Exception as api_exc:
                if args.rotate_on_limit_or_error:
                    if rotate_api_key(reason_override=f"Errore API"):
                        break # Esce dal ciclo for dei tentativi per riprovare con la nuova chiave
                
                retry_delay = handle_api_error(api_exc, context_for_log, active_key_short, attempt_idx)
                if attempt_idx < MAX_RETRIES_PER_API_CALL - 1:
                    time.sleep(retry_delay)
        
        # Se tutti i tentativi falliscono per una chiave
        major_failure_count += 1
        print(f"    - Fallimento definitivo con Key ...{active_key_short}. Conteggio fallimenti: {major_failure_count}/{MAX_MAJOR_FAILURES_THRESHOLD}")
        
        if major_failure_count >= MAX_MAJOR_FAILURES_THRESHOLD:
            if not rotate_api_key():
                print("    ⚠️  ATTENZIONE: Rotazione API fallita. Pausa di 60s prima di ritentare.")
                time.sleep(60)
        else:
            time.sleep(15)

def traduci_testo_json(input_file, output_file, args):
    """Elabora un singolo file JSON."""
    file_basename = os.path.basename(input_file)
    print(f"\n--- Elaborazione JSON: {file_basename} ---")
    
    try:
        with open(input_file, 'r', encoding=args.encoding) as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        log_critical_error_and_exit(f"Impossibile leggere o parsare il file JSON '{input_file}': {e}")

    keys_to_translate = {k.strip() for k in args.json_keys.split(',')}
    translated_texts_for_only_output = []
    texts_to_translate_count = 0

    # Funzione ricorsiva per contare i testi traducibili
    def count_translatable_items(obj, path=""):
        nonlocal texts_to_translate_count
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                if current_path in keys_to_translate and determine_if_translatable(value):
                    texts_to_translate_count += 1
                else:
                    count_translatable_items(value, current_path)
        elif isinstance(obj, list):
            for item in obj:
                count_translatable_items(item, path)
    
    count_translatable_items(data)
    print(f"Trovati {texts_to_translate_count} valori da tradurre per le chiavi specificate.")
    processed_count = 0

    def traverse_and_translate(obj, path=""):
        nonlocal processed_count
        if isinstance(obj, dict):
            # Usiamo list(obj.items()) per creare una copia, permettendo la modifica del dizionario durante l'iterazione
            for key, value in list(obj.items()):
                current_path = f"{path}.{key}" if path else key
                if current_path in keys_to_translate and determine_if_translatable(value):
                    processed_count += 1
                    context_log = f"JSON '{file_basename}', Chiave: '{current_path}'"
                    print(f"\n  ({processed_count}/{texts_to_translate_count}) Traduzione per '{current_path}':")
                    print(f"    Originale: '{str(value)[:80]}...'")
                    
                    translated_value = get_translation_from_api(value, context_log, args)
                    obj[key] = translated_value
                    
                    print(f"    Tradotto:  '{str(translated_value)[:80]}...'")
                    if args.translation_only_output:
                        translated_texts_for_only_output.append(translated_value)
                else:
                    traverse_and_translate(value, current_path)
        elif isinstance(obj, list):
            for item in obj:
                traverse_and_translate(item, path)

    traverse_and_translate(data)

    try:
        with open(output_file, 'w', encoding=args.encoding) as f:
            if args.translation_only_output:
                for text in translated_texts_for_only_output:
                    f.write(text + "\n")
            else:
                json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        log_critical_error_and_exit(f"Impossibile scrivere il file di output '{output_file}': {e}")

    print(f"--- Completato JSON: {file_basename} ---")

def traduci_testo_csv(input_file, output_file, args):
    """Elabora un singolo file CSV."""
    file_basename = os.path.basename(input_file)
    print(f"\n--- Elaborazione CSV: {file_basename} ---")
    
    rows = []
    try:
        with open(input_file, 'r', encoding=args.encoding, newline='') as infile:
            reader = csv.reader(infile, delimiter=args.delimiter)
            rows = list(reader)
    except Exception as e:
        log_critical_error_and_exit(f"Impossibile leggere il file CSV '{input_file}': {e}")

    header = rows[0] if rows else None
    data_rows = rows[1:] if header else rows
    
    texts_to_translate_count = sum(1 for row in data_rows if len(row) > args.translate_col and determine_if_translatable(row[args.translate_col]))
    print(f"Trovate {texts_to_translate_count} righe da tradurre nella colonna {args.translate_col}.")
    processed_count = 0
    translated_texts_for_only_output = []

    for i, row in enumerate(data_rows):
        display_row_num = i + (2 if header else 1)
        if len(row) > args.translate_col and determine_if_translatable(row[args.translate_col]):
            processed_count += 1
            original_text = row[args.translate_col]
            context_log = f"CSV '{file_basename}', Riga: {display_row_num}"
            print(f"\n  ({processed_count}/{texts_to_translate_count}) Traduzione per riga {display_row_num}:")
            print(f"    Originale: '{original_text[:80]}...'")
            
            translated_text = get_translation_from_api(original_text, context_log, args)
            row[args.output_col] = translated_text
            
            print(f"    Tradotto:  '{translated_text[:80]}...'")
            if args.translation_only_output:
                translated_texts_for_only_output.append(translated_text)

    try:
        with open(output_file, 'w', encoding=args.encoding, newline='') as outfile:
            if args.translation_only_output:
                for text in translated_texts_for_only_output:
                    outfile.write(text + "\n")
            else:
                writer = csv.writer(outfile, delimiter=args.delimiter, quoting=csv.QUOTE_MINIMAL)
                if header: writer.writerow(header)
                writer.writerows(data_rows)
    except Exception as e:
        log_critical_error_and_exit(f"Impossibile scrivere il file di output '{output_file}': {e}")
        
    print(f"--- Completato CSV: {file_basename} ---")

def process_files_recursively(args):
    """Scansiona le cartelle, trova i file e avvia il processo di traduzione corretto."""
    base_input_dir = args.input
    total_files_found = 0

    print(f"\nInizio scansione per file *.{args.file_type} da: '{base_input_dir}'")
    
    for root_dir, dirs_list, files_list in os.walk(base_input_dir):
        # Evita di entrare nelle cartelle 'tradotto'
        if "tradotto" in dirs_list:
            dirs_list.remove("tradotto")

        files_to_process = [f for f in files_list if f.endswith(f'.{args.file_type}')]
        if not files_to_process: continue
            
        print(f"\nEsplorando cartella: '{root_dir}' - Trovati {len(files_to_process)} file *.{args.file_type}.")
        total_files_found += len(files_to_process)

        output_subfolder = os.path.join(root_dir, "tradotto")
        os.makedirs(output_subfolder, exist_ok=True)

        for filename in files_to_process:
            if script_args.interactive and user_command_skip_file:
                print(f"COMANDO 'skip file' ricevuto. Salto file '{filename}'.")
                with command_lock: user_command_skip_file = False
                continue

            if script_args.interactive: check_and_wait_if_paused(f"Inizio file: {filename}")
            
            input_path = os.path.join(root_dir, filename)
            output_filename = f"{os.path.splitext(filename)[0]}_trads.txt" if args.translation_only_output else filename
            output_path = os.path.join(output_subfolder, output_filename)
            
            if args.file_type == 'csv':
                traduci_testo_csv(input_path, output_path, args)
            elif args.file_type == 'json':
                traduci_testo_json(input_path, output_path, args)


if __name__ == "__main__":
    print(ALUMEN_ASCII_ART)
    print("Benvenuto in Alumen - Traduttore Automatico Multilingua!\n")

    args_parsed_main = get_script_args_updated()
    
    if args_parsed_main.file_type == 'json' and not args_parsed_main.json_keys:
        log_critical_error_and_exit("Per --file-type 'json', è obbligatorio specificare le chiavi con --json-keys.")

    script_is_paused.set()

    if args_parsed_main.enable_file_log: setup_log_file()
    initialize_api_keys_and_model()

    if not os.path.isdir(args_parsed_main.input):
        log_critical_error_and_exit(f"Il percorso di input '{args_parsed_main.input}' non è una cartella valida.")

    cmd_thread = None
    if args_parsed_main.interactive:
        cmd_thread = threading.Thread(target=command_input_thread_func, daemon=True)
        cmd_thread.start()

    try:
        process_files_recursively(args_parsed_main)
    except KeyboardInterrupt:
        print("\n🛑 Interruzione da tastiera (Ctrl+C). Uscita...")
        with command_lock: user_command_skip_file = True
    finally:
        if cmd_thread and cmd_thread.is_alive():
            print("INFO: Thread input comandi attivo (terminerà con lo script).")
        write_to_log(f"--- FINE Sessione Log: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        print("\nScript Alumen terminato.")
