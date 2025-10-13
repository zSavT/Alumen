# Contenuto completo del file modificato 'Alumen.py'

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
import polib

# ----- Costanti Globali -----
MAX_RETRIES_PER_API_CALL = 3            # Tentativi per ogni richiesta con API
MAX_MAJOR_FAILURES_THRESHOLD = 6        # Numero massimo di fallimenti prima del passaggio ad nuova API
DEFAULT_MODEL_NAME = "gemini-2.5-flash" # Modello Gemini predefinito
LOG_FILE_NAME = "log.txt"               # Nome file log
CACHE_FILE_NAME = "alumen_cache.json"   # Nome file per la cache persistente
DEFAULT_API_ERROR_RETRY_SECONDS = 10    # Numero di secondi di attesa tra una chiamata all'API se non impostato RPM o l'errore dell'api non suggerisce un delay
BASE_API_CALL_INTERVAL_SECONDS = 0.2    # Pausa minima tra chiamate API, l'RPM gestisce il resto
FILE_CONTEXT_SAMPLE_SIZE = 15           # Numero di righe/entry da usare per determinare il contesto del file

# ----- Variabili Globali -----
available_api_keys = []      # Lista API CaricateI
current_api_key_index = 0    # Indice api attiva
major_failure_count = 0      # Contatore per fallimenti API con la stessa chiave
model = None                 # Modello Gemini
script_args = None           # Oggetto per gli argomenti passati allo script
log_file_path = None         # Path file log
translation_cache = {}       # Dizionario per la cache delle traduzioni

# Lista di parole o frasi che non devono essere tradotte ma preservate.
# NOTA: Inserisci qui tutti i termini da non tradurre (es. nomi propri, ID, variabili).
BLACKLIST_TERMS = set([
    "Dummy",
    "dummy"
])

# Variabile Globale per la blacklist delle API
blacklisted_api_key_indices = set() # Set di indici delle API key considerate esaurite (token finiti, ecc.)

# Nuovi contatori per le statistiche
api_call_counts = {}         # Dizionario per contare l'uso di ogni API key (indice: conteggio)
cache_hit_count = 0          # Contatore per le traduzioni trovate nella cache
# Nuovi contatori per le statistiche richieste
start_time = 0.0             # Tempo di inizio esecuzione
total_files_translated = 0   # Contatore per i file tradotti
total_entries_translated = 0 # Contatore per le frasi/entry tradotte

# Gestione Cache e Stato Salvataggio
last_cache_save_time = 0.0 # Timestamp dell'ultimo salvataggio cache 

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

    utility_group.add_argument("--oneThread", action="store_true", help="\033[97mDisabilita l'animazione di caricamento.\033[0m")
    utility_group.add_argument("--enable-file-log", action="store_true", help=f"\033[97mAttiva la scrittura di un log ('{LOG_FILE_NAME}').\033[0m")
    utility_group.add_argument("--interactive", action="store_true", help="\033[97mAbilita comandi interattivi.\033[0m")
    utility_group.add_argument("--resume", action="store_true", help="\033[97mTenta di riprendere la traduzione da file parziali.\033[0m")
    utility_group.add_argument("--rotate-on-limit-or-error", action="store_true", help="\033[97mPassa alla API key successiva in caso di errore o limite RPM.\033[0m")
    utility_group.add_argument("--persistent-cache", action="store_true", help=f"\033[97mAttiva la cache persistente su file ('{CACHE_FILE_NAME}').\033[0m")

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
    global available_api_keys, current_api_key_index, model, rpm_limit, api_call_counts
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
    
    # Inizializza il contatore delle chiamate API per ogni chiave
    api_call_counts = {i: 0 for i in range(len(available_api_keys))}
    
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

def add_api_key(new_key):
    """Aggiunge una nuova API key in runtime."""
    global available_api_keys, api_call_counts, blacklisted_api_key_indices
    new_key = new_key.strip()
    if not new_key:
        print("   ERRORE: La chiave API non può essere vuota.")
        return False
    if new_key in available_api_keys:
        print("   INFO: Questa API key è già presente nella lista.")
        return False

    # Aggiungi la nuova chiave e inizializza il suo contatore
    available_api_keys.append(new_key)
    new_index = len(available_api_keys) - 1
    api_call_counts[new_index] = 0
    
    # Rimuovi l'indice dalla blacklist se per qualche motivo era presente (non dovrebbe)
    blacklisted_api_key_indices.discard(new_index)
    
    print(f"   ✅ API Key ...{new_key[-4:]} aggiunta con successo. Totale: {len(available_api_keys)} keys.")
    write_to_log(f"COMANDO INTERATTIVO: Aggiunta nuova API Key ...{new_key[-4:]}")
    return True


def rotate_api_key(triggered_by_user=False, reason_override=None):
    global current_api_key_index, major_failure_count, model, blacklisted_api_key_indices 
    
    usable_keys_count = len(available_api_keys) - len(blacklisted_api_key_indices)
    
    # Modificato check per una sola chiave utilizzabile (se la chiave attuale non è blacklisted)
    if usable_keys_count <= 1 and current_api_key_index not in blacklisted_api_key_indices:
        print("⚠️  Solo una API key utilizzabile disponibile. Impossibile ruotare.")
        return False
    
    if usable_keys_count == 0:
        print("🛑 ERRORE CRITICO: Tutte le API key sono state blacklisted. Impossibile proseguire.")
        write_to_log("ERRORE CRITICO: Tutte le API key sono state blacklisted.")
        return False

    previous_key_index = current_api_key_index
    initial_index = current_api_key_index
    
    # Loop per trovare la prossima chiave non blacklisted
    while True:
        current_api_key_index = (current_api_key_index + 1) % len(available_api_keys)
        
        if current_api_key_index not in blacklisted_api_key_indices:
            break
            
        if current_api_key_index == initial_index:
            # Rotazione completa senza successo
            print("🛑 ERRORE CRITICO: Impossibile trovare una API key non blacklisted.")
            write_to_log("ERRORE CRITICO: Impossibile trovare una API key non blacklisted.")
            # Ripristinare l'indice precedente se si è fallito e l'indice precedente non era blacklisted
            if previous_key_index not in blacklisted_api_key_indices:
                current_api_key_index = previous_key_index
            return False # Nessuna chiave utilizzabile trovata

    new_api_key = available_api_keys[current_api_key_index]
    trigger_reason = reason_override if reason_override else ("Comando utente." if triggered_by_user else f"Soglia fallimenti raggiunta.")
    print(f"INFO: Rotazione API key ({trigger_reason})...")
    try:
        genai.configure(api_key=new_api_key)
        model = genai.GenerativeModel(script_args.model_name)
        print(f"✅ API key ruotata e modello '{script_args.model_name}' riconfigurato. Nuova Key: ...{new_api_key[-4:]}")
        major_failure_count = 0
        return True
    except Exception as e:
        print(f"❌ ERRORE: Configurazione nuova API Key fallita: {e}")
        # Gestione fallimento: ripristina la chiave precedente se non blacklisted, altrimenti fallisce.
        if previous_key_index not in blacklisted_api_key_indices:
            current_api_key_index = previous_key_index
            try:
                genai.configure(api_key=available_api_keys[previous_key_index])
                model = genai.GenerativeModel(script_args.model_name)
                print("✅ API Key precedente ripristinata.")
            except Exception as e_revert:
                log_critical_error_and_exit(f"Errore nel ripristino della API Key precedente: {e_revert}.")
        else:
            print("🛑 ERRORE CRITICO: Fallita rotazione API e la chiave precedente è blacklisted. Nessuna chiave utilizzabile.")
            log_critical_error_and_exit("Fallita rotazione API e la chiave precedente è blacklisted. Nessuna chiave utilizzabile.")

        return False

def blacklist_current_api_key():
    """Aggiunge l'indice della chiave API corrente alla lista nera e tenta una rotazione."""
    global current_api_key_index, blacklisted_api_key_indices
    
    if current_api_key_index in blacklisted_api_key_indices:
        print(f"   INFO: L'API Key ...{available_api_keys[current_api_key_index][-4:]} è già nella lista nera.")
        return False
        
    blacklisted_api_key_indices.add(current_api_key_index)
    key_suffix = available_api_keys[current_api_key_index][-4:]
    print(f"   ✅ COMANDO RICEVUTO: API Key ...{key_suffix} aggiunta alla lista nera (token esauriti).")
    write_to_log(f"COMANDO INTERATTIVO: API Key ...{key_suffix} aggiunta alla lista nera.")
    
    # Tenta immediatamente la rotazione
    return rotate_api_key(triggered_by_user=True, reason_override="Key blacklisted (Token Exhausted)")


def animazione_caricamento(stop_event):
    for simbolo in itertools.cycle(['|', '/', '-', '\\']):
        if stop_event.is_set(): break
        sys.stdout.write(f"\rTraduzione in corso {simbolo} ")
        sys.stdout.flush()
        time.sleep(0.2)
    sys.stdout.write("\r" + " " * 40 + "\r")

def show_stats():
    """Visualizza le statistiche attuali."""
    end_time = time.time()
    total_time = end_time - start_time
    total_api_calls = sum(api_call_counts.values())
    
    avg_time_per_file = 0.0
    if total_files_translated > 0:
        avg_time_per_file = total_time / total_files_translated
        
    print("\n\n" + "=" * 50)
    print("      STATISTICHE ATTUALI (Interattiva)")
    print("=" * 50)
    
    print(f"⏳ Tempo Trascorso:            {format_time_delta(total_time)}")
    print(f"✅ File Tradotti:              {total_files_translated}")
    print(f"✅ Frasi/Entry Tradotte:       {total_entries_translated}")
    if total_files_translated > 0:
        print(f"⏱️  Tempo Medio per File:       {format_time_delta(avg_time_per_file)}")
    
    print(f"\n➡️  Cache Hit Totali: {cache_hit_count}")
    print(f"➡️  API Call Totali:  {total_api_calls}")
    
    print("\n--- Dettaglio API Key ---")
    for i, count in api_call_counts.items():
        key_suffix = available_api_keys[i][-4:]
        status = "(ATTIVA)" if i == current_api_key_index else ""
        
        # Indicazione Blacklist
        if i in blacklisted_api_key_indices: 
            status = "(BLACKLISTED - Token Finiti)" 
            
        print(f"    - Key ...{key_suffix} {status}: {count} chiamate")
    print("-" * 50)


def command_input_thread_func():
    global user_command_skip_api, user_command_skip_file, script_is_paused
    print("\n\n============================================")
    print("    Alumen - Console Interattiva")
    print("============================================")
    print("ℹ️  Digita 'help' per i comandi, 'exit' o 'quit' per chiudere.")
    while True:
        try:
            prompt_indicator = "(In Pausa) " if not script_is_paused.is_set() else ""
            command_line = input(f"Alumen Interattivo {prompt_indicator}> ").strip()
            command_parts = command_line.lower().split(maxsplit=2)
            command = command_parts[0] if command_parts else ""
            sub_command = command_parts[1] if len(command_parts) > 1 else ""

            with command_lock:
                if command == "skip":
                    if sub_command == "api":
                        user_command_skip_api = True; print("   COMANDO RICEVUTO: 'skip api'.")
                    elif sub_command == "file":
                        user_command_skip_file = True; print("   COMANDO RICEVUTO: 'skip file'.")
                    else:
                        print("   Comando 'skip' non valido. Usa 'skip api' o 'skip file'.")
                elif command == "pause": 
                    script_is_paused.clear(); print("   COMANDO RICEVUTO: 'pause'.")
                elif command == "resume": 
                    script_is_paused.set(); print("   COMANDO RICEVUTO: 'resume'.")
                elif command == "stats":
                    show_stats(); print("   COMANDO RICEVUTO: 'stats'.")
                elif command == "add":
                    if sub_command == "api" and len(command_parts) > 2:
                        new_key = command_parts[2].strip()
                        add_api_key(new_key)
                    else:
                         print("   Comando 'add' non valido. Usa 'add api <chiave_api>'.")
                elif command == "exhausted":
                    blacklist_current_api_key()
                # NUOVO COMANDO INTERATTIVO PER IL SALVATAGGIO DELLA CACHE
                elif command == "save" or (command == "salva" and sub_command == "cache"):
                    if script_args.persistent_cache:
                        print("   COMANDO RICEVUTO: 'save cache'. Salvataggio cache in corso...")
                        save_persistent_cache()
                        print("   ✅ Salvataggio cache completato.")
                    else:
                        print(f"   ⚠️  Attenzione: La cache persistente è disabilitata. Usa --persistent-cache all'avvio dello script.")
                # FINE NUOVO COMANDO
                elif command == "help": 
                    print("\n   Comandi:")
                    print("     pause: Mette in pausa l'elaborazione.")
                    print("     resume: Riprende l'elaborazione.")
                    print("     skip api: Salta l'attuale API key e ruota alla successiva.")
                    print("     skip file: Salta l'elaborazione del file corrente.")
                    print("     stats: Mostra le statistiche attuali di esecuzione.")
                    print("     add api <chiave>: Aggiunge una nuova chiave API in runtime.")
                    print("     exhausted: Mette nella lista nera (blacklist) l'API key attualmente in uso (es. token finiti) e ruota alla successiva.")
                    print("     save cache / salva cache: Salva immediatamente la cache di traduzione su file (necessita --persistent-cache).") # AGGIORNATO
                    print("     exit/quit: Termina la console interattiva.")
                    print("\n")
                elif command: 
                    print(f"   Comando non riconosciuto: '{command}'. Digita 'help'.")
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
    
    # 1. Controllo base: vuoto, solo numeri, o solo simboli/underscore
    if not text_value_stripped or text_value_stripped.isdigit() or re.match(r'^[\W_]+$', text_value_stripped) or "\\u" in text_value_stripped:
        return False

    # 2. Controllo per flessibilità (per distinguere ID da frasi):
    # Salta se contiene underscore ('_') ma non contiene spazi. 
    if '_' in text_value_stripped and ' ' not in text_value_stripped:
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

def load_persistent_cache():
    """Carica la cache delle traduzioni da file se l'opzione è attiva e imposta il tempo di salvataggio iniziale."""
    global translation_cache, script_args, last_cache_save_time
    if not script_args.persistent_cache:
        return
    try:
        if os.path.exists(CACHE_FILE_NAME):
            with open(CACHE_FILE_NAME, 'r', encoding='utf-8') as f:
                translation_cache = json.load(f)
            print(f"✅ Cache persistente caricata da '{CACHE_FILE_NAME}' con {len(translation_cache)} voci.")
            last_cache_save_time = time.time() # Imposta il tempo di salvataggio al momento del caricamento
        else:
            print(f"ℹ️  File cache '{CACHE_FILE_NAME}' non trovato. Verrà creato a fine esecuzione.")
            last_cache_save_time = 0.0
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  Attenzione: Impossibile caricare la cache da '{CACHE_FILE_NAME}': {e}. La cache verrà ricreata.")
        translation_cache = {}
        last_cache_save_time = 0.0

def save_persistent_cache():
    """Salva la cache delle traduzioni su file se l'opzione è attiva e aggiorna il timestamp."""
    global translation_cache, script_args, last_cache_save_time
    if not script_args.persistent_cache or not translation_cache:
        if script_args.persistent_cache:
            # Se la cache è abilitata ma vuota, e viene chiamato esplicitamente, lo notifichiamo.
            if not translation_cache:
                print("\nℹ️  Salvataggio cache ignorato: la cache di traduzione è attualmente vuota.")
            # Se la cache non è abilitata, il messaggio è gestito dal chiamante (o semplicemente ritorna in silenzio)
        return
    try:
        with open(CACHE_FILE_NAME, 'w', encoding='utf-8') as f:
            json.dump(translation_cache, f, ensure_ascii=False, indent=4)
        print(f"\n✅ Cache di traduzione ({len(translation_cache)} voci) salvata in '{CACHE_FILE_NAME}'.")
        last_cache_save_time = time.time() # Aggiorna il timestamp di salvataggio
    except IOError as e:
        print(f"\n❌ ERRORE: Impossibile salvare la cache in '{CACHE_FILE_NAME}': {e}")

def check_and_save_cache():
    """Salva la cache se sono trascorsi 10 minuti (600 secondi) dall'ultimo salvataggio."""
    global last_cache_save_time, script_args
    if not script_args.persistent_cache:
        return
        
    current_time = time.time()
    if current_time - last_cache_save_time >= 600: # 10 minutes = 600 seconds
        print("\nℹ️  Salvataggio cache periodico (10 minuti) in corso...")
        write_to_log("Salvataggio cache periodico (10 minuti) attivato.")
        save_persistent_cache()


# --- FUNZIONE PER LA GENERAZIONE DEL CONTESTO DEL FILE ---
def generate_file_context(sample_text, file_name, args):
    """Genera il contesto generale del file basandosi su un campione di testo."""
    global major_failure_count, model, translation_cache, cache_hit_count, api_call_counts
    
    # La chiave di cache per il contesto del file può rimanere, dato che dipende dagli argomenti globali e dal nome del file.
    context_cache_key = f"CONTEXT_FILE::{file_name}::{args.game_name}::{args.prompt_context}"
    if args.full_context_sample:
        context_cache_key += "::FULL_SAMPLE"
        
    if context_cache_key in translation_cache:
        print(f"  - ✅ CACHE HIT: Trovato contesto in cache per il file '{file_name}'.")
        cache_hit_count += 1
        return translation_cache[context_cache_key]

    print(f"  - Richiesta API per la determinazione del contesto per il file '{file_name}'...")
    
    context_for_log = f"Generazione Contesto per File: {file_name}"

    prompt = f"""
    Analizza il seguente campione di testo, che proviene da un file di traduzione per il gioco '{args.game_name}'.
    Il tuo compito è determinare, in non più di due frasi concise, l'argomento principale, il contesto generale o l'ambientazione più probabile di questo file.
    Questo contesto verrà utilizzato per migliorare la qualità delle traduzioni successive.
    Rispondi solo con il contesto generato.

    Campione di testo:\n---
    {sample_text}
    ---
    Contesto generato:
    """
    
    while True:
        if args.interactive: check_and_wait_if_paused(context_for_log)
        
        active_key_short = available_api_keys[current_api_key_index][-4:]
        
        for attempt_idx in range(MAX_RETRIES_PER_API_CALL):
            try:
                wait_for_rpm_limit()
                time.sleep(BASE_API_CALL_INTERVAL_SECONDS)
                
                response_obj = model.generate_content(prompt)
                file_context = response_obj.text.strip()
                
                api_call_counts[current_api_key_index] += 1 # Aggiorna contatore API
                
                if args.wrap_at and args.wrap_at > 0:
                    file_context = textwrap.fill(file_context, width=args.wrap_at, newline=args.newline_char, replace_whitespace=False)
                
                translation_cache[context_cache_key] = file_context
                print(f"  - ✅ Contesto file generato: '{file_context}'")
                write_to_log(f"Contesto generato per {file_name}: {file_context}")
                major_failure_count = 0
                return file_context

            except Exception as api_exc:
                if args.rotate_on_limit_or_error:
                    if rotate_api_key(reason_override=f"Errore API durante generazione contesto"):
                        break
                
                retry_delay = handle_api_error(api_exc, context_for_log, active_key_short, attempt_idx)
                if attempt_idx < MAX_RETRIES_PER_API_CALL - 1:
                    time.sleep(retry_delay)
        
        # Gestione fallimenti API per la generazione del contesto
        major_failure_count += 1
        print(f"    - Fallimento definitivo generazione contesto con Key ...{active_key_short}. Conteggio fallimenti: {major_failure_count}/{MAX_MAJOR_FAILURES_THRESHOLD}")
        
        if major_failure_count >= MAX_MAJOR_FAILURES_THRESHOLD:
            if not rotate_api_key():
                print("    ⚠️  ATTENZIONE: Rotazione API fallita. Contesto file non generabile. Proseguo senza contesto specifico.")
                write_to_log(f"ERRORE CRITICO: Contesto file non generabile per {file_name}. Proseguo senza contesto specifico.")
                return None
        else:
            time.sleep(15)
            
    return None # Fallback in caso di errore non gestito

# --- FUNZIONE GET_TRANSLATION_FROM_API (Modificata per la cache e la blacklist) ---
def get_translation_from_api(text_to_translate, context_for_log, args, dynamic_context=None):
    """
    Funzione centralizzata per ottenere la traduzione. Gestisce i tentativi, la rotazione delle API,
    i limiti RPM, la costruzione del prompt e il caching.
    """
    global major_failure_count, user_command_skip_api, model, translation_cache, cache_hit_count, api_call_counts, BLACKLIST_TERMS

    # 1. CHECK BLACKLIST (Controlla se l'intera stringa è in blacklist)
    if text_to_translate.strip() in BLACKLIST_TERMS:
        print(f"    - 🛑 BLACKLIST HIT: Il testo '{text_to_translate}' è in blacklist. Salto traduzione.")
        write_to_log(f"BLACKLIST HIT: Saltata traduzione per '{text_to_translate}' nel contesto: {context_for_log}")
        return text_to_translate

    if not determine_if_translatable(text_to_translate):
        return text_to_translate

    # La chiave della cache (un tuple) viene convertita in una stringa JSON per essere serializzabile.
    # Rimosso dynamic_context da cache_key_tuple!
    cache_key_tuple = (text_to_translate, args.source_lang, args.target_lang, args.game_name, args.prompt_context)
    cache_key = json.dumps(cache_key_tuple, ensure_ascii=False)

    if cache_key in translation_cache:
        print(f"    - ✅ CACHE HIT: Trovata traduzione in cache per '{text_to_translate[:50].strip()}...'.")
        write_to_log(f"CACHE HIT: Usata traduzione in cache per il contesto: {context_for_log}")
        cache_hit_count += 1 # Aggiorna contatore cache hit
        return translation_cache[cache_key]
    
    while True:
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
                        return text_to_translate
                    prompt_text = args.custom_prompt.format(text_to_translate=text_to_translate)
                else:
                    # Preparazione lista blacklist per il prompt
                    blacklist_str = ", ".join(BLACKLIST_TERMS)
                    
                    # MODIFICA: Aggiunta istruzione per preservare gli a capo.
                    prompt_base = f"""Traduci il seguente testo da {args.source_lang} a {args.target_lang}, mantenendo il contesto del gioco '{args.game_name}'. ISTRUZIONE CRITICA: preserva esattamente tutti gli a capo originali (come `\\n` o `\\r\\n`) presenti nel testo. Inoltre, preserva eventuali tag HTML, placeholder (come [p], {{player_name}}), o codici speciali (come ad esempio stringhe con codici tipo: talk_id_player). Assicurati di mantenere identici i seguenti termini che NON devono essere tradotti, anche se appaiono in frasi più lunghe: {blacklist_str}. In caso di dubbi sul genere (Femminile o Maschile), utilizza il maschile."""
                    
                    if args.prompt_context: prompt_base += f"\nIstruzione aggiuntiva: {args.prompt_context}."
                    
                    # Usa dynamic_context per il contesto specifico del file o dell'entry (o entrambi)
                    if dynamic_context: prompt_base += f"\nContesto aggiuntivo per questa traduzione: '{dynamic_context}'."
                    
                    prompt_base += "\nRispondi solo con la traduzione diretta."
                    prompt_text = f"{prompt_base}\nTesto originale:\n{text_to_translate}\n\nTraduzione in {args.target_lang}:"
                
                time.sleep(BASE_API_CALL_INTERVAL_SECONDS)
                response_obj = model.generate_content(prompt_text)
                translated_text = response_obj.text.strip()
                
                api_call_counts[current_api_key_index] += 1 # Aggiorna contatore API

                if args.wrap_at and args.wrap_at > 0:
                    translated_text = textwrap.fill(translated_text, width=args.wrap_at, newline=args.newline_char, replace_whitespace=False)
                
                major_failure_count = 0
                translation_cache[cache_key] = translated_text # Salva con la chiave SENZA dynamic_context
                write_to_log(f"CACHE MISS: Nuova traduzione salvata in cache per il contesto: {context_for_log}")

                return translated_text

            except Exception as api_exc:
                if args.rotate_on_limit_or_error:
                    if rotate_api_key(reason_override=f"Errore API"):
                        break
                
                retry_delay = handle_api_error(api_exc, context_for_log, active_key_short, attempt_idx)
                if attempt_idx < MAX_RETRIES_PER_API_CALL - 1:
                    time.sleep(retry_delay)
        
        major_failure_count += 1
        print(f"    - Fallimento definitivo con Key ...{active_key_short}. Conteggio fallimenti: {major_failure_count}/{MAX_MAJOR_FAILURES_THRESHOLD}")
        
        if major_failure_count >= MAX_MAJOR_FAILURES_THRESHOLD:
            if not rotate_api_key():
                print("    ⚠️  ATTENZIONE: Rotazione API fallita. Pausa di 60s prima di ritentare.")
                time.sleep(60)
        else:
            time.sleep(15)

# --- NUOVA FUNZIONE HELPER PER ESTRARRE IL CAMPIONE JSON ---
def _extract_json_sample_texts(obj, keys_to_translate, sample_list, path="", match_full=False, limit=FILE_CONTEXT_SAMPLE_SIZE):
    """Estrae i primi N testi traducibili per la determinazione del contesto JSON. Se 'limit' è None, estrae tutti."""
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
        for item in obj:
            _extract_json_sample_texts(item, keys_to_translate, sample_list, path, match_full, limit)


def should_translate_msgctxt(context_string):
    """
    Determina se un msgctxt debba essere tradotto.
    Ritorna False se sembra un ID, una chiave, un tag o contiene caratteri non testuali.
    """
    # Utilizza il controllo generale esistente come base
    if not determine_if_translatable(context_string) or '_' in context_string:
        return False

    # Controlli specifici aggiuntivi per identificare chiavi o dati non traducibili
    
    # 1. Contiene caratteri di tabulazione (es: "1165\tCOMPLEANNO")
    if '\t' in context_string:
        return False

    # 2. Contiene tag simili a HTML/XML (es: "<Speaker>Player</Speaker>")
    if re.search(r'<[a-zA-Z/][^>]*>', context_string):
        return False

    # 3. È una stringa senza spazi che contiene numeri o una combinazione di maiuscole/minuscole
    #    (es. "item123", "KeyName"), che suggerisce sia un ID o una variabile.
    stripped_context = context_string.strip()
    if ' ' not in stripped_context:
        has_digits = any(char.isdigit() for char in stripped_context)
        # islower() e isupper() sono entrambe False se la stringa ha un mix di casi
        is_mixed_case = not stripped_context.islower() and not stripped_context.isupper()

        if has_digits or is_mixed_case:
            return False
    
    # Se supera tutti i controlli, viene considerato testo traducibile. (Messo a False perchè non dovrebbe mai essere tradotto)
    return False

def traduci_testo_po(input_file, output_file, args):
    """Elabora un singolo file PO."""
    file_basename = os.path.basename(input_file)
    print(f"\n--- Elaborazione PO: {file_basename} ---")

    try:
        po_file = polib.pofile(input_file, encoding=args.encoding)
    except Exception as e:
        log_critical_error_and_exit(f"Impossibile leggere o parsare il file PO '{input_file}': {e}")

    # --- Generazione Contesto File (PO) ---
    file_context = None
    if args.enable_file_context:
        sample_limit = None if args.full_context_sample else FILE_CONTEXT_SAMPLE_SIZE
        sample_texts = []
        for entry in po_file:
            # Qui usiamo solo determine_if_translatable, la logica anti-ID ora è lì
            if determine_if_translatable(entry.msgid):
                sample_texts.append(entry.msgid)
                if sample_limit is not None and len(sample_texts) >= sample_limit:
                    break
        
        if sample_texts:
            print(f"  - Generazione contesto con {'TUTTE' if sample_limit is None else f'le prime {sample_limit}'} frasi ({len(sample_texts)} totali)...")
            sample_text_for_api = "\n".join(sample_texts)
            file_context = generate_file_context(sample_text_for_api, file_basename, args)

    texts_to_translate_count = sum(1 for entry in po_file if determine_if_translatable(entry.msgid))
    print(f"Trovate {texts_to_translate_count} entry da tradurre nel file.")
    processed_count = 0
    global total_entries_translated

    try:
        for entry in po_file:
            with command_lock:
                if user_command_skip_file:
                    print(f"COMANDO 'skip file' ricevuto. Interruzione elaborazione di '{file_basename}'.")
                    raise KeyboardInterrupt

            print(f"\n--- Riga {entry.linenum} ---")

            original_context = entry.msgctxt
            context_for_prompt = None
            context_is_translatable_prose = should_translate_msgctxt(original_context)

            if context_is_translatable_prose:
                # Se è testo valido, traducilo
                print(f"  - Traduzione Contesto...")
                print(f"    Originale: '{original_context}'")
                
                context_log_for_ctxt = f"PO '{file_basename}', Traduzione Contesto, Riga: {entry.linenum}"
                # Non usiamo il file_context per tradurre il msgctxt, altrimenti ci sarebbe un contesto nel contesto
                translated_context = get_translation_from_api(original_context, context_log_for_ctxt, args, dynamic_context=None) 
                
                entry.msgctxt = translated_context
                context_for_prompt = translated_context # Usa il contesto tradotto per il msgid
                total_entries_translated += 1
                print(f"    Tradotto:  '{entry.msgctxt}'")
            elif original_context:
                # Se il contesto esiste ma non è traducibile (è un ID/chiave), usalo com'è come informazione
                print(f"  - Contesto non traducibile, usato come informazione per il testo: '{original_context}'")
                context_for_prompt = original_context # Usa il contesto originale per il msgid

            is_msgid_translatable = (entry.msgid and 
                                     determine_if_translatable(entry.msgid))
            
            if is_msgid_translatable:
                processed_count += 1
                total_entries_translated += 1
                print(f"  - Traduzione Testo ({processed_count}/{texts_to_translate_count})...")

                combined_context = []
                if file_context:
                    combined_context.append(f"Contesto Generale File: {file_context}")
                if context_for_prompt:
                    # Aggiorna la descrizione per chiarezza nel log
                    context_description = "msgctxt tradotto" if context_is_translatable_prose else "da msgctxt"
                    combined_context.append(f"Contesto Specifico Entry ({context_description}): {context_for_prompt}")
                
                final_dynamic_context = " - ".join(combined_context) if combined_context else None
                
                if final_dynamic_context:
                    print(f"    (Usando contesto combinato: '{final_dynamic_context}')")
                elif original_context:
                    print(f"    (Contesto ID ignorato per traduzione: '{original_context}')")

                original_text = entry.msgid
                print(f"    Originale: '{original_text[:80].replace(chr(10), ' ')}...'")
                
                context_log = f"PO '{file_basename}', Traduzione msgid, Riga: {entry.linenum}"
                # Passa il contesto combinato come dynamic_context
                translated_text = get_translation_from_api(original_text, context_log, args, dynamic_context=final_dynamic_context)
                entry.msgstr = translated_text
                
                print(f"    Tradotto:  '{translated_text[:80].replace(chr(10), ' ')}...'")
            else:
                # Se msgid non è traducibile, copia msgid in msgstr.
                if entry.msgid:
                    entry.msgstr = entry.msgid
                    print(f"  - Testo non traducibile (msgid non valido o è un ID/Chiave). msgstr impostato a: '{entry.msgstr[:80].replace(chr(10), ' ')}...'")
                    
    except KeyboardInterrupt:
        print(f"\n🛑 INTERRUZIONE UTENTE: Salvataggio dei progressi per il file '{file_basename}' in corso...")
        write_to_log(f"INTERRUZIONE UTENTE: Salvataggio progressi parziali per PO '{file_basename}'")
    
    finally:
        write_to_log(f"Salvataggio (completo o parziale) in corso per '{file_basename}' in '{output_file}'.")
        try:
            po_file.save(output_file)
            print(f"✅ Salvataggio dati in '{output_file}' completato.")
            save_persistent_cache() # Save cache after file completion
        except Exception as e:
            log_critical_error_and_exit(f"Impossibile scrivere il file di output '{output_file}': {e}")
            
    print(f"--- Completato PO: {file_basename} ---")


# --- FUNZIONE TRADUCI_TESTO_JSON AGGIORNATA ---
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
    
    # --- Generazione Contesto File (JSON) ---
    file_context = None
    if args.enable_file_context: # CHECK FLAG
        sample_texts = []
        # NUOVA LOGICA: DETERMINAZIONE DEL LIMITE
        sample_limit = None if args.full_context_sample else FILE_CONTEXT_SAMPLE_SIZE
        
        _extract_json_sample_texts(data, keys_to_translate, sample_texts, path="", match_full=args.match_full_json_path, limit=sample_limit) # Corretto sample_list in sample_texts

        if sample_texts:
            print(f"  - Generazione contesto con {'TUTTE' if sample_limit is None else f'le prime {sample_limit}'} frasi ({len(sample_texts)} totali)...")
            sample_text_for_api = "\n".join(sample_texts)
            file_context = generate_file_context(sample_text_for_api, file_basename, args)
    # ----------------------------------------
    
    try:
        texts_to_translate_count = 0
        processed_count = 0
        global total_entries_translated # Dichiarazione variabile globale

        if args.match_full_json_path:
            print("ℹ️  Modalità traduzione JSON con corrispondenza percorso completo abilitata.")
            def _count_translatable_items_legacy(obj, path=""):
                nonlocal texts_to_translate_count
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        if current_path in keys_to_translate and determine_if_translatable(value):
                            texts_to_translate_count += 1
                        _count_translatable_items_legacy(value, current_path)
                elif isinstance(obj, list):
                    for item in obj:
                        _count_translatable_items_legacy(item, path)

            def _traverse_and_translate_legacy(obj, path=""):
                nonlocal processed_count
                global total_entries_translated # Importo qui per le funzioni annidate
                if isinstance(obj, dict):
                    for key, value in list(obj.items()):
                        current_path = f"{path}.{key}" if path else key
                        if current_path in keys_to_translate and determine_if_translatable(value):
                            processed_count += 1
                            total_entries_translated += 1 # INCREMENTO GLOBALE
                            context_log = f"JSON '{file_basename}', Chiave: '{current_path}'"
                            print(f"\n  ({processed_count}/{texts_to_translate_count}) Traduzione per '{current_path}':")
                            print(f"    Originale: '{str(value)[:80]}...'")
                            # Passa il contesto del file
                            translated_value = get_translation_from_api(value, context_log, args, dynamic_context=file_context)
                            obj[key] = translated_value
                            print(f"    Tradotto:  '{str(translated_value)[:80]}...'")
                            if args.translation_only_output:
                                translated_texts_for_only_output.append(translated_value)
                        _traverse_and_translate_legacy(value, current_path)
                elif isinstance(obj, list):
                    for item in obj:
                        _traverse_and_translate_legacy(item, path)
            count_func, translate_func = _count_translatable_items_legacy, _traverse_and_translate_legacy
        else:
            print("ℹ️  Modalità traduzione JSON con corrispondenza nome chiave (default) abilitata.")
            def _count_translatable_items_new(obj, path=""):
                nonlocal texts_to_translate_count
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key in keys_to_translate and determine_if_translatable(value):
                            texts_to_translate_count += 1
                        _count_translatable_items_new(value, f"{path}.{key}" if path else key)
                elif isinstance(obj, list):
                    for item in obj:
                        _count_translatable_items_new(item, path)

            def _traverse_and_translate_new(obj, path=""):
                nonlocal processed_count
                global total_entries_translated # Importo qui per le funzioni annidate
                if isinstance(obj, dict):
                    for key, value in list(obj.items()):
                        if key in keys_to_translate and determine_if_translatable(value):
                            processed_count += 1
                            total_entries_translated += 1 # INCREMENTO GLOBALE
                            current_path_for_log = f"{path}.{key}" if path else key
                            context_log = f"JSON '{file_basename}', Chiave: '{current_path_for_log}'"
                            print(f"\n  ({processed_count}/{texts_to_translate_count}) Traduzione per '{current_path_for_log}':")
                            print(f"    Originale: '{str(value)[:80]}...'")
                            # Passa il contesto del file
                            translated_value = get_translation_from_api(value, context_log, args, dynamic_context=file_context)
                            obj[key] = translated_value
                            print(f"    Tradotto:  '{str(translated_value)[:80]}...'")
                            if args.translation_only_output:
                                translated_texts_for_only_output.append(translated_value)
                        _traverse_and_translate_new(value, f"{path}.{key}" if path else key)
                elif isinstance(obj, list):
                    for item in obj:
                        _traverse_and_translate_new(item, path)
            count_func, translate_func = _count_translatable_items_new, _traverse_and_translate_new

        count_func(data)
        print(f"Trovati {texts_to_translate_count} valori da tradurre per le chiavi specificate.")
        
        translate_func(data)
        
        print(f"--- Completato JSON: {file_basename} ---")

    except KeyboardInterrupt:
        print(f"\n🛑 INTERRUZIONE UTENTE: Salvataggio dei progressi per il file '{file_basename}' in corso...")
        write_to_log(f"INTERRUZIONE UTENTE: Salvataggio progressi parziali per JSON '{file_basename}'")
        raise
    
    finally:
        write_to_log(f"Salvataggio (completo o parziale) in corso per '{file_basename}' in '{output_file}'.")
        try:
            with open(output_file, 'w', encoding=args.encoding) as f:
                if args.translation_only_output:
                    for text in translated_texts_for_only_output:
                        f.write(text + "\n")
                else:
                    json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"✅ Salvataggio dati in '{output_file}' completato.")
            save_persistent_cache() # Save cache after file completion
        except Exception as e:
            log_critical_error_and_exit(f"Impossibile scrivere il file di output '{output_file}': {e}")

# --- FUNZIONE TRADUCI_TESTO_CSV AGGIORNATA ---
def traduci_testo_csv(input_file, output_file, args):
    """Elabora un singolo file CSV."""
    file_basename = os.path.basename(input_file)
    print(f"\n--- Elaborazione CSV: {file_basename} ---")
    
    rows = []
    try:
        with open(input_file, 'r', encoding=args.encoding, newline='') as infile:
            # Per gestire meglio i file CSV potenzialmente errati, si può provare a dedurre il dialetto, 
            # ma per ora manteniamo la semplicità con il delimitatore fornito.
            reader = csv.reader(infile, delimiter=args.delimiter)
            rows = list(reader)
    except Exception as e:
        log_critical_error_and_exit(f"Impossibile leggere il file CSV '{input_file}': {e}")

    header = rows[0] if rows and not args.resume else None # Assumiamo l'header solo se non in resume mode per semplicità
    data_rows = rows[1:] if header else rows
    
    # --- Generazione Contesto File (CSV) ---
    file_context = None
    if args.enable_file_context: # CHECK FLAG
        sample_texts = []
        # NUOVA LOGICA: DETERMINAZIONE DEL LIMITE
        sample_limit = None if args.full_context_sample else FILE_CONTEXT_SAMPLE_SIZE
        
        for row in data_rows:
            if len(row) > args.translate_col and determine_if_translatable(row[args.translate_col]):
                sample_texts.append(row[args.translate_col])
                if sample_limit is not None and len(sample_texts) >= sample_limit:
                    break
        
        if sample_texts:
            print(f"  - Generazione contesto con {'TUTTE' if sample_limit is None else f'le prime {sample_limit}'} frasi ({len(sample_texts)} totali)...")
            sample_text_for_api = "\n".join(sample_texts)
            file_context = generate_file_context(sample_text_for_api, file_basename, args)
    # ----------------------------------------
    
    texts_to_translate_count = sum(1 for row in data_rows if len(row) > args.translate_col and determine_if_translatable(row[args.translate_col]))
    print(f"Trovate {texts_to_translate_count} righe da tradurre nella colonna {args.translate_col}.")
    processed_count = 0
    translated_texts_for_only_output = []
    global total_entries_translated # Dichiarazione variabile globale

    for i, row in enumerate(data_rows):
        display_row_num = i + (2 if header else 1)
        
        # Controllo per saltare righe già tradotte in modalità resume
        if args.resume and len(row) > args.output_col and not determine_if_translatable(row[args.translate_col]):
             # Se la colonna di output è già riempita e non è la colonna originale
             if args.output_col != args.translate_col and row[args.output_col].strip():
                print(f"  - Riga {display_row_num} (Originale: '{row[args.translate_col][:80]}...') già tradotta (Resume Mode). Salto.")
                processed_count += 1
                if args.translation_only_output and len(row) > args.output_col:
                    translated_texts_for_only_output.append(row[args.output_col])
                continue
        
        # Controllo per tradurre
        if len(row) > args.translate_col and determine_if_translatable(row[args.translate_col]):
            processed_count += 1
            total_entries_translated += 1 # INCREMENTO GLOBALE
            original_text = row[args.translate_col]
            context_log = f"CSV '{file_basename}', Riga: {display_row_num}"
            print(f"\n  ({processed_count}/{texts_to_translate_count}) Traduzione per riga {display_row_num}:")
            print(f"    Originale: '{original_text[:80]}...'")
            
            # Passa il contesto del file
            translated_text = get_translation_from_api(original_text, context_log, args, dynamic_context=file_context)
            
            # Assicura che la riga abbia abbastanza colonne per l'output
            while len(row) <= args.output_col:
                row.append('') 
                
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
                if header: 
                    writer.writerow(rows[0])
                    writer.writerows(data_rows)
                else:
                    writer.writerows(rows)
        
        print(f"✅ Salvataggio dati in '{output_file}' completato.")
        save_persistent_cache() # Save cache after file completion
    except Exception as e:
        log_critical_error_and_exit(f"Impossibile scrivere il file di output '{output_file}': {e}")
        
    print(f"--- Completato CSV: {file_basename} ---")

def process_files_recursively(args):
    """Scansiona le cartelle, trova i file e avvia il processo di traduzione corretto."""
    global user_command_skip_file, total_files_translated
    base_input_dir = os.path.abspath(args.input)
    base_output_dir = os.path.join(os.path.dirname(base_input_dir), "tradotto") # Cartella 'tradotto' allo stesso livello di 'input'

    # Se la cartella di input si chiama 'input', l'output sarà 'tradotto'
    if os.path.basename(base_input_dir) != "input":
        base_output_dir = os.path.join(os.path.dirname(base_input_dir), "tradotto") # L'output va in una cartella parallela "tradotto"

    total_files_found = 0

    print(f"\nInizio scansione per file *.{args.file_type} da: '{base_input_dir}'")
    print(f"Output verrà salvato nella struttura di cartelle sotto: '{base_output_dir}'")
    
    os.makedirs(base_output_dir, exist_ok=True)


    for root_dir, dirs_list, files_list in os.walk(base_input_dir):
        # Calcola il path relativo della sottocartella rispetto all'input base
        relative_path = os.path.relpath(root_dir, base_input_dir)
        
        # Definisci la cartella di output corrispondente per la sottocartella
        current_output_dir = os.path.join(base_output_dir, relative_path)
        
        os.makedirs(current_output_dir, exist_ok=True)
            
        files_to_process = [f for f in files_list if f.endswith(f'.{args.file_type}')]
        if not files_to_process: continue
            
        print(f"\nEsplorando cartella: '{root_dir}' (Output: '{current_output_dir}') - Trovati {len(files_to_process)} file *.{args.file_type}.")
        total_files_found += len(files_to_process)

        for filename in files_to_process:
            
            check_and_save_cache() # Periodic cache check

            with command_lock:
                if user_command_skip_file:
                    print(f"COMANDO 'skip file' ricevuto. Salto file '{filename}'.")
                    user_command_skip_file = False
                    continue

            if script_args.interactive: check_and_wait_if_paused(f"Inizio file: {os.path.join(relative_path, filename)}")
            
            input_path = os.path.join(root_dir, filename)
            
            # Determina il nome del file di output
            if args.translation_only_output:
                 output_filename = f"{os.path.splitext(filename)[0]}_trads.txt"
            else:
                 output_filename = filename
                 
            output_path = os.path.join(current_output_dir, output_filename)
            
            # Logica per la ripresa (resume mode)
            if args.resume and os.path.exists(output_path):
                if args.file_type != 'csv':
                    print(f"⚠️  Attenzione: Resume mode abilitato, ma non supportato per {args.file_type}. Sovrascrivo '{output_path}'.")
                elif args.file_type == 'csv':
                    print(f"ℹ️  Resume mode attivo. Tentativo di riprendere da '{output_path}'.")
                    pass 
                
            
            if args.file_type == 'csv':
                traduci_testo_csv(input_path, output_path, args)
            elif args.file_type == 'json':
                traduci_testo_json(input_path, output_path, args)
            elif args.file_type == 'po':
                traduci_testo_po(input_path, output_path, args)
                
            total_files_translated += 1 # INCREMENTO FILE CONTATORE


if __name__ == "__main__":
    print(ALUMEN_ASCII_ART)
    print("Benvenuto in Alumen - Traduttore Automatico Multilingua!\n")

    args_parsed_main = get_script_args_updated()
    
    if args_parsed_main.file_type == 'json' and not args_parsed_main.json_keys:
        log_critical_error_and_exit("Per --file-type 'json', è obbligatorio specificare le chiavi con --json-keys.")

    script_is_paused.set()

    start_time = time.time()

    if args_parsed_main.enable_file_log: setup_log_file()
    initialize_api_keys_and_model()
    load_persistent_cache()  # Carica la cache prima di iniziare l'elaborazione

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
            
        save_persistent_cache()  # Salvataggio finale garantito
        

        show_stats()

        write_to_log(f"--- FINE Sessione Log: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        print("\nScript Alumen terminato.")