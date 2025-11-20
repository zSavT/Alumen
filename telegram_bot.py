import logging
import json
import threading
import asyncio
import sys
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, JobQueue

# Importa il Core per accedere allo stato globale
try:
    import AlumenCore
except ImportError:
    print("Errore: AlumenCore.py non trovato nella stessa directory.")
    sys.exit(1)

# --- Globali ---
bot_app = None
CHAT_ID = None

# --- Log Handler ---
class TelegramLogHandler(logging.Handler):
    def __init__(self, application, chat_id):
        super().__init__()
        self.app = application
        self.cid = chat_id

    def emit(self, record):
        if any(x in record.name for x in ["httpx", "telegram", "apscheduler"]): return
        msg = self.format(record)
        if self.app.job_queue:
            self.app.job_queue.run_once(lambda c: c.bot.send_message(chat_id=self.cid, text=msg), 0)

# --- Command Processor Interno ---
def execute_core_command(command: str):
    """
    Esegue comandi agendo direttamente su AlumenCore.
    Poiché AlumenCore 2.0 non ha un processore comandi, lo simuliamo qui.
    """
    cmd_parts = command.strip().lower().split(maxsplit=1)
    cmd = cmd_parts[0]
    
    if cmd == "stop":
        if AlumenCore.global_stop_event: AlumenCore.global_stop_event.set()
        return "🛑 Stop richiesto. Terminazione in corso..."
    elif cmd == "pause":
        if AlumenCore.global_pause_event: AlumenCore.global_pause_event.clear()
        return "⏸️ Processo in pausa."
    elif cmd == "resume":
        if AlumenCore.global_pause_event: AlumenCore.global_pause_event.set()
        return "▶️ Processo ripreso."
    elif cmd == "skip":
        sub_cmd = cmd_parts[1] if len(cmd_parts) > 1 else ""
        if sub_cmd == "file":
            if AlumenCore.global_skip_event: AlumenCore.global_skip_event.set()
            return "⏭️ Salto del file corrente richiesto."
        elif sub_cmd == "api":
            AlumenCore.log_msg("🔄 Rotazione API Key richiesta da Telegram...")
            if AlumenCore.script_args_global:
                AlumenCore.rotate_key(AlumenCore.script_args_global)
                return "✅ API Key ruotata."
            return "⚠️ Impossibile ruotare la chiave: script non inizializzato."
        else:
            return "Comando non riconosciuto. Usa `/skip file` o `/skip api`."

    elif cmd == "status" or cmd == "stats":
        # Usa la nuova funzione per statistiche complete
        if hasattr(AlumenCore, '_get_full_stats_text'):
            return AlumenCore._get_full_stats_text(is_telegram=True)
        return "Funzione statistiche non disponibile."

    elif cmd == "help":
        return (
            "🤖 *Comandi Disponibili:*\n"
            "`/stats` o `/status` - Mostra statistiche\n"
            "`/stop` - Ferma il processo\n"
            "`/pause` - Mette in pausa\n"
            "`/resume` - Riprende il processo\n"
            "`/skip file` o `/skip api` - Salta file o ruota API\n"
            "I log verranno inviati qui automaticamente."
        )
    
    return "Comando non riconosciuto. Usa /help."

# --- Handler Telegram ---
async def generic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt.startswith('/'): txt = txt[1:]
    
    AlumenCore.log_msg(f"[Telegram] Comando ricevuto: {txt}")
    response = execute_core_command(txt)
    await update.message.reply_text(response, parse_mode="Markdown")

# --- Public API ---
def send_telegram_notification(msg):
    if bot_app and bot_app.job_queue:
        bot_app.job_queue.run_once(lambda c: c.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown"), 0)

def start_bot():
    global bot_app, CHAT_ID
    try:
        with open("telegram_config.json", "r") as f:
            cfg = json.load(f)
            token = cfg.get("bot_token")
            CHAT_ID = cfg.get("chat_id")
    except:
        print("⚠️ telegram_config.json mancante.")
        return None

    if not token or not CHAT_ID: return None

    jq = JobQueue()
    bot_app = Application.builder().token(token).job_queue(jq).build()

    # Log redirection
    h = TelegramLogHandler(bot_app, CHAT_ID)
    h.setFormatter(logging.Formatter('ℹ️ %(message)s'))
    logging.getLogger().addHandler(h)

    bot_app.add_handler(MessageHandler(filters.TEXT, generic_handler))

    t = threading.Thread(target=bot_app.run_polling, daemon=True)
    t.start()
    
    print("✅ Telegram Bot Avviato.")
    send_telegram_notification("🚀 *Alumen Core Avviato!*")
    return bot_app

def stop_bot():
    global bot_app
    if not bot_app: return
    print("Arresto Telegram...")
    
    loop = bot_app.loop
    if loop and loop.is_running():
        async def bye():
            await bot_app.bot.send_message(chat_id=CHAT_ID, text="🏁 Script Terminato.")
            await bot_app.shutdown()
        try:
            future = asyncio.run_coroutine_threadsafe(bye(), loop)
            future.result(timeout=5)
        except: pass
