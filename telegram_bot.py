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
    cmd = command.strip().lower()
    
    if cmd == "stop":
        # Cerca un evento di stop nel Core (assumendo che venga passato o sia globale)
        # Nel codice Core fornito, stop_event è passato ai thread.
        # Per semplicità, qui solleviamo un flag globale se esiste, o usiamo sys.exit come fallback brutale se necessario,
        # ma cerchiamo di essere gentili.
        
        # Nota: AlumenCore.py non espone 'stop_event' globalmente al modulo, ma 
        # possiamo provare a usare graceful_exit_requested se definito, o forzare l'uscita.
        # Soluzione: AlumenCore dovrebbe avere un flag globale. Se non c'è, questo comando è limitato.
        # Assumiamo che l'utente abbia usato lo script AlumenCore fornito che NON ha un stop_event globale esposto.
        # Tuttavia, possiamo iniettare un'eccezione o messaggio.
        
        return "⚠️ Il comando Stop via Telegram richiede che lo script sia in modalità GUI o supporti l'evento globale."

    elif cmd == "status" or cmd == "stats":
        # Legge variabili globali di AlumenCore
        try:
            files = AlumenCore.total_files_translated
            keys = len(AlumenCore.available_api_keys)
            curr_k = AlumenCore.current_api_key_index
            cache = len(AlumenCore.translation_cache)
            return (
                f"📊 *STATO ALUMEN*\n"
                f"✅ File Tradotti: `{files}`\n"
                f"🔑 API Keys attive: `{keys}` (Indice corrente: `{curr_k}`)\n"
                f"💾 Voci in Cache: `{cache}`"
            )
        except Exception as e:
            return f"Errore lettura stato: {e}"
            
    elif cmd == "skip":
        # Questo è difficile senza accesso al lock del thread specifico.
        return "⚠️ Il comando Skip non è disponibile in questa versione 'Core'."

    elif cmd == "help":
        return (
            "🤖 *Comandi Disponibili:*\n"
            "`/status` - Mostra statistiche traduzione\n"
            "`/stop` - (Non disponibile in Core-only mode)\n"
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
    
    # Shutdown asincrono hacky per thread sincrono
    loop = bot_app.loop
    if loop and loop.is_running():
        async def bye():
            await bot_app.bot.send_message(chat_id=CHAT_ID, text="🏁 Script Terminato.")
            await bot_app.shutdown()
        asyncio.run_coroutine_threadsafe(bye(), loop)    # Aggiungi un unico gestore per tutti i messaggi di testo
    bot_app.add_handler(MessageHandler(filters.TEXT, generic_command_handler))

    bot_thread = threading.Thread(target=bot_app.run_polling, daemon=True)
    bot_thread.start()
    
    Alumen.console.print("[bold green]✅ Bot Telegram attivo e in ascolto.[/]")
    
    bot_app.job_queue.run_once(
        lambda context: context.bot.send_message(chat_id=CHAT_ID, text="🚀 Script Alumen avviato! Il logging e i comandi sono attivi."),
        1
    )
    
    return bot_app

def stop_bot():
    """
    Arresta il bot di Telegram in modo controllato, gestendo i timeout di rete
    per evitare che lo script si blocchi durante la chiusura.
    """
    global bot_app
    if not bot_app:
        return

    # Controlla se il bot è effettivamente in esecuzione
    if not bot_app.updater or not bot_app.updater._running: # <--- MODIFICA QUI
        Alumen.console.print("ℹ️  Il bot di Telegram non era in esecuzione.", style="yellow")
        return

    Alumen.console.print("🤖 Arresto del bot Telegram in corso...", style="telegram")

    # Ottieni l'event loop asyncio del bot, che è già in esecuzione
    loop = bot_app.loop

    async def shutdown_with_timeout():
        """ Coroutine che esegue lo shutdown con un timeout di sicurezza. """
        try:
            # Invia il messaggio di chiusura
            if bot_app.job_queue:
                await bot_app.bot.send_message(chat_id=CHAT_ID, text="🛑 Script Alumen terminato.")
            
            # Diamo al processo di shutdown della libreria un massimo di 5 secondi per completarsi.
            await asyncio.wait_for(bot_app.shutdown(), timeout=5.0)
            Alumen.console.print("   - Shutdown pulito del bot completato.", style="telegram")
        except asyncio.TimeoutError:
            Alumen.console.print("⚠️  Timeout durante lo shutdown del bot. La chiusura potrebbe non essere pulita.", style="yellow")
        except Exception as e:
            Alumen.console.print(f"⚠️  Errore non gestito durante lo shutdown del bot: {e}", style="yellow")

    # Poiché stop_bot() è sincrona, scheduliamo la coroutine asincrona
    # sull'event loop del bot in modo sicuro tra i thread.
    if loop and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(shutdown_with_timeout(), loop)
        
        try:
            # Attendi il completamento del future, ma con un timeout per non bloccare tutto.
            future.result(timeout=6.0)
        except TimeoutError:
            Alumen.console.print("⚠️  La procedura di shutdown di Telegram non è terminata in tempo, ma lo script principale continuerà.", style="yellow")
        except Exception as e:
            Alumen.console.print(f"⚠️  Errore nell'attesa del risultato dello shutdown: {e}", style="yellow")
    else:
        Alumen.console.print("⚠️  L'event loop del bot non è in esecuzione. Impossibile eseguire uno shutdown pulito.", style="yellow")
