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

# ----- Costanti Globali -----
MAX_RETRIES_PER_API_CALL = 3            # Tentativi per ogni richiesta con API
MAX_MAJOR_FAILURES_THRESHOLD = 6        # Numero massimo di fallimenti prima del passaggio ad nuova API
DEFAULT_MODEL_NAME = "gemini-2.0-flash" # Modello Gemini predefinito
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
    # Definisce e processa gli argomenti da riga di comando.
    global script_args
    parser = argparse.ArgumentParser(
        description="Alumen - Script per tradurre file CSV (o estrarre traduzioni) utilizzando Google Gemini.\nCerca file CSV ricorsivamente e crea sottocartelle 'tradotto' per l'output.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    api_group = parser.add_argument_group('Configurazione API e Modello')
    api_group.add_argument("--api", type=str,
                        help="Specifica una o più chiavi API Google Gemini, separate da virgola.\nAlternativamente, crea un file 'api_key.txt' (una chiave per riga).")
    api_group.add_argument("--model-name", type=str, default=DEFAULT_MODEL_NAME,
                        help=f"Nome del modello Gemini da utilizzare (es. 'gemini-1.5-pro', '{DEFAULT_MODEL_NAME}').\nDefault: '{DEFAULT_MODEL_NAME}'")

    file_format_group = parser.add_argument_group('Configurazione File Input/Output e Formato CSV')
    file_format_group.add_argument("--input", type=str, default="input",
                        help="Percorso della cartella base contenente i file CSV da tradurre (ricerca ricorsiva).\nDefault: 'input'")
    file_format_group.add_argument("--delimiter", type=str, default=",",
                        help="Carattere delimitatore nei file CSV (es. ',' per virgola, '\\t' per tabulazione).\nDefault: ','")
    file_format_group.add_argument("--translate-col", type=int, default=3,
                        help="Indice (0-based) della colonna con il testo originale da tradurre.\nDefault: 3 (quarta colonna)")
    file_format_group.add_argument("--output-col", type=int, default=3,
                        help="Indice (0-based) della colonna per il testo tradotto (usato se non --translation-only-output).\nDefault: 3 (sovrascrive l'originale)")
    file_format_group.add_argument("--max-cols", type=int, default=None,
                        help="Numero massimo di colonne attese per riga (opzionale, per validazione).\nRighe con più colonne verranno saltate. Default: Nessun controllo.")
    file_format_group.add_argument("--encoding", type=str, default="utf-8",
                        help="Codifica caratteri dei file CSV (es. 'utf-8', 'utf-16', 'latin-1').\nDefault: 'utf-8'")

    translation_group = parser.add_argument_group('Parametri di Traduzione')
    translation_group.add_argument("--game-name", type=str, default="un videogioco generico",
                        help="Nome del gioco per contestualizzare la traduzione nel prompt.\nDefault: 'un videogioco generico'")
    translation_group.add_argument("--source-lang", type=str, default="inglese",
                        help="Lingua originale del testo da tradurre (es. 'inglese', 'giapponese').\nDefault: 'inglese'")
    translation_group.add_argument("--target-lang", type=str, default="italiano",
                        help="Lingua di destinazione per la traduzione (es. 'italiano', 'spagnolo').\nDefault: 'italiano'")
    translation_group.add_argument("--translation-only-output", action="store_true",
                        help="Se specificato, il file di output conterrà unicamente i testi tradotti,\nuno per riga. Altrimenti, verrà creata una copia del CSV con la traduzione inserita.")
    translation_group.add_argument("--rpm", type=int, default=None,
                                help="Numero massimo di richieste API a Gemini per minuto. Se specificato,\nlo script regolerà la velocità. Default: illimitato.")


    wrapping_group = parser.add_argument_group('Opzioni A Capo Automatico (Word Wrapping)')
    wrapping_group.add_argument("--wrap-at", type=int, default=None,
                                help="Lunghezza massima della riga per il testo tradotto. Se > 0, attiva l'a capo automatico.\nIl testo tradotto verrà spezzato e unito con --newline-char.\nDefault: disattivato.")
    wrapping_group.add_argument("--newline-char", type=str, default='\\n',
                                help="Carattere o sequenza da usare per l'a capo automatico (es. '\\n', '<br />', 'MY_NL').\nEfficace solo se --wrap-at è specificato e > 0.\nDefault: '\\n' (newline standard).")

    utility_group = parser.add_argument_group('Utilità e Modalità Interattiva')
    utility_group.add_argument("--oneThread", action="store_true",
                        help="Disabilita l'animazione di caricamento testuale (barra di progresso).")
    utility_group.add_argument("--enable-file-log", action="store_true",
                        help=f"Se specificato, attiva la scrittura di un log ('{LOG_FILE_NAME}') nella cartella dello script.")
    utility_group.add_argument("--interactive", action="store_true",
                                help="Se specificato, abilita l'input da tastiera per comandi interattivi\ndurante l'esecuzione (es. 'pause', 'resume', 'skip api', 'skip file', 'help').")
    utility_group.add_argument("--resume", action="store_true",
                                help="Se specificato, tenta di riprendere la traduzione dai file parzialmente completati,\nsaltando le righe già tradotte all'interno di essi.")
    utility_group.add_argument("--rotate-on-limit-or-error", action="store_true",
                                help="Se attivo, in caso di superamento RPM o errore API, tenta immediatamente\ndi passare alla API key successiva invece di attendere o ritentare con la stessa.")


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
    # Converte secondi in formato hh:mm:ss.
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"

def count_lines_in_file(filepath, encoding='utf-8'):
    # Conta le righe in un file, utile per la modalità resume.
    try:
        with open(filepath, 'r', encoding=encoding, newline='') as f:
            return sum(1 for _ in f)
    except FileNotFoundError:
        return 0
    except Exception as e:
        print(f"⚠️  Attenzione: Impossibile contare le righe nel file '{filepath}': {e}")
        if script_args and script_args.enable_file_log:
            write_to_log(f"AVVISO: Impossibile contare le righe nel file '{filepath}': {e}")
        return 0

def setup_log_file():
    # Prepara il file di log se l'opzione è abilitata.
    global log_file_path, script_args
    if not script_args.enable_file_log:
        return

    try:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            script_dir = os.getcwd()
            print(f"⚠️  Attenzione: __file__ non definito, log salvato in directory corrente: {script_dir}")
            write_to_log(f"AVVISO: __file__ non definito, log salvato in directory corrente: {script_dir}")

        log_file_path = os.path.join(script_dir, LOG_FILE_NAME)

        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(ALUMEN_ASCII_ART + "\n")
            f.write(f"--- Nuova Sessione di Log Avviata: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            config_to_log = {k: (v if k != 'api' or not v or len(v) < 15 else f"{v[:5]}...{v[-4:]}(nascosta)")
                             for k, v in vars(script_args).items()}
            f.write(f"Configurazione Applicata: {config_to_log}\n")
            f.write("-" * 70 + "\n")
        print(f"Logging su file abilitato. Output in: '{log_file_path}'")
    except Exception as e:
        print(f"⚠️  Attenzione: Impossibile inizializzare il file di log '{LOG_FILE_NAME}': {e}")
        log_file_path = None

def write_to_log(message):
    # Scrive un messaggio nel file di log, se abilitato.
    global script_args, log_file_path
    if script_args and script_args.enable_file_log and log_file_path:
        try:
            with open(log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        except Exception:
            pass

def log_critical_error_and_exit(message):
    # Logga un errore critico e termina lo script.
    print(f"🛑 ERRORE CRITICO: {message}")
    write_to_log(f"ERRORE CRITICO: {message}")
    sys.exit(1)

def initialize_api_keys_and_model():
    # Carica le API keys e inizializza il modello Gemini.
    global available_api_keys, current_api_key_index, model, script_args, rpm_limit
    print("\n--- Inizializzazione API e Modello ---")
    if script_args.api:
        keys_from_arg = [key.strip() for key in script_args.api.split(',') if key.strip()]
        available_api_keys.extend(keys_from_arg)
        if keys_from_arg:
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

    keys_info_msg = f"Totale API keys uniche disponibili: {len(available_api_keys)}."
    print(f"ℹ️  {keys_info_msg}")
    write_to_log(f"INFO: {keys_info_msg}")
    current_api_key_index = 0
    try:
        current_key = available_api_keys[current_api_key_index]
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel(script_args.model_name)
        init_msg = f"Modello '{script_args.model_name}' inizializzato con API Key: ...{current_key[-4:]}"
        print(f"✅ {init_msg}")
        write_to_log(f"INFO: {init_msg}")
    except Exception as e:
        key_display = available_api_keys[current_api_key_index][-4:] if available_api_keys else 'N/A'
        log_critical_error_and_exit(f"Errore durante l'inizializzazione del modello '{script_args.model_name}' con API Key ...{key_display}: {e}\nVerifica la validità della API key, il nome del modello e la connessione di rete.")

    if script_args.rpm and script_args.rpm > 0:
        rpm_limit = script_args.rpm
        rpm_msg = f"Limite RPM impostato a: {rpm_limit} richieste/minuto."
        print(f"INFO: {rpm_msg}")
        write_to_log(f"INFO: {rpm_msg}")
    print("-" * 50)


def rotate_api_key(triggered_by_user=False, reason_override=None):
    # Passa alla successiva API key disponibile.
    global current_api_key_index, major_failure_count, model, script_args, available_api_keys
    if len(available_api_keys) <= 1:
        msg = "Solo una API key disponibile. Impossibile ruotare."
        print(f"⚠️  {msg}")
        write_to_log(f"AVVISO: {msg}")
        return False

    previous_key_index = current_api_key_index
    current_api_key_index = (current_api_key_index + 1) % len(available_api_keys)
    new_api_key = available_api_keys[current_api_key_index]

    prev_key_display = available_api_keys[previous_key_index][-4:] if available_api_keys[previous_key_index] else "N/A"
    new_key_display = new_api_key[-4:] if new_api_key else "N/A"

    trigger_reason = reason_override if reason_override else ("Comando utente." if triggered_by_user else f"Soglia {MAX_MAJOR_FAILURES_THRESHOLD} fallimenti raggiunta.")
    log_msg_start = f"Rotazione API key ({trigger_reason}). Da Key ...{prev_key_display} (idx {previous_key_index}) a Key ...{new_key_display} (idx {current_api_key_index})."
    print(f"INFO: {log_msg_start}")
    write_to_log(f"INFO: {log_msg_start}")
    try:
        genai.configure(api_key=new_api_key)
        model = genai.GenerativeModel(script_args.model_name)
        success_msg = f"API key ruotata e modello '{script_args.model_name}' riconfigurato con API Key: ...{new_key_display}"
        print(f"✅ {success_msg}")
        write_to_log(f"INFO: {success_msg}")
        major_failure_count = 0
        return True
    except Exception as e:
        error_msg = f"Errore durante la configurazione della nuova API Key ...{new_key_display} (modello '{script_args.model_name}'): {e}"
        print(f"❌ ERRORE: {error_msg}")
        write_to_log(f"ERRORE: {error_msg}")

        revert_msg_start = f"Ripristino API Key precedente (indice {previous_key_index}, Key ...{prev_key_display})"
        print(f"INFO: {revert_msg_start}")
        write_to_log(f"INFO: {revert_msg_start}")
        current_api_key_index = previous_key_index
        try:
            genai.configure(api_key=available_api_keys[previous_key_index])
            model = genai.GenerativeModel(script_args.model_name)
            revert_success_msg = f"API Key precedente ...{prev_key_display} ripristinata."
            print(f"✅ {revert_success_msg}")
            write_to_log(f"INFO: {revert_success_msg}")
        except Exception as e_revert:
             log_critical_error_and_exit(f"Errore nel ripristino della API Key precedente: {e_revert}. Problemi con tutte le API key?")
        return False

def animazione_caricamento(stop_event):
    # Mostra un'animazione testuale.
    for simbolo in itertools.cycle(['|', '/', '-', '\\']):
        if stop_event.is_set():
            break
        sys.stdout.write(f"\rTraduzione in corso {simbolo} ")
        sys.stdout.flush()
        time.sleep(0.2)
    sys.stdout.write("\r" + " " * 40 + "\r")

def command_input_thread_func():
    # Gestisce l'input utente per comandi interattivi.
    global user_command_skip_api, user_command_skip_file, script_args, script_is_paused

    print("\n\n============================================")
    print("    Alumen - Console Interattiva")
    print("============================================")
    print("ℹ️  Digita 'help' per i comandi.")
    print("ℹ️  Digita 'exit' o 'quit' per chiudere (lo script continuerà).")
    while True:
        try:
            prompt_indicator = ""
            if script_args.interactive:
                if not script_is_paused.is_set():
                    prompt_indicator = "(In Pausa) "

            command = input(f"Alumen Interattivo {prompt_indicator}> ").strip().lower()
            with command_lock:
                if command == "skip api":
                    if not user_command_skip_api:
                        user_command_skip_api = True
                        print("   COMANDO RICEVUTO: 'skip api'. Prossima API key al prossimo tentativo.")
                        write_to_log("COMANDO UTENTE: Ricevuto 'skip api'.")
                    else:
                        print("   INFO: Comando 'skip api' già in attesa.")
                elif command == "skip file":
                    if not user_command_skip_file:
                        user_command_skip_file = True
                        print("   COMANDO RICEVUTO: 'skip file'. File corrente saltato appena possibile.")
                        write_to_log("COMANDO UTENTE: Ricevuto 'skip file'.")
                    else:
                        print("   INFO: Comando 'skip file' già in attesa.")
                elif command == "pause":
                    if not script_is_paused.is_set():
                        print("   INFO: Lo script è già in pausa.")
                    else:
                        script_is_paused.clear()
                        print("   COMANDO RICEVUTO: 'pause'. Script in pausa al prossimo controllo.")
                        write_to_log("COMANDO UTENTE: Script messo in pausa.")
                elif command == "resume":
                    if script_is_paused.is_set():
                         print("   INFO: Lo script è già in esecuzione.")
                    else:
                        script_is_paused.set()
                        print("   COMANDO RICEVUTO: 'resume'. Script ripreso.")
                        write_to_log("COMANDO UTENTE: Script ripreso.")
                elif command == "help":
                    print("\n   Comandi disponibili:")
                    print("     pause     - Mette in pausa l'elaborazione.")
                    print("     resume    - Riprende l'elaborazione se in pausa.")
                    print("     skip api  - Passa alla prossima API key.")
                    print("     skip file - Salta il file CSV corrente.")
                    print("     exit/quit - Termina questa console.\n")
                elif command in ["exit", "quit"]:
                    print("   INFO: Thread input comandi terminato.")
                    break
                elif command:
                    print(f"   Comando non riconosciuto: '{command}'. Digita 'help'.")
        except EOFError:
            print("\nINFO: Thread input comandi: EOF ricevuto. Chiusura console.")
            break
        except KeyboardInterrupt:
             print("\nINFO: Thread input comandi: Interruzione. Chiusura console.")
             break
        except Exception as e:
            print(f"🛑 Errore nel thread input comandi: {e}")
            break

def check_and_wait_if_paused(file_context=""):
    # Blocca l'esecuzione se lo script è in pausa (modalità interattiva).
    global script_args, script_is_paused
    if script_args.interactive and not script_is_paused.is_set():
        sys.stdout.write("\r" + " " * 40 + "\r")
        pause_msg = f"Script in PAUSA (Contesto: {file_context if file_context else 'N/A'}). Digita 'resume' per continuare..."
        print(f"\n\n⏳ {pause_msg}\n")
        write_to_log(f"INFO: {pause_msg}")
        script_is_paused.wait()
        resumed_msg = f"Script RIPRESO (Contesto: {file_context if file_context else 'N/A'})."
        print(f"▶️  {resumed_msg}\n")
        write_to_log(f"INFO: {resumed_msg}")

def wait_for_rpm_limit():
    # Gestisce il limite RPM, attendendo o ruotando la chiave API se necessario.
    global rpm_limit, rpm_request_timestamps, script_args, rpm_lock

    if not rpm_limit or rpm_limit <= 0:
        return

    while True:
        if script_args.interactive:
            check_and_wait_if_paused("Attesa RPM")

        wait_duration = 0 # Inizializza wait_duration per questo ciclo
        num_requests_in_window = 0

        with rpm_lock:
            current_time = time.time()
            rpm_request_timestamps[:] = [ts for ts in rpm_request_timestamps if ts > current_time - 60.0]
            num_requests_in_window = len(rpm_request_timestamps)

            if num_requests_in_window < rpm_limit:
                rpm_request_timestamps.append(current_time)
                wait_duration = 0 # Assicura che si esca dal loop while
                break # Esce dal loop while True, la richiesta può partire
            else: # Limite RPM raggiunto
                if script_args.rotate_on_limit_or_error:
                    print(f"INFO: Limite RPM ({rpm_limit}/min) raggiunto. Tento rotazione API Key...")
                    write_to_log(f"INFO: Limite RPM ({rpm_limit}/min) raggiunto. Tento rotazione API Key per --rotate-on-limit-or-error.")
                    if rotate_api_key(reason_override="Limite RPM raggiunto"):
                        print(f"INFO: API Key ruotata con successo. Procedo con la nuova chiave.")
                        write_to_log(f"INFO: API Key ruotata con successo. Procedo con la nuova chiave.")
                        wait_duration = 0 # Resetta l'attesa
                        # Dopo la rotazione, esce per permettere la richiesta con la nuova chiave.
                        # Il prossimo check RPM valuterà la situazione della nuova chiave.
                        break # MODIFICA CHIAVE: Esce dal while
                    # Se rotate_api_key() restituisce False, si procederà con l'attesa.

                # Calcola wait_duration se il limite è ancora raggiunto
                if rpm_request_timestamps:
                    time_of_next_slot = rpm_request_timestamps[0] + 60.0
                    wait_duration = max(0, time_of_next_slot - current_time)
                else:
                    wait_duration = 0

        if wait_duration > 0:
            rpm_msg_console = (f"Limite RPM ({rpm_limit}/min). Richieste finestra: {num_requests_in_window}. "
                               f"Attesa: {wait_duration:.1f}s...")
            print(f"    INFO: {rpm_msg_console}")
            if script_args.enable_file_log:
                write_to_log(f"RPM: {rpm_msg_console}")

            sleep_chunk = 0.5
            slept_time = 0
            while slept_time < wait_duration:
                if script_args.interactive:
                     check_and_wait_if_paused(f"Attesa RPM ({wait_duration-slept_time:.1f}s rimanenti)")

                actual_sleep = min(sleep_chunk, wait_duration - slept_time)
                time.sleep(actual_sleep)
                slept_time += actual_sleep
                if not script_is_paused.is_set():
                    break
        else:
            break

def determine_if_translatable(text_value):
    """Determina se un testo deve essere tradotto (non vuoto, non solo numeri/simboli)."""
    if not isinstance(text_value, str): return False
    text_value_stripped = text_value.strip()
    if not text_value_stripped: return False
    if text_value_stripped.isdigit(): return False
    if re.match(r'^[\W_]+$', text_value_stripped): return False
    if "\\u" in text_value_stripped: return False
    return True

def handle_api_error(e, file_abs_path, display_row_num, text_preview, active_key_display, attempt_num):
    """Gestisce gli errori API, logga e determina il ritardo per il prossimo tentativo."""
    error_message_str = str(e)
    error_api_msg_console = f"Tentativo {attempt_num + 1}/{MAX_RETRIES_PER_API_CALL} (Key ...{active_key_display}) Errore API: {error_message_str}"
    error_api_msg_log = f"File '{file_abs_path}', Riga {display_row_num}, Tentativo {attempt_num + 1}/{MAX_RETRIES_PER_API_CALL} (Key ...{active_key_display}) per testo '{text_preview}...'. Errore: {error_message_str}"
    print(f"    - {error_api_msg_console}")
    write_to_log(f"ERRORE API: {error_api_msg_log}")

    retry_delay_seconds_to_use = DEFAULT_API_ERROR_RETRY_SECONDS
    match = re.search(r"retry_delay\s*{\s*seconds:\s*(\d+)\s*}", error_message_str, re.IGNORECASE)
    if match:
        try:
            suggested_seconds = int(match.group(1))
            retry_delay_seconds_to_use = suggested_seconds + 1
            print(f"      API suggerisce ritardo di {suggested_seconds}s. Attendo {retry_delay_seconds_to_use}s.")
            write_to_log(f"INFO: Errore API per File '{file_abs_path}' (Riga {display_row_num}) suggerisce ritardo di {suggested_seconds}s. Attesa: {retry_delay_seconds_to_use}s.")
        except ValueError:
            print(f"      Impossibile parsare retry_delay: '{match.group(1)}'. Uso fallback {retry_delay_seconds_to_use}s.")
            write_to_log(f"AVVISO: Impossibile parsare retry_delay per File '{file_abs_path}' (Riga {display_row_num}). Fallback: {retry_delay_seconds_to_use}s.")
    else:
        print(f"      Nessun suggerimento di retry_delay. Uso fallback {retry_delay_seconds_to_use}s.")
    return retry_delay_seconds_to_use

def print_translation_progress(file_basename, display_row_num, col_name, active_key_display, original_text_preview, source_lang):
    """Stampa le informazioni sullo stato di avanzamento della traduzione per un testo."""
    print(f"\n  --------------------------------------------------")
    print(f"  File: {file_basename} | Riga: {display_row_num} | Col: {col_name}")
    print(f"  API Key: ...{active_key_display}")
    log_value_preview_cleaned = original_text_preview.replace('\n', ' ').replace('\r', '')
    print(f"  Originale ({source_lang}):\n    '{log_value_preview_cleaned}'")

def write_row_to_output(outfile_handle, csv_writer_obj, row_data_list, translation_only_mode_flag, translated_text_str, output_col_idx_val):
    """Scrive la riga elaborata (originale o con traduzione) nel file di output."""
    if translation_only_mode_flag:
        outfile_handle.write(translated_text_str + "\n")
    elif csv_writer_obj:
        output_row = list(row_data_list)
        if output_col_idx_val >= len(output_row):
            output_row.extend([""] * (output_col_idx_val - len(output_row) + 1))
        output_row[output_col_idx_val] = translated_text_str
        csv_writer_obj.writerow(output_row)

def handle_resume_logic(output_fpath, encoding_val, translation_only_flag, file_basename_val, file_abs_path_val):
    """Gestisce la logica per la modalità --resume."""
    open_mode = 'w'
    skip_data_rows = 0
    skip_trans_lines = 0
    output_file_exists = os.path.exists(output_fpath)

    if script_args.resume and output_file_exists:
        open_mode = 'a'
        lines_in_output = count_lines_in_file(output_fpath, encoding_val)

        if not translation_only_flag:
            skip_data_rows = lines_in_output -1 if lines_in_output > 0 else 0
            resume_msg = f"Ripresa CSV '{file_basename_val}': {lines_in_output} righe output. Salto {skip_data_rows} righe dati input."
        else:
            skip_trans_lines = lines_in_output
            resume_msg = f"Ripresa TXT '{file_basename_val}': {lines_in_output} traduzioni output. Salto {skip_trans_lines} righe traducibili input."
        print(f"INFO: {resume_msg}")
        write_to_log(f"INFO (Resume): File '{file_abs_path_val}' - {resume_msg}")
    return open_mode, skip_data_rows, skip_trans_lines


def traduci_testo_csv(input_file, output_file, current_script_args):
    # Funzione principale per la traduzione di un singolo file CSV.
    global major_failure_count, model, user_command_skip_api, user_command_skip_file, script_is_paused

    stop_event = Event()
    loader_thread = None
    if not current_script_args.oneThread:
        loader_thread = Thread(target=animazione_caricamento, args=(stop_event,))
        loader_thread.start()

    righe_lette_total = 0
    righe_elaborate_per_traduzione = 0
    nome_file_corrente_basename = os.path.basename(input_file)
    nome_file_corrente_abs = os.path.abspath(input_file)

    params = {
        "delimiter": current_script_args.delimiter,
        "translate_col": current_script_args.translate_col,
        "output_col": current_script_args.output_col,
        "max_cols": current_script_args.max_cols,
        "encoding": current_script_args.encoding,
        "game_name": current_script_args.game_name,
        "source_lang": current_script_args.source_lang,
        "target_lang": current_script_args.target_lang,
        "translation_only": current_script_args.translation_only_output,
        "wrap_at": current_script_args.wrap_at,
        "newline_char": current_script_args.newline_char,
    }

    output_open_mode, skip_input_data_rows_count, skip_translatable_lines_count = handle_resume_logic(
        output_file, params["encoding"], params["translation_only"], nome_file_corrente_basename, nome_file_corrente_abs
    )

    try:
        with open(input_file, 'r', encoding=params["encoding"], newline='') as infile, \
             open(output_file, output_open_mode, encoding=params["encoding"], newline='') as outfile_handle:

            reader = csv.reader(infile, delimiter=params["delimiter"])
            csv_writer = None
            if not params["translation_only"]:
                csv_writer = csv.writer(outfile_handle, delimiter=params["delimiter"], quoting=csv.QUOTE_MINIMAL)

            input_header = next(reader, None)
            if input_header:
                righe_lette_total += 1
                if csv_writer and output_open_mode == 'w':
                    csv_writer.writerow(input_header)

            current_data_row_idx_processed = 0
            current_translatable_lines_proc = 0

            for row_number_in_data, row_data in enumerate(reader):
                if script_args.interactive: check_and_wait_if_paused(f"File: {nome_file_corrente_basename}, Riga Dati: {row_number_in_data + 1}")

                with command_lock:
                    if user_command_skip_file:
                        print(f"COMANDO 'skip file' per '{nome_file_corrente_basename}'. Interruzione file.")
                        write_to_log(f"COMANDO UTENTE: File '{nome_file_corrente_abs}' saltato (inizio riga) causa 'skip file'.")
                        user_command_skip_file = False
                        if loader_thread and loader_thread.is_alive(): stop_event.set(); loader_thread.join()
                        return

                righe_lette_total +=1
                display_row_number = row_number_in_data + 1 + (1 if input_header else 0)
                translated_row_content = list(row_data)

                if current_script_args.resume and os.path.exists(output_file):
                    if not params["translation_only"]:
                        if current_data_row_idx_processed < skip_input_data_rows_count:
                            current_data_row_idx_processed += 1
                            continue
                    else:
                        text_for_resume_check = row_data[params["translate_col"]] if len(row_data) > params["translate_col"] else ""
                        if determine_if_translatable(text_for_resume_check):
                            if current_translatable_lines_proc < skip_translatable_lines_count:
                                current_translatable_lines_proc +=1
                                continue

                if not row_data:
                    write_row_to_output(outfile_handle, csv_writer, [], params["translation_only"], "", params["output_col"])
                    continue

                if params["max_cols"] is not None and len(row_data) > params["max_cols"]:
                    msg = f"File '{nome_file_corrente_basename}', Riga {display_row_number}: Supera num. max colonne ({len(row_data)} > {params['max_cols']}). "
                    print(f"⚠️  {msg}Riga saltata/scritta invariata.")
                    write_to_log(f"AVVISO: {msg}Riga saltata/scritta invariata.")
                    if not params["translation_only"]:
                         write_row_to_output(outfile_handle, csv_writer, row_data, False, "", params["output_col"])
                    continue

                value_to_translate_original = row_data[params["translate_col"]] if len(row_data) > params["translate_col"] else ""

                if determine_if_translatable(value_to_translate_original):
                    righe_elaborate_per_traduzione +=1
                    current_col_name = input_header[params["translate_col"]] if input_header and params["translate_col"] < len(input_header) else str(params["translate_col"]+1)
                    translated_text_output = ""
                    translation_successful_for_this_text = False

                    while not translation_successful_for_this_text:
                        if script_args.interactive: check_and_wait_if_paused(f"File: {nome_file_corrente_basename}, Riga: {display_row_number}, Testo: '{value_to_translate_original[:20].replace(params['newline_char'], ' ')}...'")

                        with command_lock:
                            if user_command_skip_file:
                                print(f"COMANDO 'skip file' per '{nome_file_corrente_basename}'. Interruzione file.")
                                write_to_log(f"COMANDO UTENTE: File '{nome_file_corrente_abs}' saltato causa 'skip file'.")
                                user_command_skip_file = False
                                if loader_thread and loader_thread.is_alive(): stop_event.set(); loader_thread.join()
                                return
                            if user_command_skip_api:
                                print(f"   INFO: Comando 'skip api'. Tento rotazione API...")
                                write_to_log(f"COMANDO UTENTE: 'skip api' per File: {nome_file_corrente_abs} Riga: {display_row_number}")
                                rotate_api_key(triggered_by_user=True)
                                user_command_skip_api = False

                        active_key_short = available_api_keys[current_api_key_index][-4:] if available_api_keys and available_api_keys[current_api_key_index] else "N/A"
                        print_translation_progress(nome_file_corrente_basename, display_row_number, current_col_name, active_key_short, value_to_translate_original, params["source_lang"])

                        for attempt_idx in range(MAX_RETRIES_PER_API_CALL):
                            try:
                                wait_for_rpm_limit()
                                prompt_text = f"""Traduci il seguente testo da {params["source_lang"]} a {params["target_lang"]}, mantenendo il contesto del gioco '{params["game_name"]}' e preservando eventuali tag HTML, placeholder (come [p], {{player_name}}), o codici speciali. Rispondi solo con la traduzione diretta.
Testo originale:
{value_to_translate_original}

Traduzione in {params["target_lang"]}:"""

                                time.sleep(BASE_API_CALL_INTERVAL_SECONDS)
                                response_obj = model.generate_content(prompt_text)
                                translated_text_output = response_obj.text.strip()

                                if params["wrap_at"] and params["wrap_at"] > 0 and translated_text_output:
                                    translated_text_output = textwrap.fill(
                                        translated_text_output, width=params["wrap_at"],
                                        initial_indent='', subsequent_indent='',
                                        newline=params["newline_char"], replace_whitespace=False,
                                        drop_whitespace=False, break_long_words=True,
                                        break_on_hyphens=True
                                    )
                                log_trans_preview = translated_text_output.replace(params["newline_char"], ' ')
                                print(f"    Tradotto ({params['target_lang']}):\n      '{log_trans_preview}'")
                                translation_successful_for_this_text = True
                                major_failure_count = 0
                                break

                            except Exception as api_exc:
                                if script_args.rotate_on_limit_or_error:
                                    print(f"    INFO: Errore API con Key ...{active_key_short}. Tento rotazione per --rotate-on-limit-or-error.")
                                    write_to_log(f"INFO: Errore API ({api_exc}) con Key ...{active_key_short} File '{nome_file_corrente_abs}', Riga {display_row_number}. Tentativo rotazione per --rotate-on-limit-or-error.")
                                    if rotate_api_key(reason_override=f"Errore API: {str(api_exc)[:50]}"):
                                        break
                                
                                retry_delay = handle_api_error(api_exc, nome_file_corrente_abs, display_row_number, value_to_translate_original[:30], active_key_short, attempt_idx)
                                if attempt_idx < MAX_RETRIES_PER_API_CALL - 1:
                                    print(f"      Riprovo tra {retry_delay} secondi...")
                                    time.sleep(retry_delay)
                        
                        if not translation_successful_for_this_text:
                            if not (script_args.rotate_on_limit_or_error and len(available_api_keys) > 1) :
                                major_failure_count +=1

                            print(f"    - Traduzione fallita dopo {MAX_RETRIES_PER_API_CALL} tentativi con Key ...{active_key_short}.")
                            write_to_log(f"FALLIMENTO INTERMEDIO: File '{nome_file_corrente_abs}', Riga {display_row_number}, Traduzione fallita dopo {MAX_RETRIES_PER_API_CALL} tentativi con Key ...{active_key_short}.")
                            print(f"      Conteggio fallimenti per Key ...{active_key_short}: {major_failure_count}/{MAX_MAJOR_FAILURES_THRESHOLD}")
                            write_to_log(f"INFO: Conteggio fallimenti per Key ...{active_key_short}: {major_failure_count}/{MAX_MAJOR_FAILURES_THRESHOLD}")

                            if major_failure_count >= MAX_MAJOR_FAILURES_THRESHOLD and not script_args.rotate_on_limit_or_error:
                                if len(available_api_keys) > 1:
                                    print(f"    INFO: Soglia {MAX_MAJOR_FAILURES_THRESHOLD} fallimenti. Rotazione API standard.")
                                    write_to_log(f"AVVISO: Soglia {MAX_MAJOR_FAILURES_THRESHOLD} fallimenti per Key ...{active_key_short}. Rotazione standard.")
                                    if not rotate_api_key():
                                        print(f"    ⚠️  ATTENZIONE: Rotazione API Key fallita. Pausa 60s...")
                                        write_to_log(f"AVVISO CRITICO: Rotazione API Key fallita. Pausa 60s (File: {nome_file_corrente_abs}, Riga {display_row_number})")
                                        time.sleep(60)
                                else:
                                    print(f"    ⚠️  ATTENZIONE: Unica API Key ...{active_key_short} fallisce (soglia {MAX_MAJOR_FAILURES_THRESHOLD}). Pausa 30s...")
                                    write_to_log(f"AVVISO CRITICO: Unica API Key ...{active_key_short} fallisce (soglia {MAX_MAJOR_FAILURES_THRESHOLD}). Pausa 30s (File: {nome_file_corrente_abs}, Riga {display_row_number})")
                                    time.sleep(30)
                            elif not script_args.rotate_on_limit_or_error:
                                print(f"    Attesa: Pausa 15s prima di ritentare con Key ...{active_key_short}...")
                                time.sleep(15)
                    
                    write_row_to_output(outfile_handle, csv_writer, translated_row_content, params["translation_only"], translated_text_output, params["output_col"])

                else:
                    write_row_to_output(outfile_handle, csv_writer, translated_row_content, params["translation_only"], value_to_translate_original if not params["translation_only"] else "", params["output_col"])


                if determine_if_translatable(value_to_translate_original):
                    print(f"  --------------------------------------------------")

    except FileNotFoundError:
        log_critical_error_and_exit(f"File non trovato '{input_file}'.")
    except UnicodeDecodeError as e:
        log_critical_error_and_exit(f"ERRORE DI ENCODING nel file '{nome_file_corrente_abs}' con encoding '{params['encoding']}': {e}\nProva a specificare un encoding diverso con --encoding.")
    except IndexError as e:
        log_critical_error_and_exit(f"ERRORE DI INDICE nel file '{nome_file_corrente_abs}' (riga ~{righe_lette_total}): {e}. Controlla indici colonne e CSV.")
    except Exception as e:
        log_critical_error_and_exit(f"ERRORE IMPREVISTO durante l'elaborazione del file '{nome_file_corrente_abs}': {e}")
    finally:
        if loader_thread and loader_thread.is_alive():
            stop_event.set()
            loader_thread.join()
            sys.stdout.write("\r" + " " * 40 + "\r")

    summary_msg = f"Riepilogo file '{nome_file_corrente_basename}': Righe lette (dati): {righe_lette_total-(1 if input_header else 0)}, Testi elaborati: {righe_elaborate_per_traduzione}"
    print(f"\nINFO: {summary_msg}")


def traduci_tutti_csv_in_cartella_ricorsivo(current_script_args):
    # Scansiona ricorsivamente e traduce tutti i file CSV.
    global user_command_skip_api, user_command_skip_file
    base_input_dir = current_script_args.input
    start_time_total_proc = time.time()
    total_files_proc_count = 0
    total_csv_found = 0

    print(f"\nInizio scansione ricorsiva da: '{base_input_dir}'")
    output_mode_str = "Solo Traduzioni (.txt)" if current_script_args.translation_only_output else "CSV Completo (.csv)"
    wrap_str = f"A capo a {current_script_args.wrap_at} con '{repr(current_script_args.newline_char)}'" if current_script_args.wrap_at and current_script_args.wrap_at > 0 else "Nessuno"
    rpm_str = f"{current_script_args.rpm}richieste/minuto" if current_script_args.rpm and current_script_args.rpm > 0 else "Nessun limite RPM script"
    rotate_on_limit_str = 'Sì' if current_script_args.rotate_on_limit_or_error else 'No'

    config_summary_str = (
        f"------------------------------------------------------------\n"
        f"          Configurazione Globale Applicata\n"
        f"------------------------------------------------------------\n"
        f"  Delimitatore CSV:         '{current_script_args.delimiter}'\n"
        f"  Colonna Testo Originale:  {current_script_args.translate_col}\n"
        f"  Colonna Testo Tradotto:   {current_script_args.output_col} (per output CSV)\n"
        f"  Encoding File:            '{current_script_args.encoding}'\n"
        f"  Modello Gemini:           '{current_script_args.model_name}'\n"
        f"  Contesto Gioco:           '{current_script_args.game_name}'\n"
        f"  Lingua Originale:         '{current_script_args.source_lang}'\n"
        f"  Lingua Destinazione:      '{current_script_args.target_lang}'\n"
        f"  Max Richieste/Minuto:     {rpm_str}\n"
        f"  Rotazione API su Lim/Err: {rotate_on_limit_str}\n"
        f"  Modalità Output File:     '{output_mode_str}'\n"
        f"  A Capo Automatico:        {wrap_str}\n"
        f"  Ripresa Abilitata:        {'Sì' if current_script_args.resume else 'No'}\n"
        f"  Logging su File:          {'Abilitato ('+LOG_FILE_NAME+')' if current_script_args.enable_file_log else 'Disabilitato'}\n"
        f"  Modalità Interattiva:     {'ATTIVA' if current_script_args.interactive else 'NON ATTIVA'}\n"
        f"  Animazione Caricamento:   {'Disabilitata' if current_script_args.oneThread else 'Abilitata'}\n"
        f"------------------------------------------------------------"
    )
    print(config_summary_str)

    for root_dir, dirs_list, files_list in os.walk(base_input_dir, topdown=True):
        if script_args.interactive: check_and_wait_if_paused(f"Scansione cartella: {root_dir}")

        if "tradotto" in dirs_list:
            dirs_list.remove("tradotto")

        current_normalized_root = os.path.normpath(root_dir)
        path_parts = current_normalized_root.split(os.sep)
        if "tradotto" in path_parts and current_normalized_root != os.path.normpath(base_input_dir) :
            continue

        csv_files_current_dir = [f for f in files_list if f.endswith('.csv')]

        if not csv_files_current_dir:
            continue

        print(f"\nEsplorando cartella: '{root_dir}'")
        print(f"   Trovati {len(csv_files_current_dir)} file CSV.")
        total_csv_found += len(csv_files_current_dir)

        output_subfolder = os.path.join(root_dir, "tradotto")
        if not os.path.exists(output_subfolder):
            try:
                os.makedirs(output_subfolder)
                created_dir_log_msg = f"Creata sotto-cartella output: '{output_subfolder}'"
                print(f"   INFO: {created_dir_log_msg}")
                write_to_log(f"INFO: {created_dir_log_msg}")
            except OSError as e:
                error_creating_dir_msg = f"Impossibile creare cartella output '{output_subfolder}': {e}. File saltati."
                print(f"   ❌ ERRORE: {error_creating_dir_msg}")
                write_to_log(f"ERRORE: {error_creating_dir_msg}")
                continue

        for csv_filename in csv_files_current_dir:
            if script_args.interactive: check_and_wait_if_paused(f"Inizio file: {csv_filename} in {root_dir}")

            with command_lock:
                if user_command_skip_file:
                    skip_file_log_msg = f"COMANDO 'skip file' attivo. Salto file '{csv_filename}' in '{root_dir}'."
                    print(f"INFO: {skip_file_log_msg}")
                    write_to_log(f"COMANDO UTENTE: {skip_file_log_msg}")
                    user_command_skip_file = False
                    continue

            file_proc_start_time = time.time()
            input_fpath_abs = os.path.abspath(os.path.join(root_dir, csv_filename))

            output_fname_base, _ = os.path.splitext(csv_filename)
            output_final_fname_str = f"{output_fname_base}_trads_only.txt" if current_script_args.translation_only_output else csv_filename
            output_fpath_abs = os.path.abspath(os.path.join(output_subfolder, output_final_fname_str))

            if current_script_args.resume and os.path.exists(output_fpath_abs):
                print(f"INFO: File output '{output_fpath_abs}' esiste. Resume tenterà di continuare.")
                write_to_log(f"INFO (Resume): Trovato output esistente '{output_fpath_abs}'. Tentativo ripresa interna.")

            print(f"\nInizio elaborazione file: '{input_fpath_abs}'")
            write_to_log(f"AVVIO FILE: Inizio elaborazione di '{input_fpath_abs}'")

            traduci_testo_csv(input_fpath_abs, output_fpath_abs, current_script_args)

            file_proc_elapsed_s = time.time() - file_proc_start_time
            total_elapsed_cumulative_s = time.time() - start_time_total_proc

            log_entry_file_done_str = (f"COMPLETATO FILE (o saltato):\n"
                                   f"     Sorgente: '{input_fpath_abs}'\n"
                                   f"     Output:   '{output_fpath_abs}'\n"
                                   f"     Tempo per file: {format_time_delta(file_proc_elapsed_s)}\n"
                                   f"     Durata Totale: {format_time_delta(total_elapsed_cumulative_s)}")
            print(f"   File output: '{output_fpath_abs}'")
            print(f"   Tempo per file: {format_time_delta(file_proc_elapsed_s)}")
            write_to_log(log_entry_file_done_str)
            total_files_proc_count += 1

    final_elapsed_time = time.time() - start_time_total_proc
    summary_final_msg = (f"Scansione e traduzione completata.\n"
                       f"     Totale file CSV trovati: {total_csv_found}\n"
                       f"     Totale file elaborati: {total_files_proc_count}\n"
                       f"     Tempo totale esecuzione: {format_time_delta(final_elapsed_time)}")
    print(f"\n{summary_final_msg}")
    write_to_log(f"SOMMARIO FINALE: {summary_final_msg.replace(current_script_args.newline_char, ' // ')}")


if __name__ == "__main__":
    # Punto di ingresso principale
    print(ALUMEN_ASCII_ART)
    print("Benvenuto in Alumen - Traduttore Automatico Multilingua!\n")

    args_parsed_main = get_script_args_updated()
    script_is_paused.set()

    if args_parsed_main.enable_file_log:
        setup_log_file()

    initialize_api_keys_and_model()

    if not os.path.exists(args_parsed_main.input):
        log_critical_error_and_exit(f"La cartella di input base '{args_parsed_main.input}' non esiste.")
    if not os.path.isdir(args_parsed_main.input):
        log_critical_error_and_exit(f"Il percorso di input base '{args_parsed_main.input}' non è una cartella.")

    main_start_log_msg = f"Cartella input base: '{os.path.abspath(args_parsed_main.input)}'"
    print(f"\nINFO: {main_start_log_msg}")
    write_to_log(f"INFO: {main_start_log_msg}")
    print(f"INFO: Sottocartelle 'tradotto' create dinamicamente.")

    cmd_thread = None
    if args_parsed_main.interactive:
        cmd_thread = threading.Thread(target=command_input_thread_func, daemon=True)
        cmd_thread.start()

    try:
        traduci_tutti_csv_in_cartella_ricorsivo(args_parsed_main)
    except KeyboardInterrupt:
        print("\n🛑 Interruzione da tastiera (Ctrl+C). Uscita...")
        write_to_log("INTERRUZIONE: Script interrotto da tastiera (Ctrl+C).")
        with command_lock:
            user_command_skip_file = True
    finally:
        if script_args and script_args.interactive and cmd_thread and cmd_thread.is_alive():
            print("INFO: Thread input comandi attivo (terminerà con lo script).")

        write_to_log(f"--- FINE Sessione Log: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        print("\nScript Alumen terminato.")