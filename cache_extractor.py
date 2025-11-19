import os
import json
import argparse
import csv
import polib
import re
from argparse_color_formatter import ColorHelpFormatter

# Tentativo import openpyxl per Excel
try:
    import openpyxl
except ImportError:
    openpyxl = None

# Nome del file di cache di default
CACHE_FILE_NAME = "alumen_cache.json"

# --- Funzioni di supporto ---

def log_critical_error_and_exit(message):
    print(f"🛑 ERRORE CRITICO: {message}")
    exit(1)

def determine_if_translatable(text_value):
    """Logica identica ad AlumenCore per determinare se una stringa va in cache."""
    if not isinstance(text_value, str): return False
    text_value_stripped = text_value.strip()
    if not text_value_stripped or text_value_stripped.isdigit() or re.match(r'^[\W_]+$', text_value_stripped) or "\\u" in text_value_stripped:
        return False
    # Filtra variabili isolate es. {name} o <br> (Allineato con AlumenCore v2.5)
    if re.match(r'^\{[\w\.]+\}$', text_value_stripped) or re.match(r'^<[\w\s="/]+>$', text_value_stripped): 
        return False
    return True

def get_cache_key(original_text, args):
    """
    Genera la chiave di cache.
    ⚠️ IMPORTANTE: Allineato con AlumenCore v2.0/2.5
    Formato: (text, source_lang, target_lang)
    """
    # Nota: game_name e context sono stati rimossi dalla chiave nella v2.0 per favorire il riutilizzo
    cache_key_tuple = (original_text, args.source_lang, args.target_lang)
    return json.dumps(cache_key_tuple, ensure_ascii=False)

# --- Logica di Estrazione ---

def extract_from_csv(s_path, t_path, cache, args):
    try:
        with open(s_path, 'r', encoding=args.encoding) as sf, open(t_path, 'r', encoding=args.encoding) as tf:
            s_rows = list(csv.reader(sf, delimiter=args.delimiter))
            t_rows = list(csv.reader(tf, delimiter=args.delimiter))
    except Exception as e: print(f"  ❌ Err CSV {s_path}: {e}"); return

    added = 0
    for i in range(min(len(s_rows), len(t_rows))):
        if i == 0 and not args.no_header: continue # Skip header
        s_r, t_r = s_rows[i], t_rows[i]
        if len(s_r) > args.source_col and len(t_r) > args.target_col:
            src, tgt = s_r[args.source_col], t_r[args.target_col]
            if determine_if_translatable(src) and tgt.strip():
                key = get_cache_key(src, args)
                if key not in cache:
                    cache[key] = tgt
                    added += 1
    print(f"  ✅ CSV: Aggiunte {added} voci.")

def extract_from_json(s_path, t_path, cache, args):
    try:
        with open(s_path, 'r', encoding=args.encoding) as sf, open(t_path, 'r', encoding=args.encoding) as tf:
            s_data, t_data = json.load(sf), json.load(tf)
    except Exception as e: print(f"  ❌ Err JSON {s_path}: {e}"); return

    keys = set(args.json_keys.split(','))
    added = 0
    
    def traverse(s_obj, t_obj, path=""):
        nonlocal added
        if isinstance(s_obj, dict) and isinstance(t_obj, dict):
            for k, v in s_obj.items():
                curr = f"{path}.{k}" if path else k
                is_match = (curr in keys) if args.match_full_json_path else (k in keys)
                tgt_v = t_obj.get(k)
                if is_match and isinstance(v, str) and isinstance(tgt_v, str) and determine_if_translatable(v) and tgt_v.strip():
                    key = get_cache_key(v, args)
                    if key not in cache:
                        cache[key] = tgt_v
                        added += 1
                if k in t_obj: traverse(v, t_obj.get(k), curr)
        elif isinstance(s_obj, list) and isinstance(t_obj, list):
            for i in range(min(len(s_obj), len(t_obj))): traverse(s_obj[i], t_obj[i], path)

    traverse(s_data, t_data)
    print(f"  ✅ JSON: Aggiunte {added} voci.")

def extract_from_po(t_path, cache, args):
    try:
        po = polib.pofile(t_path, encoding=args.encoding)
    except Exception as e: print(f"  ❌ Err PO {t_path}: {e}"); return
    added = 0
    for e in po:
        if e.msgid and e.msgstr and determine_if_translatable(e.msgid):
            key = get_cache_key(e.msgid, args)
            if key not in cache:
                cache[key] = e.msgstr
                added += 1
    print(f"  ✅ PO: Aggiunte {added} voci.")

def extract_from_srt(s_path, t_path, cache, args):
    try:
        with open(s_path, 'r', encoding=args.encoding) as f: s_txt = f.read()
        with open(t_path, 'r', encoding=args.encoding) as f: t_txt = f.read()
    except Exception: return

    # Regex SRT semplice
    pattern = re.compile(r'\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}\s*\n(.*?)(?=\n\s*\n|\Z)', re.DOTALL)
    s_matches = [m.group(1).strip() for m in pattern.finditer(s_txt)]
    t_matches = [m.group(1).strip() for m in pattern.finditer(t_txt)]

    added = 0
    for src, tgt in zip(s_matches, t_matches):
        if determine_if_translatable(src) and tgt:
            key = get_cache_key(src, args)
            if key not in cache:
                cache[key] = tgt
                added += 1
    print(f"  ✅ SRT: Aggiunte {added} voci.")

def extract_from_xlsx(s_path, t_path, cache, args):
    if not openpyxl: print("  ⚠️ Modulo openpyxl mancante. Salto XLSX."); return
    try:
        wb_s = openpyxl.load_workbook(s_path, read_only=True)
        wb_t = openpyxl.load_workbook(t_path, read_only=True)
        ws_s = wb_s.active
        ws_t = wb_t.active
    except Exception as e: print(f"  ❌ Err XLSX {s_path}: {e}"); return

    # Converti lettere colonna (A, B) in indici 0-based
    try:
        s_idx = openpyxl.utils.column_index_from_string(args.xlsx_source_col) - 1
        t_idx = openpyxl.utils.column_index_from_string(args.xlsx_target_col) - 1
    except: print("  ❌ Colonne Excel non valide."); return

    added = 0
    # Itera sulle righe (zip per sicurezza)
    for r_s, r_t in zip(ws_s.iter_rows(), ws_t.iter_rows()):
        if len(r_s) > s_idx and len(r_t) > t_idx:
            src = r_s[s_idx].value
            tgt = r_t[t_idx].value
            if isinstance(src, str) and isinstance(tgt, str) and determine_if_translatable(src) and tgt.strip():
                key = get_cache_key(src, args)
                if key not in cache:
                    cache[key] = tgt
                    added += 1
    print(f"  ✅ XLSX: Aggiunte {added} voci.")

# --- Main ---

def process_files(args, cache):
    s_dir, t_dir = os.path.abspath(args.source_dir), os.path.abspath(args.target_dir)
    print(f"Scansione: {s_dir} -> {t_dir} (Format: {args.file_type})")
    
    for root, _, files in os.walk(s_dir):
        rel = os.path.relpath(root, s_dir)
        curr_t_dir = os.path.join(t_dir, rel)
        target_files = [f for f in files if f.endswith(f'.{args.file_type}')]
        
        for fname in target_files:
            s_path = os.path.join(root, fname)
            t_path = os.path.join(curr_t_dir, fname)
            
            if args.file_type == 'po': # PO file has both src and tgt
                t_path = s_path 
            
            if not os.path.exists(t_path) and args.file_type != 'po':
                continue

            print(f" Elaborazione: {fname}")
            if args.file_type == 'csv': extract_from_csv(s_path, t_path, cache, args)
            elif args.file_type == 'json': extract_from_json(s_path, t_path, cache, args)
            elif args.file_type == 'po': extract_from_po(s_path, cache, args)
            elif args.file_type == 'srt': extract_from_srt(s_path, t_path, cache, args)
            elif args.file_type == 'xlsx': extract_from_xlsx(s_path, t_path, cache, args)

def main():
    parser = argparse.ArgumentParser(description="Alumen Cache Extractor v2.5", formatter_class=ColorHelpFormatter)
    
    g = parser.add_argument_group('Configurazione')
    g.add_argument("--source-dir", required=True, help="Cartella file ORIGINALI")
    g.add_argument("--target-dir", required=True, help="Cartella file TRADOTTI")
    g.add_argument("--file-type", default="csv", choices=['csv', 'json', 'po', 'srt', 'xlsx'])
    g.add_argument("--encoding", default="utf-8")
    g.add_argument("--output-cache-file", default=CACHE_FILE_NAME)
    g.add_argument("--append", action="store_true")

    c = parser.add_argument_group('CSV/Excel')
    c.add_argument("--delimiter", default=",")
    c.add_argument("--source-col", type=int, default=3, help="Index colonna originale (CSV)")
    c.add_argument("--target-col", type=int, default=3, help="Index colonna tradotta (CSV)")
    c.add_argument("--xlsx-source-col", default="A", help="Lettera colonna originale (Excel)")
    c.add_argument("--xlsx-target-col", default="B", help="Lettera colonna tradotta (Excel)")
    c.add_argument("--no-header", action="store_true")

    j = parser.add_argument_group('JSON')
    j.add_argument("--json-keys", default=None)
    j.add_argument("--match-full-json-path", action="store_true")

    t = parser.add_argument_group('Parametri Traduzione (Devono coincidere con AlumenCore)')
    t.add_argument("--source-lang", default="inglese")
    t.add_argument("--target-lang", default="italiano")
    # Nota: game-name e prompt-context rimossi dalla chiave cache v2.0 per universalità

    args = parser.parse_args()
    if args.delimiter == '\\t': args.delimiter = '\t'

    cache = {}
    if args.append and os.path.exists(args.output_cache_file):
        try: 
            with open(args.output_cache_file, 'r', encoding='utf-8') as f: cache = json.load(f)
            print(f"Cache caricata: {len(cache)} voci.")
        except: pass

    process_files(args, cache)

    if cache:
        with open(args.output_cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=4)
        print(f"🎉 Cache salvata: {args.output_cache_file} ({len(cache)} voci).")
    else:
        print("Nessuna voce estratta.")

if __name__ == "__main__":
    main()    entries_added = 0
    entries_skipped = 0 # MODIFICA: Aggiunto contatore per le voci saltate

    def _traverse_and_extract(source_obj, target_obj, path=""):
        nonlocal entries_added, entries_skipped
        if isinstance(source_obj, dict) and isinstance(target_obj, dict):
            for key, source_value in source_obj.items():
                current_path = f"{path}.{key}" if path else key
                target_value = target_obj.get(key)
                
                is_match = (current_path in keys_to_translate) if args.match_full_json_path else (key in keys_to_translate)
                
                if is_match and determine_if_translatable(source_value) and isinstance(target_value, str) and target_value.strip():
                    key_cache = get_cache_key(source_value, args)
                    # MODIFICA: Aggiunto controllo per evitare di aggiungere chiavi esistenti
                    if key_cache not in cache_map:
                        cache_map[key_cache] = target_value
                        entries_added += 1
                    else:
                        entries_skipped += 1
                
                if key in target_obj:
                    _traverse_and_extract(source_value, target_value, current_path)
                    
        elif isinstance(source_obj, list) and isinstance(target_obj, list):
            for i in range(min(len(source_obj), len(target_obj))):
                 _traverse_and_extract(source_obj[i], target_obj[i], path)

    _traverse_and_extract(source_data, target_data)
    # MODIFICA: Aggiornato il messaggio di output
    print(f"    ✅ Aggiunte {entries_added} nuove voci. Saltate {entries_skipped} voci già presenti in cache.")


def extract_cache_from_po(target_path, cache_map, args):
    """Estrae le coppie di cache dai file PO (msgid -> msgstr)."""
    try:
        po_file = polib.pofile(target_path, encoding=args.encoding)
    except FileNotFoundError:
        print(f"    ⚠️  Target file mancante: '{target_path}'. Salto.")
        return
    except Exception as e:
        print(f"    ❌ Errore lettura PO: {e}. Salto.")
        return

    entries_added = 0
    entries_skipped = 0 # MODIFICA: Aggiunto contatore per le voci saltate
    for entry in po_file:
        if entry.msgid and entry.msgstr and determine_if_translatable(entry.msgid):
            original_text = entry.msgid
            translated_text = entry.msgstr
            key = get_cache_key(original_text, args)
            # MODIFICA: Aggiunto controllo per evitare di aggiungere chiavi esistenti
            if key not in cache_map:
                cache_map[key] = translated_text
                entries_added += 1
            else:
                entries_skipped += 1
            
    # MODIFICA: Aggiornato il messaggio di output
    print(f"    ✅ Aggiunte {entries_added} nuove voci. Saltate {entries_skipped} voci già presenti in cache.")

# --- Processo Principale ---

def process_files_recursively(args, cache_map):
    """Scansiona le cartelle, trova i file e avvia il processo di estrazione."""
    source_dir = os.path.abspath(args.source_dir)
    target_dir = os.path.abspath(args.target_dir)

    print(f"\nInizio scansione per file *.{args.file_type} dalla sorgente: '{source_dir}'")
    
    file_count = 0
    for root_dir, dirs_list, files_list in os.walk(source_dir):
        relative_path = os.path.relpath(root_dir, source_dir)
        current_target_dir = os.path.join(target_dir, relative_path)
        
        files_to_process = [f for f in files_list if f.endswith(f'.{args.file_type}')]
        
        for filename in files_to_process:
            file_count += 1
            source_path = os.path.join(root_dir, filename)
            target_path = os.path.join(current_target_dir, filename)
            
            print(f"\n[{file_count}] Elaborazione: {os.path.join(relative_path, filename)}")
            
            if args.file_type == 'csv':
                # FIX: Rimosso controllo 'required' che falliva, ora è gestito qui
                if args.source_col is None or args.target_col is None:
                    log_critical_error_and_exit("Per i file CSV, è obbligatorio specificare --source-col e --target-col.")
                extract_cache_from_csv(source_path, target_path, cache_map, args)
            elif args.file_type == 'json':
                if not args.json_keys:
                    log_critical_error_and_exit("Per i file JSON, è obbligatorio specificare --json-keys.")
                extract_cache_from_json(source_path, target_path, cache_map, args)
            elif args.file_type == 'po':
                extract_cache_from_po(target_path, cache_map, args)

def main():
    parser = argparse.ArgumentParser(
        description="Cache Extractor - Script per costruire la cache di traduzione da file sorgente e target esistenti.",
        formatter_class=ColorHelpFormatter
    )

    file_group = parser.add_argument_group('\033[96mConfigurazione File\033[0m')
    file_group.add_argument("--source-dir", type=str, required=True, help="\033[97mPercorso della cartella contenente i file ORIGINALI (sorgente).\033[0m")
    file_group.add_argument("--target-dir", type=str, required=True, help="\033[97mPercorso della cartella contenente i file TRADOTTI (target).\033[0m")
    file_group.add_argument("--file-type", type=str, default="csv", choices=['csv', 'json', 'po'], help="\033[97mTipo di file da elaborare: 'csv', 'json' o 'po'. Default: 'csv'\033[0m")
    file_group.add_argument("--encoding", type=str, default="utf-8", help="\033[97mCodifica caratteri dei file. Default: 'utf-8'\033[0m")

    csv_options_group = parser.add_argument_group('\033[96mOpzioni Specifiche per CSV\033[0m')
    csv_options_group.add_argument("--delimiter", type=str, default=",", help="\033[97m[Solo CSV] Carattere delimitatore. Default: ','\033[0m")
    csv_options_group.add_argument("--source-col", type=int, help="\033[97m[Solo CSV] Indice (0-based) della colonna con il testo ORIGINALE nel file sorgente.\033[0m")
    csv_options_group.add_argument("--target-col", type=int, help="\033[97m[Solo CSV] Indice (0-based) della colonna con il testo TRADOTTO nel file target.\033[0m")
    csv_options_group.add_argument("--no-header", action="store_true", help="\033[97m[Solo CSV] Non saltare la prima riga.\033[0m")
    
    json_options_group = parser.add_argument_group('\033[96mOpzioni Specifiche per JSON\033[0m')
    json_options_group.add_argument("--json-keys", type=str, default=None, help="\033[97m[Solo JSON, Obbligatorio] Elenco di chiavi (separate da virgola) che sono state tradotte (es. 'key1,path.to.key2').\033[0m")
    json_options_group.add_argument("--match-full-json-path", action="store_true", help="\033[97m[Solo JSON] Richiede la corrispondenza del percorso completo della chiave (es. 'parent.child.key'), non solo del nome.\033[0m")


    translation_group = parser.add_argument_group('\033[96mParametri di Cache (DEVONO CORRISPONDERE A QUELLI USATI PER LA TRADUZIONE)\033[0m')
    translation_group.add_argument("--game-name", type=str, default="un videogioco generico", help="\033[97mNome del gioco usato per la contestualizzazione.\033[0m")
    translation_group.add_argument("--source-lang", type=str, default="inglese", help="\033[97mLingua originale del testo.\033[0m")
    translation_group.add_argument("--target-lang", type=str, default="italiano", help="\033[97mLingua di destinazione.\033[0m")
    translation_group.add_argument("--prompt-context", type=str, default=None, help="\033[97MInformazione contestuale extra usata nel prompt.\033[0m")
    translation_group.add_argument("--output-cache-file", type=str, default=CACHE_FILE_NAME, help=f"\033[97mNome del file di cache da creare. Default: '{CACHE_FILE_NAME}'\033[0m")
    translation_group.add_argument("--append", action="store_true", help="\033[97mAggiunge le nuove voci a una cache esistente invece di sovrascriverla.\033[0m")

    args = parser.parse_args()

    if args.delimiter == '\\t':
        args.delimiter = '\t'
        
    cache_map = {}
    
    if args.append and os.path.exists(args.output_cache_file):
        try:
            with open(args.output_cache_file, 'r', encoding='utf-8') as f:
                cache_map = json.load(f)
            print(f"✅ Cache esistente caricata da '{args.output_cache_file}' con {len(cache_map)} voci.")
        except json.JSONDecodeError:
            print("⚠️  Attenzione: Impossibile decodificare la cache esistente. Inizio con una cache vuota.")

    try:
        process_files_recursively(args, cache_map)
    except KeyboardInterrupt:
        print("\n🛑 Interruzione da tastiera (Ctrl+C). Salvataggio cache parziale...")
    
    print("\n--- Salvataggio Cache ---")
    
    if not cache_map:
        print("ℹ️  Nessuna voce di cache estratta. File di cache non creato.")
        return

    try:
        with open(args.output_cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_map, f, ensure_ascii=False, indent=4)
        
        print(f"🎉 Processo completato. {len(cache_map)} voci di cache salvate in '{args.output_cache_file}'.")
        print("Ora puoi usare questo file con il tuo script Alumen.py (opzione --persistent-cache).")
    except Exception as e:
        log_critical_error_and_exit(f"Impossibile scrivere il file di cache: {e}")

if __name__ == "__main__":
    main()
