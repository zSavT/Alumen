import logging
import json
import threading
import asyncio
import sys
import time
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Tenta di importare JobQueue, ma gestisce l'assenza della dipendenza extra
try:
    from telegram.ext import JobQueue
    JOB_QUEUE_AVAILABLE = True
except ImportError:
    JobQueue = None
    JOB_QUEUE_AVAILABLE = False

# Importa il Core per accedere allo stato globale
try:
    import AlumenCore
except ImportError:
    print("Errore: AlumenCore.py non trovato nella stessa directory.")
    sys.exit(1)

# --- Globali ---
bot_app = None
CHAT_ID = None
bot_loop = None # Riferimento al loop del bot

# --- Log Handler ---
class TelegramLogHandler(logging.Handler):
    def __init__(self, application, chat_id):
        super().__init__()
        self.app = application
        self.cid = chat_id

    def emit(self, record):
        if any(x in record.name for x in ["httpx", "telegram", "apscheduler"]): return
        msg = self.format(record)
        # Usa JobQueue se disponibile, altrimenti prova fallback su loop
        if self.app.job_queue:
            self.app.job_queue.run_once(lambda c: c.bot.send_message(chat_id=self.cid, text=msg), 0)
        elif bot_loop and bot_loop.is_running():
             asyncio.run_coroutine_threadsafe(self.app.bot.send_message(chat_id=self.cid, text=msg), bot_loop)

# --- Command Processor Interno ---
def execute_core_command(command: str):
    """
    Esegue comandi agendo direttamente su AlumenCore.
    """
    cmd = command.strip().lower()
    
    if cmd == "stop":
        if AlumenCore.graceful_exit_requested:
            AlumenCore.graceful_exit_requested.set()
            return "🛑 Richiesta di STOP ricevuta. Il processo terminerà alla fine del file corrente."
        else:
            return "⚠️ Impossibile eseguire STOP: evento non inizializzato."

    elif cmd == "status" or cmd == "stats":
        try:
            files = AlumenCore.total_files_translated
            entries = AlumenCore.total_entries_translated
            keys = len(AlumenCore.available_api_keys)
            curr_k = AlumenCore.current_api_key_index
            cache = len(AlumenCore.translation_cache)
            
            # Nuove Statistiche
            tok_in = AlumenCore.total_input_tokens
            tok_out = AlumenCore.total_output_tokens
            api_calls = sum(AlumenCore.api_call_counts.values())
            
            elapsed_str = "0s"
            if AlumenCore.start_time > 0:
                elapsed = int(AlumenCore.get_elapsed_time())
                h, r = divmod(elapsed, 3600)
                m, s = divmod(r, 60)
                elapsed_str = f"{h}h {m}m {s}s"
            
            shutdown_status = "🔴 OFF"
            if AlumenCore.script_args and hasattr(AlumenCore.script_args, 'shutdown') and AlumenCore.script_args.shutdown:
                shutdown_status = "🟢 ON"

            return (
                f"📊 *STATO ALUMEN*\n"
                f"⏳ Tempo: `{elapsed_str}`\n"
                f"✅ File Tradotti: `{files}`\n"
                f"📝 Entry Tradotte: `{entries}`\n"
                f"📞 Chiamate API: `{api_calls}`\n"
                f"🔢 Token In/Out: `{tok_in}` / `{tok_out}`\n"
                f"🔑 API Keys attive: `{keys}` (Idx: `{curr_k}`)\n"
                f"💾 Voci in Cache: `{cache}`\n"
                f"🔌 Auto-Shutdown: {shutdown_status}"
            )
        except Exception as e:
            return f"Errore lettura stato: {e}"
            
    elif cmd == "skip" or cmd == "skip file":
        with AlumenCore.command_lock:
            AlumenCore.user_command_skip_file = True
        return "⏭️ Richiesta di SKIP FILE ricevuta. Passo al file successivo..."

    elif cmd == "skip api":
        with AlumenCore.command_lock:
            AlumenCore.user_command_skip_api = True
        return "⏭️🔑 Richiesta di SKIP API ricevuta. Ruoto la chiave..."

    elif cmd == "shutdown":
        if AlumenCore.script_args:
            # Toggle shutdown state
            current_state = getattr(AlumenCore.script_args, 'shutdown', False)
            new_state = not current_state
            AlumenCore.script_args.shutdown = new_state
            status_icon = "🟢 ON" if new_state else "🔴 OFF"
            return f"🔌 Spegnimento automatico PC impostato su: {status_icon}"
        else:
            return "⚠️ Impossibile modificare shutdown: argomenti non inizializzati."

    elif cmd == "help":
        return (
            "🤖 *Comandi Disponibili:*\n"
            "`/status` - Mostra statistiche complete\n"
            "`/stop` - Ferma il processo in modo sicuro\n"
            "`/skip` - Salta il file corrente\n"
            "`/skip api` - Forza rotazione API Key\n"
            "`/shutdown` - Attiva/Disattiva spegnimento PC\n"
            "I log verranno inviati qui automaticamente."
        )
    
    return "Comando non riconosciuto. Usa /help."

# --- Handler Telegram ---
async def generic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt.startswith('/'): txt = txt[1:]
    
    # Logga il comando ricevuto usando la funzione corretta del Core
    try:
        AlumenCore.write_to_log(f"[Telegram] Comando ricevuto: {txt}")
    except AttributeError:
        pass # Fallback se la funzione non esiste ancora
    
    response = execute_core_command(txt)
    await update.message.reply_text(response, parse_mode="Markdown")

# --- Public API ---
def send_telegram_notification(msg):
    if not bot_app: return
    
    if bot_app.job_queue:
        bot_app.job_queue.run_once(lambda c: c.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown"), 0)
    elif bot_loop and bot_loop.is_running():
        # Fallback senza JobQueue
        asyncio.run_coroutine_threadsafe(bot_app.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown"), bot_loop)

def _run_bot_thread(token):
    global bot_app, bot_loop
    
    # Crea un nuovo loop per questo thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot_loop = loop
    
    builder = Application.builder().token(token)
    
    # Se JobQueue è disponibile e installata correttamente, usala
    if JOB_QUEUE_AVAILABLE:
        try:
            jq = JobQueue()
            builder.job_queue(jq)
        except RuntimeError:
            print("⚠️ Libreria 'python-telegram-bot[job-queue]' non completa. Disabilito JobQueue.")
            builder.job_queue(None)
    else:
        builder.job_queue(None)
        
    bot_app = builder.build()

    # Log redirection
    h = TelegramLogHandler(bot_app, CHAT_ID)
    h.setFormatter(logging.Formatter('ℹ️ %(message)s'))
    logging.getLogger().addHandler(h)

    bot_app.add_handler(MessageHandler(filters.TEXT, generic_handler))

    # Avvia il polling nel loop corrente
    print("✅ Telegram Bot Avviato.")
    
    # Notifica di avvio (dobbiamo farlo qui perché siamo nel loop)
    loop.run_until_complete(bot_app.bot.send_message(chat_id=CHAT_ID, text="🚀 *Alumen Core Avviato!*", parse_mode="Markdown"))
    
    bot_app.run_polling(stop_signals=None) # Disabilita gestione segnali per evitare conflitti col main thread

def start_bot(args=None):
    global CHAT_ID
    token = None
    CHAT_ID = None

    # 1. Prova a leggere da args (priorità)
    if args:
        if hasattr(args, 'telegram_token') and args.telegram_token:
            token = args.telegram_token
        if hasattr(args, 'telegram_chat_id') and args.telegram_chat_id:
            CHAT_ID = args.telegram_chat_id

    # 2. Se mancano, prova dal file di config
    if not token or not CHAT_ID:
        try:
            with open("telegram_config.json", "r") as f:
                cfg = json.load(f)
                if not token: token = cfg.get("bot_token")
                if not CHAT_ID: CHAT_ID = cfg.get("chat_id")
        except:
            pass

    if not token or not CHAT_ID:
        print("⚠️ Configurazione Telegram incompleta (Token o Chat ID mancanti).")
        return None

    t = threading.Thread(target=_run_bot_thread, args=(token,), daemon=True)
    t.start()
    
    return "BotStarted" # Ritorna un placeholder, l'app reale è in bot_app

def stop_bot():
    global bot_app, bot_loop
    if not bot_app or not bot_loop: return
    print("Arresto Telegram...")
    
    if bot_loop.is_running():
        async def bye():
            try:
                await bot_app.bot.send_message(chat_id=CHAT_ID, text="🏁 Script Terminato.")
                await bot_app.shutdown()
                await bot_app.stop()
            except: pass
        asyncio.run_coroutine_threadsafe(bye(), bot_loop)
