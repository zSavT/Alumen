# Contenuto completo del file modificato 'Alumen.py'

import time
import google.generativeai as genai
import google.api_core.exceptions
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
import polib

# ----- Costanti Globali -----
MAX_RETRIES_PER_API_CALL = 3
MAX_MAJOR_FAILURES_THRESHOLD = 6
DEFAULT_MODEL_NAME = "gemini-1.5-flash"
LOG_FILE_NAME = "log.txt"
CACHE_FILE_NAME = "alumen_cache.json"
DEFAULT_API_ERROR_RETRY_SECONDS = 10
BASE_API_CALL_INTERVAL_SECONDS = 0.2
FILE_CONTEXT_SAMPLE_SIZE = 15

# ----- Variabili Globali -----
available_api_keys = []
current_api_key_index = 0
major_failure_count = 0
model = None
script_args = None
log_file_path = None
translation_cache = {}
BLACKLIST_TERMS = set(["Dummy", "dummy"])
blacklisted_api_key_indices = set()
api_call_counts = {}
cache_hit_count = 0
start_time = 0.0
total_files_translated = 0
total_entries_translated = 0
last_cache_save_time = 0.0
rpm_limit = None
rpm_request_timestamps = []
rpm_lock = Lock()

# ----- Variabili per la Modalità Interattiva -----
user_command_skip_api = False
user_command_skip_file = False
script_is_paused = Event()
command_lock = Lock()
graceful_exit_requested = Event()
current_file_context = None
current_file_total_entries = 0
current_file_processed_entries = 0

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
        description="Alumen - Script per tradurre file CSV, JSON o PO utilizzando Google Gemini.",
        formatter_class=ColorHelpFormatter
    )
    api_group = parser.add_argument_group('\033[96mConfigurazione API e Modello\033[0m')
    file_format_group = parser.add_argument_group('\033[96mConfigurazione File e Formato\033[0m')
    csv_options_group = parser.add_argument_group('\033[96mOpzioni Specifiche per CSV\033[0m')
    json_options_group = parser.add_argument_group('\033[96mOpzioni Specifiche per JSON\033[0m')
    translation_group = parser.add_argument_group('\033[96mParametri di Traduzione\033[0m')
    wrapping_group = parser.add_argument_group('\033[96mOpzioni A Capo Automatico (Word Wrapping)\033[0m')
    utility_group = parser.add_argument_group('\033[96mUtilità e Modalità Interattiva\033[0m')
    api_group.add_argument("--api", type=str, help="\033[97mSpecifica una o più chiavi API Google Gemini, separate da virgola.\033[0m")
    api_group.add_argument("--model-name", type=str, default=DEFAULT_MODEL_NAME, help=f"\033[97mNome del modello Gemini da utilizzare. Default: '{DEFAULT_MODEL_NAME}'\033[0m")
    file_format_group.add_argument("--input", type=str, default="input", help="\033[97mPercorso della cartella base contenente i file da tradurre. Default: 'input'\033[0m")
    file_format_group.add_argument("--file-type", type=str, default="csv", choices=['csv', 'json', 'po'], help="\033[97mTipo di file da elaborare: 'csv', 'json' o 'po'. Default: 'csv'\033[0m")
    file_format_group.add_argument("--encoding", type=str, default="utf-8", help="\033[97mCodifica caratteri dei file. Default: 'utf-8'\033[0m")
    csv_options_group.add_argument("--delimiter", type=str, default=",", help="\033[97m[Solo CSV] Carattere delimitatore. Default: ','\033[0m")
    csv_options_group.add_argument("--translate-col", type=int, default=3, help="\033[97m[Solo CSV] Indice (0-based) della colonna da tradurre. Default: 3\033[0m")
    csv_options_group.add_argument("--output-col", type=int, default=3, help="\033[97m[Solo CSV] Indice (0-based) della colonna per il testo tradotto. Default: 3\033[0m")
    csv_options_group.add_argument("--max-cols", type=int, default=None, help="\033[97m[Solo CSV] Numero massimo di colonne attese per riga. Default: Nessun controllo.\033[0m")
    json_options_group.add_argument("--json-keys", type=str, default=None, help="\033[97m[Solo JSON, Obbligatorio] Elenco di chiavi (separate da virgola) da tradurre. Supporta notazione a punto per chiavi annidate (es. 'key1,path.to.key2').\033[0m")
    json_options_group.add_argument("--match-full-json-path", action="store_true", help="\033[97m[Solo JSON] Per le chiavi JSON, richiede la corrispondenza del percorso completo della chiave (es. 'parent.child.key'), invece del solo nome della chiave.\033[0m")
    translation_group.add_argument("--game-name", type=str, default="un videogioco generico", help="\033[97mNome del gioco per contestualizzare la traduzione.\033[0m")
    translation_group.add_argument("--source-lang", type=str, default="inglese", help="\033[97mLingua originale del testo.\033[0m")
    translation_group.add_argument("--target-lang", type=str, default="italiano", help="\033[97mLingua di destinazione.\033[0m")
    translation_group.add_argument("--prompt-context", type=str, default=None, help="\033[97mAggiunge un'informazione contestuale extra al prompt.\033[0m")
    translation_group.add_argument("--custom-prompt", type=str, default=None, help="\033[97mUsa un prompt personalizzato. OBBLIGATORIO: includere '{text_to_translate}'.\033[0m")
    translation_group.add_argument("--translation-only-output", action="store_true", help="\033[97mL'output conterrà solo i testi tradotti, uno per riga.\033[0m")
    translation_group.add_argument("--rpm", type=int, default=None, help="\033[97mNumero massimo di richieste API a Gemini per minuto.\033[0m")
    translation_group.add_argument("--enable-file-context", action="store_true", help="\033[97mAbilita l'analisi di un campione del file per generare un contesto generale da usare in tutte le traduzioni del file.\033[0m")
    translation_group.add_argument("--full-context-sample", action="store_true", help="\033[97m[Necessita --enable-file-context] Utilizza TUTTE le frasi valide nel file (anziché solo le prime 15) per generare il contesto generale. Attenzione: può risultare in richieste API molto grandi.\033[0m")
    wrapping_group.add_argument("--wrap-at", type=int, default=None, help="\033[97mLunghezza massima della riga per a capo automatico.\033[0m")
    wrapping_group.add_argument("--newline-char", type=str, default='\\n', help="\033[97mCarattere da usare per l'a capo automatico.\033[0m")
    utility_group.add_argument("--oneThread", action="store_true", help="\033[97mDisabilita l'animazione di caricamento/progresso. Utile per terminali senza supporto adeguato.")
    utility_group.add_argument("--enable-file-log", action="store_true", help=f"\033[97mAttiva la scrittura di un log ('{LOG_FILE_NAME}').\033[0m")
    utility_group.add_argument("--interactive", action="store_true", help="\033[97mAbilita comandi interattivi.\033[0m")
    utility_group.add_argument("--resume", action="store_true", help="\033[97mTenta di riprendere la traduzione da file parziali.\033[0m")
    utility_group.add_argument("--rotate-on-limit-or-error", action="store_true", help="\033[97mPassa alla API key successiva in caso di errore o limite RPM.\033[0m")
    utility_group.add_argument("--persistent-cache", action="store_true", help=f"\033[97mAttiva la cache persistente su file ('{CACHE_FILE_NAME}').\033[0m")
    parsed_args = parser.parse_args()
    if parsed_args.delimiter == '\\t': parsed_args.delimiter = '\t'
    if parsed_args.newline_char == '\\n': parsed_args.newline_char = '\n'
    elif parsed_args.newline_char == '\\r\\n': parsed_args.newline_char = '\r\n'
    script_args = parsed_args
    return parsed_args

def format_time_delta(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"

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
        print(f"ℹ️  Logging su file abilitato. I log verranno salvati in: '{log_file_path}'")
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
    global available_api_keys, current_api_key_index, model, rpm_limit, api_call_counts
    print("\n--- Inizializzazione API e Modello ---")
    if script_args.api:
        keys_from_arg = [key.strip() for key in script_args.api.split(',') if key.strip()]
        if keys_from_arg:
            available_api_keys.extend(keys_from_arg)
            print(f"✅ Trovate {len(keys_from_arg)} API key dall'argomento --api.")
    api_key_file_path = "api_key.txt"
    if os.path.exists(api_key_file_path):
        with open(api_key_file_path, "r") as f:
            keys_from_file = [line.strip() for line in f if line.strip()]
            if keys_from_file:
                available_api_keys.extend(keys_from_file)
                print(f"✅ Caricate {len(keys_from_file)} API key dal file '{api_key_file_path}'.")
    seen = set()
    available_api_keys = [x for x in available_api_keys if not (x in seen or seen.add(x))]
    if not available_api_keys:
        log_critical_error_and_exit("Nessuna API key trovata. Specificare tramite --api o nel file 'api_key.txt'.")
    api_call_counts = {i: 0 for i in range(len(available_api_keys))}
    print(f"ℹ️  Totale API keys uniche disponibili: {len(available_api_keys)}.")
    current_api_key_index = 0
    try:
        current_key = available_api_keys[current_api_key_index]
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel(script_args.model_name)
        print(f"✅ Modello '{script_args.model_name}' pronto. API Key attiva: ...{current_key[-4:]}")
    except Exception as e:
        log_critical_error_and_exit(f"Errore durante l'inizializzazione del modello '{script_args.model_name}': {e}")
    if script_args.rpm and script_args.rpm > 0:
        rpm_limit = script_args.rpm
        print(f"ℹ️  Limite RPM impostato a {rpm_limit} richieste al minuto.")
    print("--------------------------------------------------")

def add_api_key(new_key):
    global available_api_keys, api_call_counts, blacklisted_api_key_indices
    new_key = new_key.strip()
    if not new_key:
        print("   🛑 ERRORE: La chiave API non può essere vuota.")
        return False
    if new_key in available_api_keys:
        print("   ℹ️  Questa API key è già presente nella lista.")
        return False
    available_api_keys.append(new_key)
    new_index = len(available_api_keys) - 1
    api_call_counts[new_index] = 0
    blacklisted_api_key_indices.discard(new_index)
    print(f"   ✅ Nuova API Key ...{new_key[-4:]} aggiunta. Totale chiavi disponibili: {len(available_api_keys)}.")
    write_to_log(f"COMANDO INTERATTIVO: Aggiunta nuova API Key ...{new_key[-4:]}")
    return True

# --- FUNZIONI DI GESTIONE API E PERFORMANCE ---

def list_api_keys():
    print("\n--- Elenco Chiavi API Disponibili ---")
    usable_count = len(available_api_keys) - len(blacklisted_api_key_indices)
    print(f"Totale chiavi: {len(available_api_keys)}. Utilizzabili: {usable_count}.")
    print("-" * 35)
    for i, key in enumerate(available_api_keys):
        key_suffix = key[-4:]
        status = " "
        if i == current_api_key_index: status = "(ATTIVA)"
        if i in blacklisted_api_key_indices: status = "(BLACKLISTED)"
        calls = api_call_counts.get(i, 0)
        print(f"[{i:2}] ...{key_suffix:4} {status:<15} - {calls} chiamate")
    print("-" * 35)

def remove_api_key(index_str):
    global available_api_keys, current_api_key_index, api_call_counts, blacklisted_api_key_indices
    try:
        index = int(index_str)
        if not (0 <= index < len(available_api_keys)):
            print(f"   🛑 ERRORE: Indice {index} fuori dal range valido (0 a {len(available_api_keys) - 1}).")
            return
        key_suffix = available_api_keys[index][-4:]
        del available_api_keys[index]
        if index in blacklisted_api_key_indices: blacklisted_api_key_indices.discard(index)
        
        # Rimuovi/Rialloca i contatori e la blacklist
        new_api_call_counts = {}
        new_blacklisted_indices = set()
        for old_index, count in api_call_counts.items():
            if old_index < index: new_api_call_counts[old_index] = count
            elif old_index > index:
                new_index = old_index - 1
                new_api_call_counts[new_index] = count
                if old_index in blacklisted_api_key_indices: new_blacklisted_indices.add(new_index)
        api_call_counts = new_api_call_counts
        blacklisted_api_key_indices = new_blacklisted_indices
        
        if current_api_key_index == index:
            print(f"   ⚠️  La chiave rimossa era quella attiva. Rotazione necessaria.")
            if available_api_keys:
                current_api_key_index = index % len(available_api_keys) if index < len(available_api_keys) else len(available_api_keys) - 1
                rotate_api_key(reason_override="Chiave attiva rimossa")
            else:
                log_critical_error_and_exit("Tutte le API key rimosse. Impossibile proseguire.")
        elif current_api_key_index > index:
            current_api_key_index -= 1

        print(f"   ✅ API Key ...{key_suffix} all'indice {index} rimossa.")
        write_to_log(f"COMANDO INTERATTIVO: Rimossa API Key ...{key_suffix} all'indice {index}")
    except ValueError:
        print("   🛑 ERRORE: L'indice deve essere un numero intero.")
    except Exception as e:
        print(f"   🛑 ERRORE: Impossibile rimuovere la chiave API: {e}")

def blacklist_specific_api_key(index_str):
    global current_api_key_index, blacklisted_api_key_indices
    try:
        index = int(index_str)
        if not (0 <= index < len(available_api_keys)):
            print(f"   🛑 ERRORE: Indice {index} fuori dal range valido (0 a {len(available_api_keys) - 1}).")
            return
        if index in blacklisted_api_key_indices:
            print(f"   ℹ️  L'API Key ...{available_api_keys[index][-4:]} è già in blacklist.")
            return

        key_suffix = available_api_keys[index][-4:]
        blacklisted_api_key_indices.add(index)
        print(f"   ✅ API Key ...{key_suffix} all'indice {index} aggiunta alla blacklist.")
        write_to_log(f"COMANDO INTERATTIVO: API Key ...{key_suffix} all'indice {index} aggiunta alla blacklist.")

        if index == current_api_key_index:
            rotate_api_key(triggered_by_user=True, reason_override="Key blacklisted da comando")
    except ValueError:
        print("   🛑 ERRORE: L'indice deve essere un numero intero.")
    except Exception as e:
        print(f"   🛑 ERRORE: Impossibile blackistare la chiave API: {e}")

def clear_blacklisted_keys():
    global blacklisted_api_key_indices
    count = len(blacklisted_api_key_indices)
    if count == 0:
        print("   ℹ️  Nessuna chiave era in blacklist.")
        return
    blacklisted_api_key_indices.clear()
    print(f"   ✅ {count} chiavi rimosse dalla blacklist. Ora sono nuovamente disponibili.")
    write_to_log(f"COMANDO INTERATTIVO: {count} chiavi rimosse dalla blacklist.")

def set_rpm_limit_func(rpm_str):
    global rpm_limit, rpm_request_timestamps
    try:
        new_rpm = int(rpm_str)
        if new_rpm < 0:
            print("   🛑 ERRORE: Il limite RPM non può essere negativo.")
            return
        if new_rpm == 0:
            rpm_limit = None
            print("   ✅ Limite RPM disabilitato.")
            write_to_log("COMANDO INTERATTIVO: Limite RPM disabilitato.")
        else:
            rpm_limit = new_rpm
            with rpm_lock:
                # Resetta i timestamp per applicare subito il nuovo limite
                rpm_request_timestamps.clear()
            print(f"   ✅ Nuovo limite RPM impostato a {new_rpm}.")
            write_to_log(f"COMANDO INTERATTIVO: Nuovo limite RPM impostato a {new_rpm}.")
    except ValueError:
        print("   🛑 ERRORE: Il limite RPM deve essere un numero intero.")

def show_rpm_stats(title="Statistiche RPM"):
    global rpm_limit, rpm_request_timestamps
    current_time = time.time()
    with rpm_lock:
        rpm_request_timestamps[:] = [ts for ts in rpm_request_timestamps if ts > current_time - 60.0]
        current_rpm = len(rpm_request_timestamps)
    limit_display = f"{rpm_limit}/min" if rpm_limit is not None else "Disabilitato"
    print(f"\n--- {title} ---")
    print(f"  Limite impostato:  {limit_display}")
    print(f"  Utilizzo ultimi 60s: {current_rpm} chiamate")
    if rpm_limit is not None and rpm_limit > 0:
        remaining = rpm_limit - current_rpm
        print(f"  Chiamate rimanenti: {max(0, remaining)}")
        if current_rpm >= rpm_limit:
            wait_duration = (rpm_request_timestamps[0] + 60.0) - current_time
            print(f"  Attesa necessaria:  {max(0.0, wait_duration):.2f} secondi")
    print("-" * 25)

def set_model_name(model_name):
    global model, script_args
    if not model_name:
        print("   🛑 ERRORE: Il nome del modello non può essere vuoto.")
        return
    try:
        # Tentativo di configurare con la chiave corrente
        temp_model = genai.GenerativeModel(model_name)
        model = temp_model
        script_args.model_name = model_name
        print(f"   ✅ Modello aggiornato a '{model_name}'. Le traduzioni future lo utilizzeranno.")
        write_to_log(f"COMANDO INTERATTIVO: Modello aggiornato a '{model_name}'.")
    except Exception as e:
        print(f"   🛑 ERRORE: Impossibile impostare il modello '{model_name}'. Errore: {e}")

def show_file_progress():
    global current_file_processed_entries, current_file_total_entries, current_file_context
    if current_file_total_entries == 0:
        print("   ℹ️  Nessun file in elaborazione o file senza entry da tradurre.")
        return

    progress = (current_file_processed_entries / current_file_total_entries) * 100
    file_type = script_args.file_type.upper()
    print(f"\n--- Stato Avanzamento File ---")
    print(f"  Tipo File: {file_type}")
    print(f"  Entry Tradotte: {current_file_processed_entries} / {current_file_total_entries}")
    print(f"  Percentuale: {progress:.2f}%")
    if current_file_context:
        print(f"  Contesto: '{current_file_context[:60].strip()}...'")
    print("-" * 30)

def reload_persistent_cache():
    global translation_cache
    if not script_args.persistent_cache:
        print("   ⚠️  La cache persistente è disabilitata. Usa --persistent-cache.")
        return
    initial_count = len(translation_cache)
    try:
        load_persistent_cache()
        final_count = len(translation_cache)
        print(f"   ✅ Cache ricaricata. Voci iniziali: {initial_count}, Voci finali: {final_count}.")
        write_to_log(f"COMANDO INTERATTIVO: Cache ricaricata. Voci iniziali: {initial_count}, Voci finali: {final_count}.")
    except Exception as e:
        print(f"   🛑 ERRORE: Impossibile ricaricare la cache: {e}")

def clear_translation_cache_func():
    global translation_cache
    count = len(translation_cache)
    if count == 0:
        print("   ℹ️  La cache in memoria è già vuota.")
        return
    translation_cache.clear()
    print(f"   ✅ Cache in memoria svuotata. Rimosse {count} voci.")
    write_to_log(f"COMANDO INTERATTIVO: Cache in memoria svuotata. Rimosse {count} voci.")
    if script_args.persistent_cache:
        print("   ℹ️  Per svuotare anche la cache su disco, usa il comando 'save cache'.")

# --- FINE FUNZIONI DI GESTIONE ---

def rotate_api_key(triggered_by_user=False, reason_override=None):
    global current_api_key_index, major_failure_count, model, blacklisted_api_key_indices
    usable_keys_count = len(available_api_keys) - len(blacklisted_api_key_indices)
    if usable_keys_count <= 1 and current_api_key_index not in blacklisted_api_key_indices:
        print("⚠️  Solo una API key utilizzabile disponibile. Impossibile ruotare.")
        return False
    if usable_keys_count == 0:
        print("🛑 ERRORE CRITICO: Tutte le API key sono state blacklisted. Impossibile proseguire.")
        write_to_log("ERRORE CRITICO: Tutte le API key sono state blacklisted.")
        return False
    previous_key_index = current_api_key_index
    initial_index = current_api_key_index
    while True:
        current_api_key_index = (current_api_key_index + 1) % len(available_api_keys)
        if current_api_key_index not in blacklisted_api_key_indices: break
        if current_api_key_index == initial_index:
            print("🛑 ERRORE CRITICO: Impossibile trovare una API key non blacklisted.")
            write_to_log("ERRORE CRITICO: Impossibile trovare una API key non blacklisted.")
            if previous_key_index not in blacklisted_api_key_indices:
                current_api_key_index = previous_key_index
            return False
    new_api_key = available_api_keys[current_api_key_index]
    trigger_reason = reason_override if reason_override else ("Comando utente." if triggered_by_user else f"Soglia fallimenti raggiunta.")
    print(f"\nℹ️  Rotazione API Key in corso (Motivo: {trigger_reason})...")
    try:
        genai.configure(api_key=new_api_key)
        # Riconfigura il modello per usare la nuova chiave
        model = genai.GenerativeModel(script_args.model_name)
        print(f"✅ Rotazione completata. Nuova API Key attiva: ...{new_api_key[-4:]}")
        major_failure_count = 0
        return True
    except Exception as e:
        print(f"❌ ERRORE: Configurazione nuova API Key fallita: {e}")
        if previous_key_index not in blacklisted_api_key_indices:
            current_api_key_index = previous_key_index
            try:
                genai.configure(api_key=available_api_keys[previous_key_index])
                model = genai.GenerativeModel(script_args.model_name)
                print("✅ API Key precedente ripristinata.")
            except Exception as e_revert:
                log_critical_error_and_exit(f"Errore nel ripristino della API Key precedente: {e_revert}.")
        else:
            log_critical_error_and_exit("Fallita rotazione API e la chiave precedente è blacklisted. Nessuna chiave utilizzabile.")
        return False

def blacklist_current_api_key():
    global current_api_key_index, blacklisted_api_key_indices
    if current_api_key_index in blacklisted_api_key_indices:
        print(f"   ℹ️  L'API Key ...{available_api_keys[current_api_key_index][-4:]} è già in blacklist.")
        return False
    blacklisted_api_key_indices.add(current_api_key_index)
    key_suffix = available_api_keys[current_api_key_index][-4:]
    print(f"   ✅ API Key ...{key_suffix} aggiunta alla blacklist.")
    write_to_log(f"COMANDO INTERATTIVO: API Key ...{key_suffix} aggiunta alla blacklist.")
    return rotate_api_key(triggered_by_user=True, reason_override="Key blacklisted")

def animazione_caricamento(stop_event):
    # MODIFICA: Mostra il progresso del file
    global current_file_processed_entries, current_file_total_entries, script_args
    for simbolo in itertools.cycle(['|', '/', '-', '\\']):
        if stop_event.is_set(): break
        
        progress_info = ""
        if current_file_total_entries > 0:
            percent = (current_file_processed_entries / current_file_total_entries) * 100
            file_type = script_args.file_type.upper() if script_args else "FILE"
            
            progress_info = f"[{file_type} {current_file_processed_entries}/{current_file_total_entries} ({percent:.2f}%)] "

        sys.stdout.write(f"\rTraduzione in corso {progress_info}{simbolo} ")
        sys.stdout.flush()
        time.sleep(0.2)
    sys.stdout.write("\r" + " " * 80 + "\r") # Pulizia

def show_stats(title="STATISTICHE DI ESECUZIONE"):
    end_time = time.time()
    total_time = end_time - start_time
    total_api_calls = sum(api_call_counts.values())
    avg_time_per_file = 0.0
    if total_files_translated > 0: avg_time_per_file = total_time / total_files_translated
    print("\n\n" + "=" * 50)
    print(f"      {title}")
    print("=" * 50)
    print(f"⏳ Tempo trascorso:             {format_time_delta(total_time)}")
    print(f"✅ File tradotti:               {total_files_translated}")
    print(f"✅ Frasi/Entry tradotte:        {total_entries_translated}")
    if total_files_translated > 0: print(f"⏱️  Tempo medio per file:        {format_time_delta(avg_time_per_file)}")
    print(f"\n➡️  Traduzioni da cache:       {cache_hit_count}")
    print(f"➡️  Chiamate API totali:       {total_api_calls}")
    print("\n--- Utilizzo Chiavi API ---")
    for i, count in api_call_counts.items():
        key_suffix = available_api_keys[i][-4:]
        status = "(ATTIVA)" if i == current_api_key_index else ""
        if i in blacklisted_api_key_indices: status = "(BLACKLISTED)"
        print(f"    - Chiave ...{key_suffix} {status}: {count} chiamate")
    print("-" * 50)

def command_input_thread_func():
    global user_command_skip_api, user_command_skip_file, script_is_paused, graceful_exit_requested, current_file_context
    print("\n\n============================================")
    print("    Alumen - Console Interattiva")
    print("============================================")
    print("ℹ️  Digita 'help' per i comandi, 'exit' o 'quit' per chiudere.")
    while True:
        try:
            prompt_indicator = "(In Pausa) " if not script_is_paused.is_set() else ""
            command_line = input(f"Alumen Interattivo {prompt_indicator}> ").strip()
            command_parts = command_line.split(maxsplit=1)
            command = command_parts[0].lower() if command_parts else ""
            
            with command_lock:
                if command == "stop":
                    graceful_exit_requested.set()
                    print("   ➡️  Comando ricevuto: lo script terminerà dopo aver completato il file attuale.")
                elif command == "log":
                    if len(command_parts) > 1 and command_parts[1].strip():
                        if script_args.enable_file_log:
                            user_message = command_parts[1].strip()
                            write_to_log(f"MESSAGGIO UTENTE: {user_message}")
                            print(f"   ✅ Messaggio '{user_message}' aggiunto al log.")
                        else:
                            print("   ⚠️  Impossibile scrivere nel log: il logging su file è disabilitato (usare --enable-file-log).")
                    else:
                        print("   ⚠️  Comando non valido. Usa 'log <il tuo messaggio>'.")
                elif command == "context":
                    if current_file_context:
                        print(f"   ℹ️  Contesto attivo per il file corrente:\n   '{current_file_context}'")
                    else:
                        print("   ℹ️  Nessun contesto generato per il file corrente (o funzione non abilitata).")
                elif command == "skip":
                    sub_command = command_parts[1].lower() if len(command_parts) > 1 else ""
                    if sub_command == "api": user_command_skip_api = True; print("   ➡️  Comando ricevuto: salto dell'API corrente in corso...")
                    elif sub_command == "file": user_command_skip_file = True; print("   ➡️  Comando ricevuto: salto del file corrente in corso...")
                    else: print("   ⚠️  Comando non valido. Usa 'skip api' o 'skip file'.")
                
                # MODIFICA: Aggiunta stampa automatica delle statistiche su 'pause'
                elif command == "pause": 
                    script_is_paused.clear()
                    
                    print("\n" + "=" * 50)
                    print("   ⏳ SCRIPT IN PAUSA. Digita 'resume' per continuare.")
                    print("=" * 50)
                    
                    show_stats(title="STATISTICHE AL MOMENTO DELLA PAUSA")
                    show_rpm_stats(title="STATISTICHE RPM")
                    
                    print("\n--- Contesto File Corrente ---")
                    if current_file_context:
                        print(f"'{current_file_context}'")
                    else:
                        print("Nessun contesto generato per il file corrente (o funzione non abilitata).")
                    print("-" * 30)

                    # Ristampa del prompt per non far sembrare che il programma sia bloccato
                    sys.stdout.write("Alumen Interattivo (In Pausa) > ")
                    sys.stdout.flush()

                elif command == "resume": script_is_paused.set(); print("   ▶️  Script in esecuzione...")
                elif command == "stats": show_stats("STATISTICHE ATTUALI")
                elif command == "add":
                    parts = command_parts[1].split(maxsplit=1) if len(command_parts) > 1 else []
                    if len(parts) == 2 and parts[0].lower() == 'api': add_api_key(parts[1].strip())
                    else: print("   ⚠️  Comando non valido. Usa 'add api <tua_chiave_api>'.")
                elif command == "exhausted": blacklist_current_api_key()
                
                # --- NUOVI COMANDI ---

                # Gestione API Avanzata
                elif command == "list" and len(command_parts) > 1 and command_parts[1].lower() == 'keys': list_api_keys()
                elif command == "remove":
                    parts = command_parts[1].split(maxsplit=1) if len(command_parts) > 1 else []
                    if len(parts) == 2 and parts[0].lower() == 'key': remove_api_key(parts[1].strip())
                    else: print("   ⚠️  Comando non valido. Usa 'remove key <indice>'.")
                elif command == "blacklist":
                    if len(command_parts) > 1: blacklist_specific_api_key(command_parts[1].strip())
                    else: print("   ⚠️  Comando non valido. Usa 'blacklist <indice>'.")
                elif command == "clear" and len(command_parts) > 1 and command_parts[1].lower() == 'blacklist': clear_blacklisted_keys()
                
                # Performance
                elif command == "set":
                    parts = command_parts[1].split(maxsplit=1) if len(command_parts) > 1 else []
                    if len(parts) == 2:
                        if parts[0].lower() == 'rpm': set_rpm_limit_func(parts[1].strip())
                        elif parts[0].lower() == 'model': set_model_name(parts[1].strip())
                        else: print("   ⚠️  Comando non valido. Usa 'set rpm <numero>' o 'set model <nome_modello>'.")
                    else: print("   ⚠️  Comando non valido. Usa 'set rpm <numero>' o 'set model <nome_modello>'.")
                
                # Informazioni e Debug - show key rimosso
                elif command == "show":
                    sub_command = command_parts[1].lower() if len(command_parts) > 1 else ""
                    if sub_command == "rpm": show_rpm_stats()
                    elif sub_command == "file_progress": show_file_progress()
                    else: print("   ⚠️  Comando non valido. Usa 'show rpm' o 'show file_progress'.")
                elif command == "reload" and len(command_parts) > 1 and command_parts[1].lower() == 'cache': reload_persistent_cache()
                elif command == "clear" and len(command_parts) > 1 and command_parts[1].lower() == 'cache': clear_translation_cache_func()

                # Fine Nuovi Comandi

                elif command == "save" or (command == "salva" and len(command_parts) > 1 and command_parts[1].lower() == "cache"):
                    if script_args.persistent_cache:
                        print("   ➡️  Comando ricevuto: salvataggio della cache in corso...")
                        save_persistent_cache()
                    else: print(f"   ⚠️  Attenzione: La cache persistente è disabilitata. Usa --persistent-cache.")
                elif command == "help":
                    print("\n--- Comandi Disponibili ---")
                    print("  Controllo Esecuzione:")
                    print("    stop                - Termina lo script in modo sicuro dopo il file attuale, salvando tutto.")
                    print("    pause               - Mette in pausa l'elaborazione (stampa stats/info automaticamente).")
                    print("    resume              - Riprende l'elaborazione.")
                    print("  Salto e Rotazione:")
                    print("    skip file           - Salta il file corrente e passa al successivo.")
                    print("    skip api            - Salta l'API key corrente e passa alla successiva.")
                    print("    exhausted           - Mette in blacklist l'API key corrente (es. quota finita) e ruota.")
                    print("  Gestione API Avanzata:")
                    print("    add api <chiave>    - Aggiunge una nuova chiave API durante l'esecuzione.")
                    print("    list keys           - Elenca tutte le API key, il loro stato e l'utilizzo (inclusa la chiave attiva).")
                    print("    remove key <indice> - Rimuove una chiave API per indice.")
                    print("    blacklist <indice>  - Mette in blacklist una chiave per indice, forzando la rotazione se attiva.")
                    print("    clear blacklist     - Rende nuovamente utilizzabili tutte le chiavi in blacklist.")
                    print("  Performance:")
                    print("    set rpm <numero>    - Imposta il limite di Richieste Per Minuto (RPM) al volo (0 per disabilitare).")
                    print("    show rpm            - Mostra il limite e l'utilizzo RPM attuale.")
                    print("    set model <nome>    - Cambia il modello Gemini per le traduzioni future (es. 'gemini-1.5-flash').")
                    print("  Informazioni e Utilità:")
                    print("    stats               - Mostra le statistiche di esecuzione (tempo, file, chiamate API).")
                    print("    context             - Visualizza il contesto generato per il file corrente.")
                    print("    show file_progress  - Mostra lo stato di avanzamento della traduzione all'interno del file corrente.")
                    print("    log <messaggio>     - Scrive un messaggio personalizzato nel file di log.")
                    print("    save cache          - Salva immediatamente la cache su file.")
                    print("    reload cache        - Ricarica la cache dal file (se è stata modificata esternamente).")
                    print("    clear cache         - Svuota la cache di traduzione in memoria.")
                    print("  Uscita:")
                    print("    exit / quit         - Chiude solo questa console interattiva.\n")
                elif command in ["exit", "quit"]: print("\nINFO: Chiusura console interattiva."); break
                elif command: print(f"   ❓ Comando '{command}' non riconosciuto. Digita 'help' per la lista dei comandi.")
        except (EOFError, KeyboardInterrupt): print("\nINFO: Chiusura console interattiva."); break
        except Exception as e: print(f"🛑 Errore nel thread input comandi: {e}"); break

def check_and_wait_if_paused(file_context=""):
    global script_is_paused
    if script_args.interactive and not script_is_paused.is_set():
        # Pulizia della riga dell'animazione/progresso prima di entrare in pausa
        sys.stdout.write("\r" + " " * 80 + "\r")
        script_is_paused.wait()
        print(f"\n▶️  SCRIPT RIPRESO (Lavorando su: {file_context}).\n")

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
            print(f"    ⏳ Limite RPM ({rpm_limit}/min) raggiunto. Attesa di {wait_duration:.1f} secondi...")
            time.sleep(wait_duration)

def determine_if_translatable(text_value):
    if not isinstance(text_value, str): return False
    text_value_stripped = text_value.strip()
    if not text_value_stripped or text_value_stripped.isdigit() or re.match(r'^[\W_]+$', text_value_stripped) or "\\u" in text_value_stripped:
        return False
    if '_' in text_value_stripped and ' ' not in text_value_stripped:
        return False
    return True

def handle_api_error(e, context_for_log, active_key_display, attempt_num):
    error_message_str = str(e)
    print(f"    ⚠️  Tentativo {attempt_num + 1}/{MAX_RETRIES_PER_API_CALL} (Chiave ...{active_key_display}) fallito. Errore API: {error_message_str}")
    write_to_log(f"ERRORE API: {context_for_log}, Tentativo {attempt_num + 1}, Key ...{active_key_display}. Errore: {error_message_str}")
    retry_delay_seconds = DEFAULT_API_ERROR_RETRY_SECONDS
    match = re.search(r"retry_delay\s*{\s*seconds:\s*(\d+)\s*}", error_message_str, re.IGNORECASE)
    if match: retry_delay_seconds = int(match.group(1)) + 1
    return retry_delay_seconds

def load_persistent_cache():
    global translation_cache, script_args, last_cache_save_time
    if not script_args.persistent_cache: return
    try:
        if os.path.exists(CACHE_FILE_NAME):
            with open(CACHE_FILE_NAME, 'r', encoding='utf-8') as f:
                translation_cache = json.load(f)
            print(f"✅ Cache persistente caricata da '{CACHE_FILE_NAME}' ({len(translation_cache)} voci).")
            last_cache_save_time = time.time()
        else:
            print(f"ℹ️  File di cache '{CACHE_FILE_NAME}' non trovato. Verrà creato un nuovo file.")
            last_cache_save_time = 0.0
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  Attenzione: Impossibile caricare la cache da '{CACHE_FILE_NAME}': {e}. Verrà ricreata.")
        translation_cache = {}
        last_cache_save_time = 0.0

def save_persistent_cache():
    global translation_cache, script_args, last_cache_save_time
    if not script_args.persistent_cache or not translation_cache:
        if script_args.persistent_cache and not translation_cache:
            print("\nℹ️  Salvataggio cache ignorato: la cache è vuota.")
        return
    try:
        with open(CACHE_FILE_NAME, 'w', encoding='utf-8') as f:
            json.dump(translation_cache, f, ensure_ascii=False, indent=4)
        print(f"\n✅ Cache ({len(translation_cache)} voci) salvata correttamente in '{CACHE_FILE_NAME}'.")
        last_cache_save_time = time.time()
    except IOError as e:
        print(f"\n🛑 ERRORE: Impossibile salvare la cache in '{CACHE_FILE_NAME}': {e}")

def check_and_save_cache():
    global last_cache_save_time, script_args
    if not script_args.persistent_cache: return
    current_time = time.time()
    if last_cache_save_time == 0.0 or current_time - last_cache_save_time >= 600:
        print("\nℹ️  Salvataggio periodico della cache in corso...")
        write_to_log("Salvataggio cache periodico (10 minuti) attivato.")
        save_persistent_cache()

def generate_file_context(sample_text, file_name, args):
    global major_failure_count, model, translation_cache, cache_hit_count, api_call_counts
    context_cache_key = f"CONTEXT_FILE::{file_name}::{args.game_name}::{args.prompt_context}"
    if args.full_context_sample: context_cache_key += "::FULL_SAMPLE"
    if context_cache_key in translation_cache:
        print(f"  ✅ Contesto per '{file_name}' trovato nella cache.")
        cache_hit_count += 1
        return translation_cache[context_cache_key]
    print(f"  ➡️  Richiesta API per generare il contesto del file '{file_name}'...")
    context_for_log = f"Generazione Contesto per File: {file_name}"
    prompt = f"Analizza il seguente campione di testo, che proviene da un file di traduzione per il gioco '{args.game_name}'. Il tuo compito è determinare, in non più di due frasi concise, l'argomento principale, il contesto generale o l'ambientazione più probabile di questo file. Questo contesto verrà utilizzato per migliorare la qualità delle traduzioni successive. Rispondi solo con il contesto generato.\nCampione di testo:\n---\n{sample_text}\n---\nContesto generato:"
    while True:
        with command_lock:
            global user_command_skip_file
            if user_command_skip_file: raise KeyboardInterrupt
        if args.interactive: check_and_wait_if_paused(context_for_log)
        active_key_short = available_api_keys[current_api_key_index][-4:]
        rotation_successful = False
        for attempt_idx in range(MAX_RETRIES_PER_API_CALL):
            try:
                wait_for_rpm_limit()
                time.sleep(BASE_API_CALL_INTERVAL_SECONDS)
                response_obj = model.generate_content(prompt)
                if not response_obj or not hasattr(response_obj, 'text'): raise ValueError("Risposta dall'API non valida o vuota.")
                file_context = response_obj.text.strip()
                api_call_counts[current_api_key_index] += 1
                if args.wrap_at and args.wrap_at > 0: file_context = textwrap.fill(file_context, width=args.wrap_at, newline=args.newline_char, replace_whitespace=False)
                translation_cache[context_cache_key] = file_context
                print(f"  ✅ Contesto generato per il file: '{file_context}'")
                write_to_log(f"Contesto generato per {file_name}: {file_context}")
                major_failure_count = 0
                return file_context
            except Exception as api_exc:
                if args.rotate_on_limit_or_error:
                    if rotate_api_key(reason_override=f"Errore API durante generazione contesto"):
                        rotation_successful = True
                        break
                retry_delay = handle_api_error(api_exc, context_for_log, active_key_short, attempt_idx)
                if attempt_idx < MAX_RETRIES_PER_API_CALL - 1: time.sleep(retry_delay)
        if rotation_successful: continue
        major_failure_count += 1
        print(f"    ❌ Fallimento definitivo generazione contesto con Chiave ...{active_key_short}. Fallimenti consecutivi: {major_failure_count}/{MAX_MAJOR_FAILURES_THRESHOLD}")
        if major_failure_count >= MAX_MAJOR_FAILURES_THRESHOLD:
            if not rotate_api_key():
                print("    ⚠️  ATTENZIONE: Rotazione API fallita. Contesto file non generabile. Proseguo senza contesto specifico.")
                write_to_log(f"ERRORE CRITICO: Contesto file non generabile per {file_name}. Proseguo senza contesto specifico.")
                return None
        else: time.sleep(15)
    return None

def get_translation_from_api(text_to_translate, context_for_log, args, dynamic_context=None):
    global major_failure_count, user_command_skip_api, model, translation_cache, cache_hit_count, api_call_counts, BLACKLIST_TERMS
    if text_to_translate.strip() in BLACKLIST_TERMS:
        print(f"    - 🛑 BLACKLIST HIT: Il testo '{text_to_translate}' è in blacklist. Salto traduzione.")
        write_to_log(f"BLACKLIST HIT: Saltata traduzione per '{text_to_translate}' nel contesto: {context_for_log}")
        return text_to_translate
    if not determine_if_translatable(text_to_translate): return text_to_translate
    
    # FIX: Ripristina la chiave della cache per non includere args.model_name
    cache_key_tuple = (text_to_translate, args.source_lang, args.target_lang, args.game_name, args.prompt_context)
    cache_key = json.dumps(cache_key_tuple, ensure_ascii=False)
    
    if cache_key in translation_cache:
        print(f"    ✅ Cache: Trovata traduzione per '{text_to_translate[:50].strip()}...'.")
        write_to_log(f"CACHE HIT: Usata traduzione in cache per il contesto: {context_for_log}")
        cache_hit_count += 1
        return translation_cache[cache_key]
    while True:
        if args.interactive: check_and_wait_if_paused(context_for_log)
        with command_lock:
            if user_command_skip_api:
                rotate_api_key(triggered_by_user=True)
                user_command_skip_api = False
        active_key_short = available_api_keys[current_api_key_index][-4:]
        rotation_successful = False
        for attempt_idx in range(MAX_RETRIES_PER_API_CALL):
            try:
                wait_for_rpm_limit()
                if args.custom_prompt:
                    if "{text_to_translate}" not in args.custom_prompt:
                        print(f"    - ❌ ERRORE: Il prompt personalizzato non include '{{text_to_translate}}'. Salto.")
                        return text_to_translate
                    prompt_text = args.custom_prompt.format(text_to_translate=text_to_translate)
                else:
                    blacklist_str = ", ".join(BLACKLIST_TERMS)
                    prompt_base = f"Traduci il seguente testo da {args.source_lang} a {args.target_lang}, tenendo conto del contesto del gioco '{args.game_name}' e utilizzando uno stile che includa eventuali slang o espressioni colloquiali appropriate al contesto. ISTRUZIONE CRITICA: preserva esattamente tutti gli a capo originali (come `\\n` o `\\r\\n`) presenti nel testo. Inoltre, preserva eventuali tag HTML, placeholder (come [p], {{player_name}}), o codici speciali (come ad esempio stringhe con codici tipo: talk_id_player). Assicurati di mantenere identici i seguenti termini che NON devono essere tradotti, anche se appaiono in frasi più lunghe: {blacklist_str}. In caso di dubbi sul genere (Femminile o Maschile), utilizza il maschile."
                    if args.prompt_context: prompt_base += f"\nIstruzione aggiuntiva: {args.prompt_context}."
                    if dynamic_context: prompt_base += f"\nContesto aggiuntivo per questa traduzione: '{dynamic_context}'."
                    prompt_base += "\nRispondi solo con la traduzione diretta."
                    prompt_text = f"{prompt_base}\nTesto originale:\n{text_to_translate}\n\nTraduzione in {args.target_lang}:"
                time.sleep(BASE_API_CALL_INTERVAL_SECONDS)
                # Usa model, che è la variabile globale aggiornabile
                response_obj = model.generate_content(prompt_text)
                if not response_obj or not hasattr(response_obj, 'text'): raise ValueError("Risposta dall'API non valida o vuota.")
                translated_text = response_obj.text.strip()
                api_call_counts[current_api_key_index] += 1
                if args.wrap_at and args.wrap_at > 0: translated_text = textwrap.fill(translated_text, width=args.wrap_at, newline=args.newline_char, replace_whitespace=False)
                major_failure_count = 0
                translation_cache[cache_key] = translated_text
                write_to_log(f"CACHE MISS: Nuova traduzione salvata in cache per il contesto: {context_for_log}")
                return translated_text
            except (google.api_core.exceptions.ResourceExhausted, google.api_core.exceptions.DeadlineExceeded) as e:
                print(f"    ⚠️  Errore di Quota/Timeout con Chiave ...{active_key_short}: {e}")
                write_to_log(f"ERRORE QUOTA/TIMEOUT: {context_for_log}, Key ...{active_key_short}. Errore: {e}")
                if args.rotate_on_limit_or_error:
                    if rotate_api_key(reason_override="Quota esaurita o Timeout"):
                        rotation_successful = True
                        break
                time.sleep(15)
            except google.api_core.exceptions.PermissionDenied as e:
                print(f"    🛑 Chiave API ...{active_key_short} non valida o disabilitata. Verrà messa in blacklist.")
                write_to_log(f"ERRORE PERMESSO: {context_for_log}, Key ...{active_key_short}. Errore: {e}")
                blacklist_current_api_key()
                rotation_successful = True
                break
            except Exception as api_exc:
                if args.rotate_on_limit_or_error:
                    if rotate_api_key(reason_override=f"Errore API"):
                        rotation_successful = True
                        break
                retry_delay = handle_api_error(api_exc, context_for_log, active_key_short, attempt_idx)
                if attempt_idx < MAX_RETRIES_PER_API_CALL - 1: time.sleep(retry_delay)
        if rotation_successful: continue
        major_failure_count += 1
        print(f"    ❌ Fallimento definitivo con Chiave ...{active_key_short}. Fallimenti consecutivi: {major_failure_count}/{MAX_MAJOR_FAILURES_THRESHOLD}")
        if major_failure_count >= MAX_MAJOR_FAILURES_THRESHOLD:
            if not rotate_api_key():
                print("    ⚠️  Rotazione API fallita. Pausa di 60 secondi prima di un nuovo tentativo.")
                time.sleep(60)
        else: time.sleep(15)

def _extract_json_sample_texts(obj, keys_to_translate, sample_list, path="", match_full=False, limit=FILE_CONTEXT_SAMPLE_SIZE):
    if limit is not None and len(sample_list) >= limit: return
    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{path}.{key}" if path else key
            is_match = (current_path in keys_to_translate) if match_full else (key in keys_to_translate)
            if is_match and determine_if_translatable(value):
                sample_list.append(str(value))
                if limit is not None and len(sample_list) >= limit: return
            _extract_json_sample_texts(value, keys_to_translate, sample_list, current_path, match_full, limit)
    elif isinstance(obj, list):
        for item in obj: _extract_json_sample_texts(item, keys_to_translate, sample_list, path, match_full, limit)

def should_translate_msgctxt(context_string):
    if not determine_if_translatable(context_string) or '_' in context_string: return False
    if '\t' in context_string: return False
    if re.search(r'<[a-zA-Z/][^>]*>', context_string): return False
    stripped_context = context_string.strip()
    if ' ' not in stripped_context:
        has_digits = any(char.isdigit() for char in stripped_context)
        is_mixed_case = not stripped_context.islower() and not stripped_context.isupper()
        if has_digits or is_mixed_case: return False
    return False

def traduci_testo_po(input_file, output_file, args):
    global current_file_context, total_entries_translated, user_command_skip_file, current_file_total_entries, current_file_processed_entries
    current_file_context = None
    file_basename = os.path.basename(input_file)
    print(f"\n▶️  Inizio elaborazione file PO: '{file_basename}'")
    try: po_file = polib.pofile(input_file, encoding=args.encoding)
    except Exception as e: log_critical_error_and_exit(f"Impossibile leggere o parsare il file PO '{input_file}': {e}")
    
    texts_to_translate_count = sum(1 for entry in po_file if determine_if_translatable(entry.msgid))
    current_file_total_entries = texts_to_translate_count
    
    processed_count_local = 0

    try:
        if args.enable_file_context:
            sample_limit = None if args.full_context_sample else FILE_CONTEXT_SAMPLE_SIZE
            sample_texts = [entry.msgid for entry in po_file if determine_if_translatable(entry.msgid)][:sample_limit]
            if sample_texts:
                print(f"  ℹ️  Analisi di {len(sample_texts)} frasi per generare il contesto del file...")
                file_context = generate_file_context("\n".join(sample_texts), file_basename, args)
                current_file_context = file_context
        
        print(f"ℹ️  Trovate {current_file_total_entries} entry da tradurre.")
        for entry in po_file:
            with command_lock:
                if user_command_skip_file: raise KeyboardInterrupt
            
            original_context = entry.msgctxt
            context_for_prompt, context_is_translatable_prose = None, should_translate_msgctxt(original_context)
            
            if context_is_translatable_prose:
                print(f"\n  Traduzione contesto (Riga {entry.linenum}):")
                print(f"    - Originale: '{original_context}'")
                translated_context = get_translation_from_api(original_context, f"PO '{file_basename}', Ctxt, Riga: {entry.linenum}", args)
                entry.msgctxt = translated_context
                context_for_prompt = translated_context
                total_entries_translated += 1
                print(f"    - Tradotto:  '{entry.msgctxt}'")
            elif original_context: context_for_prompt = original_context
            
            if entry.msgid and determine_if_translatable(entry.msgid):
                processed_count_local += 1
                current_file_processed_entries = processed_count_local
                total_entries_translated += 1
                print(f"\n  Traduzione {current_file_processed_entries}/{current_file_total_entries} (Riga {entry.linenum}):")
                
                final_dynamic_context = " - ".join(filter(None, [f"Contesto Generale File: {file_context}" if file_context else None, f"Contesto Specifico Entry: {context_for_prompt}" if context_for_prompt else None]))
                if final_dynamic_context: print(f"    ℹ️  Utilizzo del contesto per migliorare la traduzione.")
                
                original_text = entry.msgid
                print(f"    - Originale: '{original_text[:80].replace(chr(10), ' ')}...'")
                translated_text = get_translation_from_api(original_text, f"PO '{file_basename}', msgid, Riga: {entry.linenum}", args, dynamic_context=final_dynamic_context)
                entry.msgstr = translated_text
                print(f"    - Tradotto:  '{translated_text[:80].replace(chr(10), ' ')}...'")
            elif entry.msgid: entry.msgstr = entry.msgid

    except KeyboardInterrupt:
        with command_lock: is_skip_command = user_command_skip_file
        if is_skip_command:
            print(f"\n➡️  Comando 'skip file' ricevuto. Salvataggio dei progressi per '{file_basename}'...")
            write_to_log(f"SKIP FILE: Salvataggio progressi parziali per PO '{file_basename}'")
        else:
            print(f"\n🛑 Interruzione da tastiera. Salvataggio dei progressi per '{file_basename}'...")
            write_to_log(f"INTERRUZIONE UTENTE: Salvataggio progressi parziali per PO '{file_basename}'")
            raise
    finally:
        try:
            po_file.save(output_file)
            print(f"✅ File parziale/completo salvato in: '{output_file}'")
            check_and_save_cache()
        except Exception as e: log_critical_error_and_exit(f"Impossibile scrivere il file di output '{output_file}': {e}")
        with command_lock:
            if user_command_skip_file: user_command_skip_file = False
    print(f"✅ Completata elaborazione di '{file_basename}'.")

def traduci_testo_json(input_file, output_file, args):
    global current_file_context, total_entries_translated, user_command_skip_file, current_file_total_entries, current_file_processed_entries
    current_file_context = None
    file_basename = os.path.basename(input_file)
    print(f"\n▶️  Inizio elaborazione file JSON: '{file_basename}'")
    try:
        with open(input_file, 'r', encoding=args.encoding) as f: data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e: log_critical_error_and_exit(f"Impossibile leggere o parsare il file JSON '{input_file}': {e}")
    
    keys_to_translate = {k.strip() for k in args.json_keys.split(',')}
    translated_texts_for_only_output = []
    
    texts_to_translate_count = 0
    def _count(obj, path=""):
        nonlocal texts_to_translate_count
        if isinstance(obj, dict):
            for k, v in obj.items():
                p = f"{path}.{k}" if path else k
                if ((p in keys_to_translate) if args.match_full_json_path else (k in keys_to_translate)) and determine_if_translatable(v): texts_to_translate_count += 1
                _count(v, p)
        elif isinstance(obj, list):
            for i, item in enumerate(obj): _count(item, f"{path}[{i}]")

    processed_count_local = 0
    def _translate(obj, path=""):
        nonlocal processed_count_local
        global total_entries_translated, current_file_processed_entries
        if isinstance(obj, dict):
            for key, value in list(obj.items()):
                with command_lock:
                    if user_command_skip_file: raise KeyboardInterrupt
                current_path = f"{path}.{key}" if path else key
                if ((current_path in keys_to_translate) if args.match_full_json_path else (key in keys_to_translate)) and determine_if_translatable(value):
                    processed_count_local += 1
                    current_file_processed_entries = processed_count_local
                    total_entries_translated += 1
                    
                    print(f"\n  Traduzione {current_file_processed_entries}/{current_file_total_entries} (Chiave: {current_path}):")
                    if current_file_context: print(f"    ℹ️  Utilizzo del contesto per migliorare la traduzione.")
                    print(f"    - Originale: '{str(value)[:80]}...'")
                    translated_value = get_translation_from_api(value, f"JSON '{file_basename}', Chiave: '{current_path}'", args, dynamic_context=current_file_context)
                    obj[key] = translated_value
                    print(f"    - Tradotto:  '{str(translated_value)[:80]}...'")
                    if args.translation_only_output: translated_texts_for_only_output.append(translated_value)
                _translate(value, current_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj): _translate(item, f"{path}[{i}]")
    
    try:
        if args.enable_file_context:
            sample_texts = []
            _extract_json_sample_texts(data, keys_to_translate, sample_texts, match_full=args.match_full_json_path, limit=None if args.full_context_sample else FILE_CONTEXT_SAMPLE_SIZE)
            if sample_texts:
                print(f"  ℹ️  Analisi di {len(sample_texts)} voci per generare il contesto del file...")
                file_context = generate_file_context("\n".join(sample_texts), file_basename, args)
                current_file_context = file_context
        
        _count(data)
        current_file_total_entries = texts_to_translate_count
        print(f"ℹ️  Trovate {current_file_total_entries} voci da tradurre.")
        _translate(data)

    except KeyboardInterrupt:
        with command_lock: is_skip_command = user_command_skip_file
        if is_skip_command:
            print(f"\n➡️  Comando 'skip file' ricevuto. Salvataggio dei progressi per '{file_basename}'...")
            write_to_log(f"SKIP FILE: Salvataggio progressi parziali per JSON '{file_basename}'")
        else:
            print(f"\n🛑 Interruzione da tastiera. Salvataggio dei progressi per '{file_basename}'...")
            write_to_log(f"INTERRUZIONE UTENTE: Salvataggio progressi parziali per JSON '{file_basename}'")
            raise
    finally:
        try:
            with open(output_file, 'w', encoding=args.encoding) as f:
                if args.translation_only_output: f.write("\n".join(translated_texts_for_only_output) + "\n")
                else: json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"✅ File parziale/completo salvato in: '{output_file}'")
            check_and_save_cache()
        except Exception as e: log_critical_error_and_exit(f"Impossibile scrivere il file di output '{output_file}': {e}")
        with command_lock:
            if user_command_skip_file: user_command_skip_file = False
    print(f"✅ Completata elaborazione di '{file_basename}'.")

def traduci_testo_csv(input_file, output_file, args):
    global current_file_context, total_entries_translated, user_command_skip_file, current_file_total_entries, current_file_processed_entries
    current_file_context = None
    file_basename = os.path.basename(input_file)
    print(f"\n▶️  Inizio elaborazione file CSV: '{file_basename}'")
    try:
        with open(input_file, 'r', encoding=args.encoding, newline='') as infile: rows = list(csv.reader(infile, delimiter=args.delimiter))
    except Exception as e: log_critical_error_and_exit(f"Impossibile leggere il file CSV '{input_file}': {e}")
    
    header = rows[0] if rows else None
    data_rows = rows[1:] if header else rows
    output_rows = [row[:] for row in rows]
    
    if args.resume and os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding=args.encoding, newline='') as resumed_file:
                resumed_rows = list(csv.reader(resumed_file, delimiter=args.delimiter))
                if len(resumed_rows) == len(output_rows):
                    output_rows = resumed_rows
                    print(f"ℹ️  Resume mode: Caricate {len(output_rows)} righe da '{output_file}'.")
        except Exception as e: print(f"⚠️  Attenzione: Impossibile leggere il file di resume '{output_file}': {e}. Verrà sovrascritto.")
    
    processed_count_local = 0
    texts_to_translate_count = 0
    translated_texts_for_only_output = []
    
    try:
        if args.enable_file_context:
            sample_limit = None if args.full_context_sample else FILE_CONTEXT_SAMPLE_SIZE
            sample_texts = [row[args.translate_col] for row in data_rows if len(row) > args.translate_col and determine_if_translatable(row[args.translate_col])][:sample_limit]
            if sample_texts:
                print(f"  ℹ️  Analisi di {len(sample_texts)} righe per generare il contesto del file...")
                file_context = generate_file_context("\n".join(sample_texts), file_basename, args)
                current_file_context = file_context
        
        texts_to_translate_count = sum(1 for i, row in enumerate(data_rows) if len(row) > args.translate_col and determine_if_translatable(row[args.translate_col]))
        current_file_total_entries = texts_to_translate_count
        print(f"ℹ️  Trovate {current_file_total_entries} righe da tradurre.")
        
        output_data_rows = output_rows[1:] if header else output_rows
        
        for i, row in enumerate(output_data_rows):
            display_row_num = i + (2 if header else 1)
            with command_lock:
                if user_command_skip_file: raise KeyboardInterrupt
            
            is_already_translated = args.resume and len(row) > args.output_col and row[args.output_col].strip() and (args.output_col != args.translate_col or row[args.output_col] != data_rows[i][args.translate_col])
            
            if is_already_translated:
                if len(data_rows[i]) > args.translate_col and determine_if_translatable(data_rows[i][args.translate_col]):
                    texts_to_translate_count -= 1
                    processed_count_local += 1
                    current_file_processed_entries = processed_count_local
                print(f"  - Riga {display_row_num} già tradotta (Resume Mode). Saltata.")
                if args.translation_only_output and len(row) > args.output_col: translated_texts_for_only_output.append(row[args.output_col])
                continue
            
            if len(row) > args.translate_col and determine_if_translatable(row[args.translate_col]):
                processed_count_local += 1
                current_file_processed_entries = processed_count_local
                total_entries_translated += 1
                original_text = row[args.translate_col]
                
                print(f"\n  Traduzione {current_file_processed_entries}/{current_file_total_entries} (Riga {display_row_num}):")
                if file_context: print(f"    ℹ️  Utilizzo del contesto per migliorare la traduzione.")
                print(f"    - Originale: '{original_text[:80]}...'")
                
                translated_text = get_translation_from_api(original_text, f"CSV '{file_basename}', Riga: {display_row_num}", args, dynamic_context=file_context)
                
                while len(row) <= args.output_col: row.append('')
                row[args.output_col] = translated_text
                
                print(f"    - Tradotto:  '{translated_text[:80]}...'")
                if args.translation_only_output: translated_texts_for_only_output.append(translated_text)

    except KeyboardInterrupt:
        with command_lock: is_skip_command = user_command_skip_file
        if is_skip_command:
            print(f"\n➡️  Comando 'skip file' ricevuto. Salvataggio dei progressi per '{file_basename}'...")
            write_to_log(f"SKIP FILE: Salvataggio progressi parziali per CSV '{file_basename}'")
        else:
            print(f"\n🛑 Interruzione da tastiera. Salvataggio dei progressi per '{file_basename}'...")
            write_to_log(f"INTERRUZIONE UTENTE: Salvataggio progressi parziali per CSV '{file_basename}'")
            raise
    finally:
        try:
            with open(output_file, 'w', encoding=args.encoding, newline='') as outfile:
                if args.translation_only_output:
                    final_texts = translated_texts_for_only_output
                    outfile.write("\n".join(final_texts) + "\n")
                else:
                    writer = csv.writer(outfile, delimiter=args.delimiter, quoting=csv.QUOTE_MINIMAL)
                    writer.writerows(output_rows)
            print(f"✅ File parziale/completo salvato in: '{output_file}'")
            check_and_save_cache()
        except Exception as e: log_critical_error_and_exit(f"Impossibile scrivere il file di output '{output_file}': {e}")
        with command_lock:
            if user_command_skip_file: user_command_skip_file = False
    print(f"✅ Completata elaborazione di '{file_basename}'.")

def process_files_recursively(args):
    global user_command_skip_file, total_files_translated, current_file_total_entries, current_file_processed_entries
    base_input_dir = os.path.abspath(args.input)
    base_output_dir = f"{base_input_dir}_tradotto" if os.path.basename(base_input_dir) != "input" else os.path.join(os.path.dirname(base_input_dir) or '.', "tradotto")
    print(f"\nInizio scansione della cartella '{base_input_dir}' per i file *.{args.file_type}...")
    print(f"I file tradotti verranno salvati in: '{base_output_dir}'")
    os.makedirs(base_output_dir, exist_ok=True)
    file_paths_to_process = [os.path.join(r, f) for r, _, files in os.walk(base_input_dir) for f in files if f.endswith(f'.{args.file_type}')]
    total_files_found = len(file_paths_to_process)
    print(f"✅ Scansione completata. Trovati {total_files_found} file da elaborare.")
    for file_index, input_path in enumerate(file_paths_to_process):
        if graceful_exit_requested.is_set():
            print("\n🛑 Uscita graduale richiesta dall'utente. Interruzione del processo di elaborazione dei file.")
            break
        with command_lock:
            if user_command_skip_file:
                print(f"➡️  Comando 'skip file' rilevato. Saltando il file: '{os.path.basename(input_path)}'.")
                continue
        
        # Reset dei contatori per il nuovo file
        current_file_total_entries = 0
        current_file_processed_entries = 0

        if script_args.interactive: check_and_wait_if_paused(f"Inizio file: {os.path.basename(input_path)}")
        print(f"\n--- [{file_index + 1}/{total_files_found}] ---")
        relative_path_dir = os.path.relpath(os.path.dirname(input_path), base_input_dir)
        current_output_dir = os.path.join(base_output_dir, relative_path_dir) if relative_path_dir != '.' else base_output_dir
        os.makedirs(current_output_dir, exist_ok=True)
        filename = os.path.basename(input_path)
        output_filename = f"{os.path.splitext(filename)[0]}_trads.txt" if args.translation_only_output else filename
        output_path = os.path.join(current_output_dir, output_filename)
        if args.resume and os.path.exists(output_path) and args.file_type != 'csv':
             print(f"⚠️  Attenzione: La modalità Resume è attiva ma non è completamente supportata per i file '{args.file_type}'. Il file '{output_path}' verrà sovrascritto.")
        try:
            if args.file_type == 'csv': traduci_testo_csv(input_path, output_path, args)
            elif args.file_type == 'json': traduci_testo_json(input_path, output_path, args)
            elif args.file_type == 'po': traduci_testo_po(input_path, output_path, args)
            total_files_translated += 1
            show_stats(title="STATISTICHE DI AVANZAMENTO")
        except Exception as e:
            error_msg = f"Errore irreversibile durante l'elaborazione del file '{filename}': {e}"
            print(f"🛑 {error_msg}")
            write_to_log(f"ERRORE CRITICO FILE: {error_msg}. Il file verrà saltato.")

if __name__ == "__main__":
    print(ALUMEN_ASCII_ART)
    print("Benvenuto in Alumen, traduttore automatico potenziato da Gemini.\n")
    args_parsed_main = get_script_args_updated()
    if not os.path.isdir(args_parsed_main.input):
        log_critical_error_and_exit(f"La cartella di input specificata '{args_parsed_main.input}' non esiste o non è una cartella.")
    if args_parsed_main.file_type == 'json' and not args_parsed_main.json_keys:
        log_critical_error_and_exit("Per --file-type 'json', è obbligatorio specificare --json-keys.")
    script_is_paused.set()
    start_time = time.time()
    if args_parsed_main.enable_file_log: setup_log_file()
    initialize_api_keys_and_model()
    load_persistent_cache()
    cmd_thread = None
    if args_parsed_main.interactive:
        cmd_thread = threading.Thread(target=command_input_thread_func, daemon=True)
        cmd_thread.start()
    main_stop_event = Event()
    loader_thread = None
    if not args_parsed_main.oneThread:
        # Se oneThread è disabilitato (default), avvia il thread per l'animazione/progresso
        loader_thread = Thread(target=animazione_caricamento, args=(main_stop_event,))
        loader_thread.start()
    try:
        process_files_recursively(args_parsed_main)
    except KeyboardInterrupt:
        print("\n\n🛑 Interruzione da tastiera (Ctrl+C) rilevata. Chiusura in corso...")
    finally:
        main_stop_event.set()
        if loader_thread and loader_thread.is_alive(): loader_thread.join()
        if cmd_thread and cmd_thread.is_alive():
            print("\nPer terminare, digita 'exit' o 'quit' nella console interattiva.")
        save_persistent_cache()
        show_stats(title="STATISTICHE FINALI DI ESECUZIONE")
        write_to_log(f"--- FINE Sessione Log: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        print("\nLavoro completato. Script Alumen terminato.")