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
available_api_keys = []      # Lista API Caricate
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
   Traductor Automatico Multilingua potenziato da Gemini
"""

def get_script_args_updated():
    # Definisce e processa gli argomenti da riga di comando. 
    global script_args
    parser = argparse.ArgumentParser(
        description="Alumen - Script per tradurre file CSV (o estrarre traduzioni) utilizzando Google Gemini.\nCerca file CSV ricorsivamente e crea sottocartelle 'tradotto' per l'output.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    api_group = parser.add_argument_group('⚙️  Configurazione API e Modello')
    api_group.add_argument("--api", type=str, 
                        help="Specifica una o più chiavi API Google Gemini, separate da virgola.\nAlternativamente, crea un file 'api_key.txt' (una chiave per riga).")
    api_group.add_argument("--model-name", type=str, default=DEFAULT_MODEL_NAME,
                        help=f"Nome del modello Gemini da utilizzare (es. 'gemini-1.5-pro', '{DEFAULT_MODEL_NAME}').\nDefault: '{DEFAULT_MODEL_NAME}'")
    
    file_format_group = parser.add_argument_group('📄 Configurazione File Input/Output e Formato CSV')
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

    translation_group = parser.add_argument_group('🗣️  Parametri di Traduzione')
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


    wrapping_group = parser.add_argument_group('📐 Opzioni A Capo Automatico (Word Wrapping)')
    wrapping_group.add_argument("--wrap-at", type=int, default=None,
                                help="Lunghezza massima della riga per il testo tradotto. Se > 0, attiva l'a capo automatico.\nIl testo tradotto verrà spezzato e unito con --newline-char.\nDefault: disattivato.") 
    wrapping_group.add_argument("--newline-char", type=str, default='\\n',
                                help="Carattere o sequenza da usare per l'a capo automatico (es. '\\n', '<br />', 'MY_NL').\nEfficace solo se --wrap-at è specificato e > 0.\nDefault: '\\n' (newline standard).")

    utility_group = parser.add_argument_group('🛠️  Utilità e Modalità Interattiva')
    utility_group.add_argument("--oneThread", action="store_true",
                        help="Disabilita l'animazione di caricamento testuale (barra di progresso).")
    utility_group.add_argument("--enable-file-log", action="store_true",
                        help=f"Se specificato, attiva la scrittura di un log ('{LOG_FILE_NAME}') nella cartella dello script.")
    utility_group.add_argument("--interactive", action="store_true",
                                help="Se specificato, abilita l'input da tastiera per comandi interattivi\ndurante l'esecuzione (es. 'pause', 'resume', 'skip api', 'skip file', 'help').") 
    utility_group.add_argument("--resume", action="store_true",
                                help="Se specificato, tenta di riprendere la traduzione dai file parzialmente completati,\nsaltando le righe già tradotte all'interno di essi.")

    parsed_args = parser.parse_args()
    
    # Gestione caratteri speciali per delimitatore e newline casi comuni
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
            f.write(f"--- 🏁 Nuova Sessione di Log Avviata: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            # Logga la configurazione, nascondendo parzialmente le API keys
            config_to_log = {k: (v if k != 'api' or not v or len(v) < 15 else f"{v[:5]}...{v[-4:]}(nascosta)") 
                             for k, v in vars(script_args).items()} 
            f.write(f"🔧 Configurazione Applicata: {config_to_log}\n")
            f.write("-" * 70 + "\n")
        print(f"📝 Logging su file abilitato. Output in: '{log_file_path}'") 
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

def initialize_api_keys_and_model():
    # Carica le API keys (da argomento o file) e inizializza il modello Gemini.
    global available_api_keys, current_api_key_index, model, script_args, rpm_limit
    print("\n--- ⚙️  Inizializzazione API e Modello ---")
    if script_args.api:
        keys_from_arg = [key.strip() for key in script_args.api.split(',') if key.strip()]
        available_api_keys.extend(keys_from_arg)
        if keys_from_arg:
             print(f"🔑 {len(keys_from_arg)} API key(s) fornite tramite argomento --api.") 

    api_key_file_path = "api_key.txt"
    if os.path.exists(api_key_file_path):
        with open(api_key_file_path, "r") as f:
            keys_from_file = [line.strip() for line in f if line.strip()]
            if keys_from_file:
                available_api_keys.extend(keys_from_file)
                print(f"🔑 {len(keys_from_file)} API key(s) caricate dal file '{api_key_file_path}'.") 
    
    # Rimuove duplicati mantenendo l'ordine
    seen = set() 
    available_api_keys = [x for x in available_api_keys if not (x in seen or seen.add(x))]

    if not available_api_keys:
        msg = "Nessuna API key trovata. Specificare tramite --api o nel file 'api_key.txt'. Script interrotto."
        print(f"🛑 ERRORE: {msg}")
        write_to_log(f"ERRORE CRITICO: {msg}")
        sys.exit(1)

    keys_info_msg = f"Totale API keys uniche disponibili: {len(available_api_keys)}."
    print(f"ℹ️  {keys_info_msg}")
    write_to_log(f"INFO: {keys_info_msg}")
    current_api_key_index = 0
    try:
        current_key = available_api_keys[current_api_key_index]
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel(script_args.model_name)
        init_msg = f"Modello '{script_args.model_name}' inizializzato con successo usando API Key: ...{current_key[-4:]}" 
        print(f"✅ {init_msg}")
        write_to_log(f"INFO: {init_msg}")
    except Exception as e:
        key_display = available_api_keys[current_api_key_index][-4:] if available_api_keys else 'N/A'
        crit_err_msg = f"Errore critico durante l'inizializzazione del modello '{script_args.model_name}' con API Key ...{key_display}: {e}"
        print(f"🛑 {crit_err_msg}")
        print("ℹ️  Verifica la validità della API key, il nome del modello e la connessione di rete. Script interrotto.") 
        write_to_log(f"ERRORE CRITICO: {crit_err_msg}")
        sys.exit(1)
    
    # Imposta il limite RPM se specificato
    if script_args.rpm and script_args.rpm > 0:
        rpm_limit = script_args.rpm 
        rpm_msg = f"Limite RPM impostato a: {rpm_limit} richieste/minuto."
        print(f"🚦 {rpm_msg}")
        write_to_log(f"INFO: {rpm_msg}")
    print("-" * 50) 


def rotate_api_key(triggered_by_user=False):
    # Passa alla successiva API key disponibile.
    # Resetta il contatore `major_failure_count` se la rotazione ha successo.
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

    trigger_reason = "Comando utente." if triggered_by_user else f"Soglia {MAX_MAJOR_FAILURES_THRESHOLD} fallimenti raggiunta."
    log_msg_start = f"Rotazione API key ({trigger_reason}). Da Key ...{prev_key_display} (idx {previous_key_index}) a Key ...{new_key_display} (idx {current_api_key_index})." 
    print(f"🔑 {log_msg_start}")
    write_to_log(f"INFO: {log_msg_start}")
    try:
        genai.configure(api_key=new_api_key)
        model = genai.GenerativeModel(script_args.model_name) 
        success_msg = f"API key ruotata e modello '{script_args.model_name}' riconfigurato con API Key: ...{new_key_display}"
        print(f"✅ {success_msg}")
        write_to_log(f"INFO: {success_msg}")
        major_failure_count = 0 # Rotazione avvenuta, azzera i fallimenti per la nuova chiave
        return True 
    except Exception as e:
        error_msg = f"Errore durante la configurazione della nuova API Key ...{new_key_display} (modello '{script_args.model_name}'): {e}" 
        print(f"❌ {error_msg}")
        write_to_log(f"ERRORE: {error_msg}")
        
        # Tenta di ripristinare la chiave precedente in caso di fallimento con la nuova
        revert_msg_start = f"Ripristino API Key precedente (indice {previous_key_index}, Key ...{prev_key_display})"
        print(f"↪️  {revert_msg_start}")
        write_to_log(f"INFO: {revert_msg_start}")
        current_api_key_index = previous_key_index 
        try: 
            genai.configure(api_key=available_api_keys[previous_key_index])
            model = genai.GenerativeModel(script_args.model_name)
            # print(model.model_info) # Lasciato commentato come nell'originale
            revert_success_msg = f"API Key precedente ...{prev_key_display} ripristinata."
            print(f"✅ {revert_success_msg}")
            write_to_log(f"INFO: {revert_success_msg}")
        except Exception as e_revert: 
             critical_revert_error = f"Errore critico nel ripristino della API Key precedente: {e_revert}. Problemi con tutte le API key?" 
             print(f"🛑 {critical_revert_error}")
             write_to_log(f"ERRORE CRITICO: {critical_revert_error}")
        return False 

def animazione_caricamento(stop_event):
    # Mostra un'animazione testuale durante le operazioni lunghe.
    for simbolo in itertools.cycle(['|', '/', '-', '\\']):
        if stop_event.is_set(): 
            break
        sys.stdout.write(f"\r🔄  Traduzione in corso {simbolo} ") 
        sys.stdout.flush() # Pulisce il buffer
        time.sleep(0.2)
    sys.stdout.write("\r" + " " * 40 + "\r") 

def command_input_thread_func():
    # Gestisce l'input utente per comandi interattivi in un thread separato.
    global user_command_skip_api, user_command_skip_file, script_args, script_is_paused
    
    print("\n\n============================================")
    print("    Alumen - Console Interattiva    ")
    print("============================================")
    print("ℹ️  Digita 'help' per i comandi.")
    print("ℹ️  Digita 'exit' o 'quit' per chiudere questa console (lo script continuerà).")
    while True: 
        try: 
            prompt_indicator = ""
            if script_args.interactive: 
                if not script_is_paused.is_set(): 
                    prompt_indicator = "(In Pausa) "

            command = input(f"Alumen Interattivo {prompt_indicator}> ").strip().lower()
            with command_lock: 
                if command == "skip api":
                    # Imposta il flag per saltare alla prossima API key
                    if not user_command_skip_api: 
                        user_command_skip_api = True
                        print("   ➡️  COMANDO RICEVUTO: 'skip api'. La prossima API key verrà usata al prossimo tentativo/testo.") 
                        write_to_log("COMANDO UTENTE: Ricevuto 'skip api'.")
                    else:
                        print("   ℹ️  INFO: Comando 'skip api' già in attesa di esecuzione.")
                elif command == "skip file":
                    # Imposta il flag per saltare il file corrente
                    if not user_command_skip_file:
                        user_command_skip_file = True
                        print("   ➡️  COMANDO RICEVUTO: 'skip file'. Il file corrente verrà saltato appena possibile.")
                        write_to_log("COMANDO UTENTE: Ricevuto 'skip file'.")
                    else:
                        print("   ℹ️  INFO: Comando 'skip file' già in attesa di esecuzione.")
                elif command == "pause": 
                    # Mette in pausa lo script
                    if not script_is_paused.is_set(): 
                        print("   ℹ️  INFO: Lo script è già in pausa.")
                    else:
                        script_is_paused.clear() 
                        print("   ⏸️  COMANDO RICEVUTO: 'pause'. Lo script verrà messo in pausa al prossimo punto di controllo.")
                        write_to_log("COMANDO UTENTE: Script messo in pausa.")
                elif command == "resume":
                    # Riprende lo script se era in pausa
                    if script_is_paused.is_set(): 
                         print("   ℹ️  INFO: Lo script è già in esecuzione.") 
                    else:
                        script_is_paused.set() 
                        print("   ▶️  COMANDO RICEVUTO: 'resume'. Lo script riprenderà l'elaborazione.")
                        write_to_log("COMANDO UTENTE: Script ripreso.") 
                elif command == "help":
                    # Mostra i comandi disponibili
                    print("\n   💡 Comandi disponibili:")
                    print("     pause     - Mette in pausa l'elaborazione dello script.") 
                    print("     resume    - Riprende l'elaborazione dello script se in pausa.")
                    print("     skip api  - Tenta di passare immediatamente alla prossima API key disponibile.")
                    print("     skip file - Salta il file CSV attualmente in elaborazione.") 
                    print("     exit/quit - Termina questa console di input comandi.\n")
                elif command in ["exit", "quit"]:
                    print("   ℹ️  Thread di input comandi terminato dall'utente.")
                    break 
                elif command: 
                    print(f"   ❓ Comando non riconosciuto: '{command}'. Digita 'help' per la lista.")
        except EOFError: 
            print("\nℹ️  Thread di input comandi: EOF ricevuto. Chiusura console interattiva.")
            break
        except KeyboardInterrupt: 
             print("\nℹ️  Thread di input comandi: Interruzione da tastiera (Ctrl+C). Chiusura console interattiva.")
             break
        except Exception as e: 
            print(f"🛑 Errore nel thread di input comandi: {e}")
            break 

def check_and_wait_if_paused(file_context=""):
    # Funzione helper per bloccare l'esecuzione se lo script è in pausa.
    global script_args, script_is_paused
    if script_args.interactive and not script_is_paused.is_set():
        sys.stdout.write("\r" + " " * 40 + "\r") # Pulisce la riga dell'animazione di caricamento, se presente
        pause_msg = f"Script in PAUSA (Contesto: {file_context if file_context else 'N/A'}). Digita 'resume' per continuare..."
        print(f"\n\n⏳ {pause_msg}\n")
        write_to_log(f"INFO: {pause_msg}")
        script_is_paused.wait() # Attende finché l'evento `script_is_paused` non viene settato
        resumed_msg = f"Script RIPRESO (Contesto: {file_context if file_context else 'N/A'})."
        print(f"▶️  {resumed_msg}\n")
        write_to_log(f"INFO: {resumed_msg}")

def wait_for_rpm_limit():
    # Gestisce il limite di richieste API per minuto (RPM).
    # Attende se il numero di richieste recenti supera il limite.
    global rpm_limit, rpm_request_timestamps, script_args, rpm_lock 
    
    if not rpm_limit or rpm_limit <= 0: # Nessun limite RPM impostato
        return

    while True: 
        if script_args.interactive: 
            check_and_wait_if_paused("Attesa RPM") # Permette la pausa anche durante l'attesa RPM
            
        with rpm_lock: 
            current_time = time.time()
            # Filtra i timestamp delle richieste mantenendo solo quelli nell'ultima finestra di 60 secondi
            rpm_request_timestamps[:] = [ts for ts in rpm_request_timestamps if ts > current_time - 60.0] 
            num_requests_in_window = len(rpm_request_timestamps)

            if num_requests_in_window < rpm_limit:
                rpm_request_timestamps.append(current_time) # Registra la nuova richiesta
                break 
            else:
                # Calcola quanto attendere per il prossimo slot disponibile
                time_of_next_slot = rpm_request_timestamps[0] + 60.0 
                wait_duration = time_of_next_slot - current_time
        
        if wait_duration > 0:
            rpm_msg_console = (f"Limite RPM ({rpm_limit}/min). Richieste finestra: {num_requests_in_window}. " 
                               f"Attesa: {wait_duration:.1f}s...")
            print(f"    🚦 {rpm_msg_console}") 
            if script_args.enable_file_log: 
                write_to_log(f"RPM: {rpm_msg_console}") 
            
            # Suddivide l'attesa in piccoli intervalli per rimanere responsivo ai comandi di pausa
            sleep_chunk = 0.5 
            slept_time = 0
            while slept_time < wait_duration:
                if script_args.interactive: 
                     check_and_wait_if_paused(f"Attesa RPM ({wait_duration-slept_time:.1f}s rimanenti)")
                
                actual_sleep = min(sleep_chunk, wait_duration - slept_time)
                time.sleep(actual_sleep)
                slept_time += actual_sleep
                if not script_is_paused.is_set(): # Interrompe l'attesa se lo script viene messo in pausa
                    break 

def traduci_testo_csv(input_file, output_file, current_script_args):
    # Funzione principale per la traduzione di un singolo file CSV.
    global major_failure_count, model, user_command_skip_api, user_command_skip_file, script_is_paused
    
    stop_event = Event() 
    loader_thread = None
    if not current_script_args.oneThread: # Avvia animazione solo se non disabilitata
        loader_thread = Thread(target=animazione_caricamento, args=(stop_event,)) 
        loader_thread.start()

    righe_lette_total = 0
    righe_elaborate_per_traduzione = 0
    nome_file_corrente_basename = os.path.basename(input_file)
    nome_file_corrente_abs = os.path.abspath(input_file) 
    
    # Parametri estratti dagli argomenti per comodità
    delimiter = current_script_args.delimiter
    translate_col_index = current_script_args.translate_col
    output_col_index = current_script_args.output_col
    max_cols = current_script_args.max_cols
    file_encoding = current_script_args.encoding
    game_name_for_prompt = current_script_args.game_name
    source_lang_for_prompt = current_script_args.source_lang
    target_lang_for_prompt = current_script_args.target_lang
    translation_only_mode = current_script_args.translation_only_output
    wrap_at_length = current_script_args.wrap_at
    newline_sequence = current_script_args.newline_char 
    resume_active = current_script_args.resume

    output_open_mode = 'w'
    skip_input_data_rows_count = 0 
    skip_translatable_lines_count = 0 
    output_exists = os.path.exists(output_file)

    # Logica per la modalità --resume
    if resume_active and output_exists:
        output_open_mode = 'a' # Apre in append se il file di output esiste
        lines_in_existing_output = count_lines_in_file(output_file, file_encoding)
        
        if not translation_only_mode: # Modalità CSV completo
            if lines_in_existing_output > 0: 
                skip_input_data_rows_count = lines_in_existing_output - 1 # Salta l'header + righe già scritte
            else: 
                skip_input_data_rows_count = 0
            resume_msg_csv = f"Ripresa per file CSV '{nome_file_corrente_basename}': Trovate {lines_in_existing_output} righe nell'output. Si salteranno {skip_input_data_rows_count} righe di dati dall'input." 
            print(f"↪️  {resume_msg_csv}")
            write_to_log(f"INFO (Resume): File CSV '{nome_file_corrente_abs}' - {resume_msg_csv}")
        else: # Modalità solo traduzioni (un testo per riga)
            skip_translatable_lines_count = lines_in_existing_output 
            resume_msg_txt = f"Ripresa per file TXT '{nome_file_corrente_basename}': Trovate {lines_in_existing_output} traduzioni nell'output. Si salteranno {skip_translatable_lines_count} righe traducibili dall'input."
            print(f"↪️  {resume_msg_txt}")
            write_to_log(f"INFO (Resume): File TXT '{nome_file_corrente_abs}' - {resume_msg_txt}")

    try:
        with open(input_file, 'r', encoding=file_encoding, newline='') as infile, \
             open(output_file, output_open_mode, encoding=file_encoding, newline='') as outfile_handle:

            reader = csv.reader(infile, delimiter=delimiter)
            csv_writer = None 
            if not translation_only_mode:
                csv_writer = csv.writer(outfile_handle, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)

            input_header = next(reader, None) # Legge l'header
            if input_header:
                righe_lette_total += 1
                if csv_writer and output_open_mode == 'w': # Scrive l'header solo se si crea un nuovo file
                    csv_writer.writerow(input_header)
            
            current_data_row_index_processed = 0 
            current_translatable_lines_processed = 0 

            for row_number_in_data, row_data in enumerate(reader): 
                if script_args.interactive: check_and_wait_if_paused(f"File: {nome_file_corrente_basename}, Riga Dati: {row_number_in_data + 1}") 

                # Gestione comando 'skip file'
                with command_lock:
                    if user_command_skip_file:
                        print(f"⏭️  COMANDO 'skip file' per '{nome_file_corrente_basename}'. Interruzione di questo file.")
                        write_to_log(f"COMANDO UTENTE: File '{nome_file_corrente_abs}' saltato (inizio riga) causa 'skip file'.")
                        user_command_skip_file = False # Resetta il flag dopo l'uso
                        if loader_thread and loader_thread.is_alive(): stop_event.set(); loader_thread.join()
                        return

                righe_lette_total +=1
                display_row_number = row_number_in_data + 1 + (1 if input_header else 0) # Numero riga per output utente 
                translated_row = list(row_data) # Crea una copia modificabile della riga

                # Logica di salto per la modalità --resume
                if resume_active and output_exists:
                    if not translation_only_mode: 
                        if current_data_row_index_processed < skip_input_data_rows_count:
                            current_data_row_index_processed += 1
                            continue
                    else: 
                        # Per la modalità solo traduzioni, il conteggio si basa sui testi effettivamente traducibili
                        is_current_row_translatable_for_skip = isinstance(row_data[translate_col_index] if len(row_data) > translate_col_index else "", str) and \
                                                            (row_data[translate_col_index] if len(row_data) > translate_col_index else "").strip() and \
                                                            not ((row_data[translate_col_index] if len(row_data) > translate_col_index else "").isdigit() or \
                                                                re.match(r'^[\W_]+$', (row_data[translate_col_index] if len(row_data) > translate_col_index else "")) or \
                                                                "\\u" in (row_data[translate_col_index] if len(row_data) > translate_col_index else "") or \
                                                                (row_data[translate_col_index] if len(row_data) > translate_col_index else "") == " ") 
                        if is_current_row_translatable_for_skip:
                            if current_translatable_lines_processed < skip_translatable_lines_count:
                                current_translatable_lines_processed +=1 
                                continue
                
                if not row_data: # Salta righe vuote
                    if csv_writer: 
                        csv_writer.writerow([])
                    continue
                
                # Controllo opzionale sul numero massimo di colonne
                if max_cols is not None and len(row_data) > max_cols:
                    msg = f"File '{nome_file_corrente_basename}', Riga {display_row_number}: Supera num. max colonne ({len(row_data)} > {max_cols}). "
                    if csv_writer:
                        print(f"⚠️  {msg}Riga scritta invariata e saltata per traduzione.")
                        write_to_log(f"AVVISO: {msg}Riga scritta invariata e saltata per traduzione.")
                        csv_writer.writerow(row_data) 
                    else: 
                        print(f"⚠️  {msg}Riga saltata.")
                        write_to_log(f"AVVISO: {msg}Riga saltata.")
                    continue

                value_to_translate = ""
                if len(row_data) > translate_col_index:
                    value_to_translate = row_data[translate_col_index]

                # Determina se il testo deve essere tradotto
                # Esclude stringhe vuote, solo numeri, solo simboli, o contenenti sequenze \u errate
                should_translate = isinstance(value_to_translate, str) and value_to_translate.strip() and \
                                   not (value_to_translate.isdigit() or re.match(r'^[\W_]+$', value_to_translate) or "\\u" in value_to_translate or value_to_translate == " ") 
                
                if should_translate:
                    righe_elaborate_per_traduzione +=1
                    current_col_name_display = input_header[translate_col_index] if input_header and translate_col_index < len(input_header) else str(translate_col_index+1) 
                    
                    translation_successful_for_text = False
                    translated_text_content = "" 

                    while not translation_successful_for_text: # Loop per tentativi di traduzione
                        if script_args.interactive: check_and_wait_if_paused(f"File: {nome_file_corrente_basename}, Riga Dati: {row_number_in_data + 1}, Testo: '{value_to_translate[:20].replace(newline_sequence if isinstance(newline_sequence, str) else chr(10), ' ')}...'")
                        
                        # Gestione comando 'skip file' durante la traduzione
                        with command_lock: 
                            if user_command_skip_file:
                                print(f"⏭️  COMANDO 'skip file' per '{nome_file_corrente_basename}' durante traduzione testo. Interruzione file.")
                                write_to_log(f"COMANDO UTENTE: File '{nome_file_corrente_abs}' saltato (durante testo) causa 'skip file'.")
                                user_command_skip_file = False
                                if loader_thread and loader_thread.is_alive(): stop_event.set(); loader_thread.join() 
                                return
                        
                        # Gestione comando 'skip api'
                        with command_lock: 
                            if user_command_skip_api:
                                cmd_msg = f"COMANDO 'skip api'. Tento rotazione API per testo corrente..." 
                                print(f"   Comando Utente: {cmd_msg}") 
                                write_to_log(f"COMANDO UTENTE: {cmd_msg} File: {nome_file_corrente_abs} Riga: {display_row_number}")
                                if rotate_api_key(triggered_by_user=True):
                                    print(f"   Comando Utente: API key ruotata.")
                                else:
                                    print(f"   Comando Utente: Impossibile ruotare API key.")
                                user_command_skip_api = False 
                        
                        active_api_key_display = available_api_keys[current_api_key_index][-4:] if available_api_keys and available_api_keys[current_api_key_index] else "N/A"
                        
                        # Output formattato per il processo di traduzione
                        print(f"\n  --------------------------------------------------") 
                        print(f"  File: {nome_file_corrente_basename} | Riga: {display_row_number} | Col: {current_col_name_display}")
                        print(f"  API Key: ...{active_api_key_display}")
                        log_value_preview = value_to_translate.replace('\n', ' ').replace('\r', '')
                        print(f"  Originale ({source_lang_for_prompt}):\n    '{log_value_preview}'")
                        
                        for attempt in range(MAX_RETRIES_PER_API_CALL): # Loop per i tentativi con la stessa API key
                            try:
                                wait_for_rpm_limit() # Rispetta il limite RPM
                                
                                prompt = f"""Traduci il seguente testo da {source_lang_for_prompt} a {target_lang_for_prompt}, mantenendo il contesto del gioco '{game_name_for_prompt}' e preservando eventuali tag HTML, placeholder (come [p], {{player_name}}), o codici speciali. Rispondi solo con la traduzione diretta.
Testo originale:
{value_to_translate}

Traduzione in {target_lang_for_prompt}:""" 
                                
                                time.sleep(BASE_API_CALL_INTERVAL_SECONDS) 
                                response = model.generate_content(prompt)
                                translated_text_content = response.text.strip()
                                
                                # Applica word wrapping se richiesto
                                if wrap_at_length and wrap_at_length > 0 and translated_text_content:
                                    translated_text_content = textwrap.fill(
                                        translated_text_content, width=wrap_at_length,
                                        initial_indent='', subsequent_indent='',
                                        newline=newline_sequence, replace_whitespace=False,
                                        drop_whitespace=False, break_long_words=True,
                                        break_on_hyphens=True
                                    )
                                log_translation_preview = translated_text_content.replace(newline_sequence if isinstance(newline_sequence, str) else chr(10), ' ' )
                                print(f"    Tradotto ({target_lang_for_prompt}):\n      '{log_translation_preview}'")
                                translation_successful_for_text = True
                                major_failure_count = 0 # Resetta fallimenti dopo successo
                                break  

                            except Exception as e:
                                error_message_str = str(e) 
                                error_api_msg_console = f"Tentativo {attempt + 1}/{MAX_RETRIES_PER_API_CALL} (Key ...{active_api_key_display}) Errore API: {error_message_str}"
                                error_api_msg_log = f"File '{nome_file_corrente_abs}', Riga {display_row_number}, Tentativo {attempt + 1}/{MAX_RETRIES_PER_API_CALL} (Key ...{active_api_key_display}) per testo '{log_value_preview}...'. L'API ha restituito un errore."
                                print(f"    - {error_api_msg_console}")
                                write_to_log(f"ERRORE API: {error_api_msg_log}") 
                                
                                # Gestione del delay suggerito dall'API in caso di errore
                                retry_delay_seconds_to_use = DEFAULT_API_ERROR_RETRY_SECONDS 
                                match = re.search(r"retry_delay\s*{\s*seconds:\s*(\d+)\s*}", error_message_str, re.IGNORECASE)
                                if match:
                                    try:
                                        suggested_seconds = int(match.group(1))
                                        retry_delay_seconds_to_use = suggested_seconds + 1 # Aggiunge 1 secondo per sicurezza
                                        print(f"      API suggerisce ritardo di {suggested_seconds}s. Attendo {retry_delay_seconds_to_use}s.")
                                        write_to_log(f"INFO: Errore API per File '{nome_file_corrente_abs}' (Riga {display_row_number}) suggerisce ritardo di {suggested_seconds}s. Attesa: {retry_delay_seconds_to_use}s.")
                                    except ValueError:
                                        print(f"      Impossibile parsare retry_delay: '{match.group(1)}'. Uso fallback {retry_delay_seconds_to_use}s.")
                                        write_to_log(f"AVVISO: Impossibile parsare retry_delay per File '{nome_file_corrente_abs}' (Riga {display_row_number}). Fallback: {retry_delay_seconds_to_use}s.")
                                else:
                                    print(f"      Nessun suggerimento di retry_delay. Uso fallback {retry_delay_seconds_to_use}s.")
                                    
                                if attempt < MAX_RETRIES_PER_API_CALL - 1:
                                    print(f"      Riprovo tra {retry_delay_seconds_to_use} secondi...")
                                    time.sleep(retry_delay_seconds_to_use)
                        
                        # Se la traduzione fallisce dopo tutti i tentativi con la chiave corrente
                        if not translation_successful_for_text:
                            major_failure_count += 1
                            fail_msg_console = f"Traduzione fallita dopo {MAX_RETRIES_PER_API_CALL} tentativi con Key ...{active_api_key_display}."
                            fail_msg_log = f"File '{nome_file_corrente_abs}', Riga {display_row_number}, Traduzione fallita dopo {MAX_RETRIES_PER_API_CALL} tentativi con Key ...{active_api_key_display}."
                            print(f"    - {fail_msg_console}")
                            write_to_log(f"FALLIMENTO INTERMEDIO: {fail_msg_log}")
                            print(f"      Conteggio fallimenti maggiori per Key ...{active_api_key_display}: {major_failure_count}/{MAX_MAJOR_FAILURES_THRESHOLD}")
                            write_to_log(f"INFO: Conteggio fallimenti maggiori per Key ...{active_api_key_display}: {major_failure_count}/{MAX_MAJOR_FAILURES_THRESHOLD}")
                            
                            # Se si raggiunge la soglia di fallimenti, prova a ruotare la chiave API
                            if major_failure_count >= MAX_MAJOR_FAILURES_THRESHOLD:
                                if len(available_api_keys) > 1:
                                    rotate_msg = f"Soglia {MAX_MAJOR_FAILURES_THRESHOLD} fallimenti maggiori per Key ...{active_api_key_display}. Rotazione."
                                    print(f"    ROTazione API: {rotate_msg}")
                                    write_to_log(f"AVVISO: {rotate_msg}")
                                    if not rotate_api_key(): # Se la rotazione fallisce (es. errore con la nuova chiave)
                                        pause_msg = f"Rotazione API Key fallita. Pausa 60s..."
                                        print(f"    ATTENZIONE: {pause_msg}")
                                        write_to_log(f"AVVISO CRITICO: {pause_msg} (File: {nome_file_corrente_abs}, Riga {display_row_number})")
                                        time.sleep(60)
                                else: # Se c'è solo una chiave API e continua a fallire
                                    pause_msg_single_key = f"Unica API Key ...{active_api_key_display} continua a fallire (soglia {MAX_MAJOR_FAILURES_THRESHOLD}). Pausa 30s..."
                                    print(f"    ATTENZIONE: {pause_msg_single_key}")
                                    write_to_log(f"AVVISO CRITICO: {pause_msg_single_key} (File: {nome_file_corrente_abs}, Riga {display_row_number})")
                                    time.sleep(30)
                            else: # Se non si è ancora raggiunta la soglia, pausa breve prima di ritentare il blocco
                                pause_msg_retry_block = f"Pausa 15s prima di ritentare blocco traduzione con Key ...{active_api_key_display}..."
                                print(f"    Attesa: {pause_msg_retry_block}")
                                time.sleep(15)
                    
                    # Scrittura dell'output
                    if translation_only_mode:
                        outfile_handle.write(translated_text_content + "\n")
                    elif csv_writer: 
                        # Assicura che la riga abbia abbastanza colonne per l'output
                        if output_col_index >= len(translated_row):
                            translated_row.extend([""] * (output_col_index - len(translated_row) + 1))
                        translated_row[output_col_index] = translated_text_content
                
                if csv_writer:
                    csv_writer.writerow(translated_row)
                
                if should_translate: # Aggiunge un separatore visivo dopo un blocco di traduzione
                    print(f"  --------------------------------------------------")


    except FileNotFoundError:
        error_fnf = f"ERRORE CRITICO: File non trovato '{input_file}'. Impossibile procedere con questo file."
        print(f"🛑 {error_fnf}")
        write_to_log(error_fnf)
    except UnicodeDecodeError as e:
        error_ude = f"ERRORE DI ENCODING nel file '{nome_file_corrente_abs}' con encoding '{file_encoding}': {e}"
        print(f"🛑 {error_ude}")
        write_to_log(error_ude)
        print(f"ℹ️  Prova a specificare un encoding diverso con l'argomento --encoding (es. --encoding 'utf-16').")
    except IndexError as e: 
        error_idx = f"ERRORE DI INDICE nel file '{nome_file_corrente_abs}' (riga ~{righe_lette_total}): {e}. Controlla gli indici delle colonne e la struttura del CSV."
        print(f"🛑 {error_idx}")
        write_to_log(error_idx)
    except Exception as e:
        error_exc = f"ERRORE IMPREVISTO durante l'elaborazione del file '{nome_file_corrente_abs}': {e}"
        print(f"🛑 {error_exc}")
        write_to_log(error_exc)
    finally:
        # Assicura che l'animazione di caricamento venga fermata
        if loader_thread and loader_thread.is_alive(): 
            stop_event.set()
            loader_thread.join()
            sys.stdout.write("\r" + " " * 40 + "\r") 

    summary_msg_file = f"Riepilogo per il file '{os.path.basename(input_file)}': Righe lette (dati): {righe_lette_total-(1 if input_header else 0)}, Testi elaborati: {righe_elaborate_per_traduzione}"
    print(f"\n📄 {summary_msg_file}")


def traduci_tutti_csv_in_cartella_ricorsivo(current_script_args):
    # Scansiona la cartella di input ricorsivamente e traduce tutti i file CSV trovati.
    global user_command_skip_api, user_command_skip_file 
    base_input_dir = current_script_args.input
    start_time_total = time.time() 
    total_files_processed_count = 0
    total_csv_found_count = 0

    print(f"\n🚀  Inizio scansione ricorsiva dalla cartella base: '{base_input_dir}'")
    output_mode_desc = "Solo Traduzioni (.txt)" if current_script_args.translation_only_output else "CSV Completo (.csv)"
    wrap_desc = f"A capo a {current_script_args.wrap_at} con '{repr(current_script_args.newline_char)}'" if current_script_args.wrap_at and current_script_args.wrap_at > 0 else "Nessuno"
    rpm_desc = f"{current_script_args.rpm} richieste/minuto" if current_script_args.rpm and current_script_args.rpm > 0 else "Nessun limite RPM script"

    # Stampa un riepilogo della configurazione
    config_summary = (
        f"------------------------------------------------------------\n"
        f"          🛠️  Configurazione Globale Applicata 🛠️\n"
        f"------------------------------------------------------------\n"
        f"  Delimitatore CSV:         '{current_script_args.delimiter}'\n"
        f"  Colonna Testo Originale:  {current_script_args.translate_col}\n"
        f"  Colonna Testo Tradotto:   {current_script_args.output_col} (per output CSV)\n"
        f"  Encoding File:            '{current_script_args.encoding}'\n"
        f"  Modello Gemini:           '{current_script_args.model_name}'\n"
        f"  Contesto Gioco:           '{current_script_args.game_name}'\n"
        f"  Lingua Originale:         '{current_script_args.source_lang}'\n"
        f"  Lingua Destinazione:      '{current_script_args.target_lang}'\n"
        f"  Max Richieste/Minuto:     {rpm_desc}\n"
        f"  Modalità Output File:     '{output_mode_desc}'\n"
        f"  A Capo Automatico:        {wrap_desc}\n"
        f"  Ripresa Abilitata:        {'Sì' if current_script_args.resume else 'No'}\n"
        f"  Logging su File:          {'Abilitato ('+LOG_FILE_NAME+')' if current_script_args.enable_file_log else 'Disabilitato'}\n"
        f"  Modalità Interattiva:     {'ATTIVA' if current_script_args.interactive else 'NON ATTIVA'}\n"
        f"  Animazione Caricamento:   {'Disabilitata' if current_script_args.oneThread else 'Abilitata'}\n"
        f"------------------------------------------------------------"
    )
    print(config_summary)

    for root, dirs, files in os.walk(base_input_dir, topdown=True):
        if script_args.interactive: check_and_wait_if_paused(f"Scansione cartella: {root}")

        with command_lock:
            if user_command_skip_file: 
                # Se skip_file è attivo a livello di cartella, i file al suo interno non vengono processati
                # da questa iterazione del loop sui file. Il flag viene resettato in traduci_testo_csv
                # o quando un file viene effettivamente saltato.
                pass 

        # Esclude le cartelle 'tradotto' dalla scansione per evitare di riprocessare l'output
        if "tradotto" in dirs:
            dirs.remove("tradotto") 
        
        normalized_root = os.path.normpath(root)
        is_tradotto_folder_to_skip = (os.path.basename(normalized_root) == "tradotto" or 
                                      f"{os.sep}tradotto{os.sep}" in f"{os.sep}{normalized_root}{os.sep}" or
                                      normalized_root.endswith(f"{os.sep}tradotto"))
        if is_tradotto_folder_to_skip and normalized_root != os.path.normpath(base_input_dir):
            continue

        csv_files_in_current_dir = [f for f in files if f.endswith('.csv')]
        
        if not csv_files_in_current_dir:
            continue 

        print(f"\n📂 Esplorando cartella: '{root}'")
        print(f"   ▶️  Trovati {len(csv_files_in_current_dir)} file CSV da analizzare.")
        total_csv_found_count += len(csv_files_in_current_dir)

        # Crea la sottocartella 'tradotto' se non esiste
        output_subfolder_for_this_root = os.path.join(root, "tradotto")
        if not os.path.exists(output_subfolder_for_this_root):
            try:
                os.makedirs(output_subfolder_for_this_root)
                created_dir_msg = f"Creata sotto-cartella di output: '{output_subfolder_for_this_root}'"
                print(f"   ✅ {created_dir_msg}")
                write_to_log(f"INFO: {created_dir_msg}")
            except OSError as e:
                error_msg_dir = f"Impossibile creare la cartella di output '{output_subfolder_for_this_root}': {e}. File in questa cartella verranno saltati."
                print(f"   ❌ {error_msg_dir}")
                write_to_log(f"ERRORE: {error_msg_dir}")
                continue 

        # Processa ciascun file CSV trovato
        for filename_csv in csv_files_in_current_dir:
            if script_args.interactive: check_and_wait_if_paused(f"Inizio file: {filename_csv} in {root}")
            
            with command_lock: 
                if user_command_skip_file: # Salta il file se il comando è attivo
                    skip_msg = f"COMANDO 'skip file' attivo. Salto il file '{filename_csv}' in '{root}'."
                    print(f"⏭️  {skip_msg}")
                    write_to_log(f"COMANDO UTENTE: {skip_msg}")
                    user_command_skip_file = False # Resetta il flag
                    continue 

            file_processing_start_time = time.time()
            input_file_path_abs = os.path.abspath(os.path.join(root, filename_csv)) 
            
            output_filename_base, input_ext = os.path.splitext(filename_csv)
            output_final_filename = filename_csv 
            if current_script_args.translation_only_output: # Nome file diverso per output solo traduzioni
                output_final_filename = f"{output_filename_base}_trads_only.txt"
            
            output_file_path_abs = os.path.abspath(os.path.join(output_subfolder_for_this_root, output_final_filename))
            
            if current_script_args.resume and os.path.exists(output_file_path_abs):
                print(f"↪️  File di output '{output_file_path_abs}' esiste. La modalità Resume tenterà di continuare dall'interno del file.")
                write_to_log(f"INFO (Resume): Trovato file di output esistente '{output_file_path_abs}'. Si tenterà la ripresa interna.")

            print(f"\n🚧 Inizio elaborazione file: '{input_file_path_abs}'")
            write_to_log(f"AVVIO FILE: Inizio elaborazione di '{input_file_path_abs}'")
            
            traduci_testo_csv(input_file_path_abs, output_file_path_abs, current_script_args) # Chiamata alla funzione di traduzione
            
            file_processing_elapsed_time = time.time() - file_processing_start_time
            total_elapsed_time_cumulative = time.time() - start_time_total
            
            log_entry_file_done = (f"COMPLETATO FILE (o saltato da utente durante l'elaborazione):\n"
                                   f"     Sorgente: '{input_file_path_abs}'\n"
                                   f"     Output:   '{output_file_path_abs}'\n"
                                   f"     Tempo per questo file: {format_time_delta(file_processing_elapsed_time)}\n"
                                   f"     Durata Totale Esecuzione: {format_time_delta(total_elapsed_time_cumulative)}")
            print(f"   💾 File di output: '{output_file_path_abs}'")
            print(f"   ⏱️  Tempo per questo file: {format_time_delta(file_processing_elapsed_time)}")
            write_to_log(log_entry_file_done) 
            total_files_processed_count += 1

    final_summary_start_time = time.time() 
    elapsed_time_total_final = final_summary_start_time - start_time_total
    
    # Riepilogo finale
    current_newline_char = current_script_args.newline_char if isinstance(current_script_args.newline_char, str) else '\n' 
    summary_end_msg = (f"Scansione e traduzione ricorsiva completata.\n"
                       f"     📑 Totale file CSV trovati (escluse cartelle 'tradotto'): {total_csv_found_count}\n"
                       f"     🗂️  Totale file elaborati (o tentati/saltati): {total_files_processed_count}\n"
                       f"     ⏳ Tempo totale di esecuzione complessivo: {format_time_delta(elapsed_time_total_final)}")
    print(f"\n🏁 {summary_end_msg}")
    write_to_log(f"SOMMARIO FINALE: {summary_end_msg.replace(current_newline_char, ' // ')}")


if __name__ == "__main__":
    # Punto di ingresso principale dello script
    print(ALUMEN_ASCII_ART) 
    print("Benvenuto in Alumen - Traduttore Automatico Multilingua!\n")
    
    args_parsed = get_script_args_updated() 
    script_is_paused.set() # Assicura che lo script parta non in pausa
    
    if args_parsed.enable_file_log: 
        setup_log_file()
        
    initialize_api_keys_and_model() # Carica API keys e inizializza il modello

    # Controlli sulla validità della cartella di input
    if not os.path.exists(args_parsed.input):
        err_msg = f"Errore: La cartella di input base '{args_parsed.input}' non esiste. Script interrotto."
        print(f"🛑 {err_msg}")
        write_to_log(f"ERRORE CRITICO: {err_msg}")
        sys.exit(1)
    if not os.path.isdir(args_parsed.input):
        err_msg = f"Errore: Il percorso di input base '{args_parsed.input}' non è una cartella. Script interrotto."
        print(f"🛑 {err_msg}")
        write_to_log(f"ERRORE CRITICO: {err_msg}")
        sys.exit(1)

    main_log_start_msg = f"Cartella di input base selezionata: '{os.path.abspath(args_parsed.input)}'"
    print(f"\n📁 {main_log_start_msg}")
    write_to_log(f"INFO: {main_log_start_msg}")
    print(f"ℹ️  Le sottocartelle 'tradotto' verranno create dinamicamente all'interno di ogni directory processata.")
    
    # Avvia il thread per i comandi interattivi, se abilitato
    command_thread = None
    if args_parsed.interactive:
        command_thread = threading.Thread(target=command_input_thread_func, daemon=True)
        command_thread.start()

    try:
        traduci_tutti_csv_in_cartella_ricorsivo(args_parsed) # Avvia il processo principale
    except KeyboardInterrupt: # Gestione interruzione da utente (Ctrl+C)
        print("\n🛑 Interruzione da tastiera (Ctrl+C) ricevuta nel thread principale. Uscita in corso...")
        write_to_log("INTERRUZIONE: Script interrotto da tastiera (Ctrl+C).")
        with command_lock: 
            user_command_skip_file = True # Tenta di saltare il file corrente per un'uscita più pulita
    finally:
        # Operazioni finali prima di terminare
        if script_args.interactive and command_thread and command_thread.is_alive():
            print("ℹ️  Il thread di input comandi è ancora attivo (terminerà con lo script).")

        write_to_log(f"--- FINE Sessione di Log: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        print("\n🎉 Script Alumen terminato. Arrivederci!")