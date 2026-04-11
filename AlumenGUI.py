# --- START OF FILE AlumenGUI.py ---
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import queue
import os
import json
import time
import AlumenCore

# --- THEME CONFIGURATION (Full Dark Mode) ---
C_ACCENT = "#0078D7"          
C_ACCENT_HOVER = "#1984D8"
C_SIDEBAR_BG = "#151515"      
C_SIDEBAR_BTN_ACTIVE = "#252526"
C_MAIN_BG = "#1E1E1E"         
C_CARD_BG = "#252526"         
C_TEXT_MAIN = "#E0E0E0"
C_TEXT_SEC = "#9E9E9E"
C_TEXT_SIDEBAR = "#AAAAAA"
C_TEXT_SIDEBAR_ACT = "#FFFFFF"
C_BORDER = "#3E3E42"
C_INPUT_BG = "#333337"

# Semantic Colors
C_SUCCESS = "#107C10"
C_WARN = "#D83B01"
C_ERR = "#A80000"

# Fonts
FONT_FAM = "Segoe UI"
F_H1 = (FONT_FAM, 22, "bold")
F_H2 = (FONT_FAM, 12, "bold")
F_BODY = (FONT_FAM, 10)
F_SMALL = (FONT_FAM, 9)
F_MONO = ("Consolas", 10)
F_SIDEBAR = (FONT_FAM, 11)
F_STATS = (FONT_FAM, 14, "bold")

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)
    def show_tip(self, event=None):
        if self.tipwindow or not self.text: return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + 25
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                       background="#151515", foreground="#E0E0E0",
                       relief=tk.SOLID, borderwidth=1, font=F_SMALL, padx=10, pady=6)
        label.pack()
    def hide_tip(self, event=None):
        if self.tipwindow: self.tipwindow.destroy(); self.tipwindow = None

class PlaceholderEntry(ttk.Entry):
    def __init__(self, container, placeholder, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.placeholder = placeholder
        self.is_active = False
        self.bind("<FocusIn>", self._foc_in)
        self.bind("<FocusOut>", self._foc_out)
        self._foc_out(None)
    def _foc_in(self, event):
        if str(self['state']) == 'disabled': return
        if not self.is_active:
            self.delete(0, tk.END)
            self.config(foreground=C_TEXT_MAIN)
            self.is_active = True
    def _foc_out(self, event):
        if not self.get():
            self.insert(0, self.placeholder)
            self.config(foreground=C_TEXT_SEC)
            self.is_active = False
        else:
            self.is_active = True
    def get_valid_value(self):
        return self.get() if self.is_active else ""
    def set_text(self, text):
        self.delete(0, tk.END)
        self.config(foreground=C_TEXT_MAIN)
        self.insert(0, text)
        self.is_active = True

class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg=C_MAIN_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, style='TFrame')
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.scrollable_frame.bind('<Enter>', self._bind_mouse)
        self.scrollable_frame.bind('<Leave>', self._unbind_mouse)
    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    def _bind_mouse(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
    def _unbind_mouse(self, event):
        self.canvas.unbind_all("<MouseWheel>")
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

class AlumenGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Alumen v2.6.2 - AI Translation Suite")
        self.root.geometry("1280x950")
        self.root.configure(bg=C_MAIN_BG)
        
        # --- Sistema i18n (Multi-Lingua) ---
        self.current_lang = "it"
        self.translations = {
            "it": {}, # L'Italiano è la lingua base hardcoded
            "en": {
                "⚙️  Configurazione": "⚙️  Configuration",
                "🧠  Avanzate": "🧠  Advanced",
                "🔑  Gestione API": "🔑  API Management",
                "🛠️  Strumenti": "🛠️  Tools",
                "🚀  Esecuzione": "🚀  Execution",
                "Configurazione Progetto": "Project Configuration",
                "Motore di Traduzione": "Translation Engine",
                "Google Gemini (Cloud)": "Google Gemini (Cloud)",
                "Ollama (Locale)": "Ollama (Local)",
                "API Key": "API Key",
                "📂 Load .txt": "📂 Load .txt",
                "Modello": "Model",
                "Host URL": "Host URL",
                "Modello Locale": "Local Model",
                "Parametri Traduzione": "Translation Parameters",
                "Lingua Sorgente": "Source Language",
                "Lingua Target": "Target Language",
                "Contesto Gioco / Progetto": "Game / Project Context",
                "Gestione File": "File Management",
                "Cartella Input": "Input Folder",
                "Cartella Output": "Output Folder",
                "Sfoglia": "Browse",
                "Formato File": "File Format",
                "Encoding": "Encoding",
                "Notifiche Telegram": "Telegram Notifications",
                "Abilita Notifiche": "Enable Notifications",
                "Bot Token": "Bot Token",
                "Chat ID": "Chat ID",
                "Impostazioni Avanzate": "Advanced Settings",
                "Specifiche Formato": "Format Specifications",
                "Delimitatore CSV": "CSV Delimiter",
                "Indice Col. Origine (0=A)": "Source Col Index (0=A)",
                "Indice Col. Destinazione": "Target Col Index",
                "Limite Max Colonne": "Max Columns Limit",
                "Chiavi JSON da Tradurre": "JSON Keys to Translate",
                "Corrispondenza Percorso Esatto": "Exact Path Match",
                "Lettera Col. Origine (es. A,C)": "Source Col Letter (e.g. A,C)",
                "Lettera Col. Destinaz. (es. B,D)": "Target Col Letter (e.g. B,D)",
                "Prompt Engineering": "Prompt Engineering",
                "Custom Prompt (SOVRASCRIVE regole base)": "Custom Prompt (OVERWRITES base rules)",
                "Contesto Fisso (Aggiunta rapida)": "Fixed Context (Quick Add)",
                "Analisi Preliminare File (Auto-Context)": "File Preliminary Analysis (Auto-Context)",
                "Full Sample (Più lento)": "Full Sample (Slower)",
                "Logica & Performance": "Logic & Performance",
                "Salva Cache": "Save Cache",
                "Auto-Rotazione API": "Auto-Rotate API",
                "Solo Output .txt": "Text Output Only",
                "Server Mode": "Server Mode",
                "Resume (Salta fatti)": "Resume (Skip done)",
                "File Log (log.txt)": "File Log (log.txt)",
                "Agentic Reflection": "Agentic Reflection",
                "Fuzzy Match Cache": "Fuzzy Match Cache",
                "Spegnimento Auto": "Auto Shutdown",
                "Upload a Gemini": "Upload to Gemini",
                "Glossario CSV": "CSV Glossary",
                "Style Guide (.txt - Manuale Regole)": "Style Guide (.txt - Rulebook)",
                "File Cache JSON": "JSON Cache File",
                "Gestione Chiavi API": "API Key Management",
                "Chiavi Caricate": "Loaded Keys",
                "Stato": "Status",
                "Chiamate": "Calls",
                "➕ Aggiungi": "➕ Add",
                "🗑️ Rimuovi Selez.": "🗑️ Remove Sel.",
                "🚫 Blacklist": "🚫 Blacklist",
                "✅ Reset Tutte": "✅ Reset All",
                "🔄 Aggiorna Lista": "🔄 Refresh List",
                "Strumenti di Utilità": "Utility Tools",
                "Analisi e Preventivo": "Analysis and Estimate",
                "Abilita Modalità Dry Run": "Enable Dry Run Mode",
                "Avvia Analisi Dry Run": "Start Dry Run Analysis",
                "Estrattore Cache": "Cache Extractor",
                "Cartella Originali": "Original Folder",
                "Cartella Tradotti": "Translated Folder",
                "Formato:": "Format:",
                "Esegui Estrazione": "Run Extraction",
                "Auto-Glossary Scanner": "Auto-Glossary Scanner",
                "Formato File:": "File Format:",
                "Avvia Scansione": "Start Scan",
                "Console di Esecuzione": "Execution Console",
                "👁️ Vedi Prompt": "👁️ View Prompt",
                "💾 Salva Cache": "💾 Save Cache",
                "FILE COMPLETATI": "FILES COMPLETED",
                "RIGHE TRADOTTE": "LINES TRANSLATED",
                "VOCI IN CACHE": "CACHE ENTRIES",
                "CHIAMATE API": "API CALLS",
                "TOKEN INPUT": "INPUT TOKENS",
                "TOKEN OUTPUT": "OUTPUT TOKENS",
                "TEMPO TOTALE": "TOTAL TIME",
                "Progresso:": "Progress:",
                "In attesa...": "Waiting...",
                "▶  AVVIA PROCESSO": "▶  START PROCESS",
                "⏸  PAUSA": "⏸  PAUSE",
                "⏭  SALTA FILE": "⏭  SKIP FILE",
                "⏹  STOP": "⏹  STOP",
                "Pronto": "Ready",
                "Batch Size": "Batch Size",
                "RPM Limit": "RPM Limit",
                "Max Entries": "Max Entries",
                "Ctx Window": "Ctx Window",
                "Wrap At": "Wrap At",
                "Newline Char": "Newline Char",
                "Esegui una simulazione per calcolare token e costi stimati senza tradurre.": "Run a simulation to calculate estimated tokens and costs without translating.",
                "Analizza i file per trovare Nomi Propri e Termini Unici.": "Analyze files to find Proper Nouns and Unique Terms.",
                "Col. Orig:": "Source Col:",
                "Col. Trad:": "Target Col:",
                "Keys:": "Keys:",
                "Alumen Console Output": "Alumen Console Output",
                "▶ RIPRENDI": "▶ RESUME",
                "⏸ PAUSA": "⏸ PAUSE",
                "Processo in PAUSA": "Process PAUSED",
                "Processo RIPRESO": "Process RESUMED",
                "Salto file corrente...": "Skipping current file...",
                "Processo INTERROTTO": "Process STOPPED",
                "Recupero modelli...": "Fetching models...",
                "Modelli aggiornati": "Models updated",
                "Errore recupero modelli": "Error fetching models",
                "Connessione a Ollama...": "Connecting to Ollama...",
                "Modelli Ollama caricati": "Ollama models loaded",
                "Nessun modello Ollama trovato": "No Ollama models found",
                "Estrazione cache in corso...": "Cache extraction in progress...",
                "Scansione termini in corso...": "Term scanning in progress...",
                "Scansione completata": "Scan completed",
                "Avvio traduzione...": "Starting translation...",
                "Cache salvata su disco": "Cache saved to disk",
                "In esecuzione...": "Running...",
                " file completati": " files completed",
                "Stima fine file: ": "Est. end: ",
                "Errore": "Error",
                "Attenzione": "Warning",
                "Info": "Info",
                "Fatto": "Done",
                "Salvataggio OK": "Save OK",
                "Inserisci Token e Chat ID": "Enter Token and Chat ID",
                "Seleziona cartelle!": "Select folders!",
                "API Key necessaria": "API Key required",
                "Manca API Key!": "Missing API Key!",
                "Seleziona un modello Ollama!": "Select an Ollama model!",
                "JSON richiede chiavi!": "JSON requires keys!",
                "Processo Avviato": "Process Started",
                "La traduzione è iniziata. Puoi monitorare l'avanzamento nella scheda 'Esecuzione'.": "Translation started. You can monitor progress in the 'Execution' tab.",
                "Processo Terminato": "Process Finished",
                "Il lavoro è stato completato.": "The job has been completed.",
                "Nessun prompt inviato finora.": "No prompt sent yet.",
                "Ultimo Prompt Inviato": "Last Prompt Sent",
                "Prompt Preview": "Prompt Preview",
                "In Attesa": "Waiting",
                "🟢 ATTIVA": "🟢 ACTIVE",
                "🔴 BLACKLIST": "🔴 BLACKLIST",
                "API Key aggiunta.": "API Key added.",
                "Blacklist resettata.": "Blacklist reset.",
                "Aggiornamento": "Update",
                "Aggiornamento disponibile: v": "Update available: v",
                " disponibile su GitHub!": " available on GitHub!",
                "Inserisci qui la tua API Key di Google Gemini.": "Enter your Google Gemini API Key here.",
                "Seleziona il modello AI da utilizzare.": "Select the AI model to use.",
                "Indirizzo del server Ollama (default: http://localhost:11434).": "Ollama server address (default: http://localhost:11434).",
                "Seleziona il modello Ollama installato.": "Select the installed Ollama model.",
                "Lingua originale del testo (es. inglese, giapponese).": "Original text language (e.g., english, japanese).",
                "Lingua in cui tradurre il testo.": "Language to translate the text into.",
                "Nome del progetto per dare contesto all'AI e migliorare la coerenza.": "Project name to give context to the AI and improve consistency.",
                "Cartella contenente i file da tradurre.": "Folder containing the files to translate.",
                "Cartella dove verranno salvati i file tradotti.": "Folder where translated files will be saved.",
                "Seleziona il formato dei file da elaborare.": "Select the format of the files to process.",
                "Codifica dei file (es. utf-8, cp1252).": "File encoding (e.g., utf-8, cp1252).",
                "Abilita l'invio di log e stato via Telegram.": "Enable sending logs and status via Telegram.",
                "Token del bot Telegram (da BotFather).": "Telegram bot token (from BotFather).",
                "ID della chat o del canale dove ricevere le notifiche.": "ID of the chat or channel to receive notifications.",
                "Carattere che separa le colonne nel file CSV (es. virgola ',' o punto e virgola ';').": "Character that separates columns in the CSV file (e.g., comma ',' or semicolon ';').",
                "Indice numerico della colonna da tradurre. La prima colonna è 0.": "Numeric index of the column to translate. The first column is 0.",
                "Indice numerico della colonna in cui salvare la traduzione. Se uguale all'origine, sovrascriverà i testi originali.": "Numeric index of the column to save the translation. If equal to source, it will overwrite the original texts.",
                "Ignora le righe che hanno più di N colonne. Utile per saltare righe di commento mal formattate.": "Ignore rows with more than N columns. Useful for skipping poorly formatted comment rows.",
                "Elenco delle chiavi JSON che contengono testo da tradurre (separate da virgola). Obbligatorio per elaborare i JSON.": "List of JSON keys containing text to translate (comma-separated). Required to process JSONs.",
                "Se attivo, controlla l'intera gerarchia della chiave (es. 'dialogue.npc.text' invece di considerare qualsiasi chiave 'text').": "If active, checks the entire key hierarchy (e.g., 'dialogue.npc.text' instead of considering any 'text' key).",
                "Lettera della colonna originale. Usa la virgola per indicarne multiple (es. A,C,E).": "Source column letter. Use comma for multiple (e.g., A,C,E).",
                "Lettera di destinazione. Usa la virgola (es. B,D,F) per abbinarle alle origini.": "Target column letter. Use comma to match sources (e.g., B,D,F).",
                "⚠️ Sostituisce in blocco il prompt di base di Alumen. Usa solo per esperimenti estremi. Richiede {text_to_translate}.": "⚠️ Completely replaces Alumen's base prompt. Use only for extreme experiments. Requires {text_to_translate}.",
                "Aggiunge una singola frase informativa alla fine delle regole standard per chiarire la trama.": "Adds a single informative sentence at the end of standard rules to clarify the plot.",
                "Legge le prime righe del file per generare un contesto automatico.": "Reads the first lines of the file to generate an automatic context.",
                "Usa tutto il file per generare il contesto (più costoso/lento).": "Uses the whole file to generate context (more expensive/slower).",
                "Salva le traduzioni per non ripeterle.": "Saves translations to avoid repeating them.",
                "Passa alla chiave successiva se una finisce la quota.": "Switches to the next key if one runs out of quota.",
                "Genera solo un file di testo con le traduzioni.": "Generates only a text file with translations.",
                "Riprova all'infinito in caso di errore (no blacklist).": "Retries infinitely in case of error (no blacklist).",
                "Salta le righe già tradotte nel file di output.": "Skips already translated rows in the output file.",
                "Salva il log su file.": "Saves the log to a file.",
                "L'AI ricontrolla la propria traduzione (2x costo).": "AI double-checks its own translation (2x cost).",
                "Usa la cache anche per frasi simili (maiuscole/punteggiatura).": "Uses cache even for similar phrases (caps/punctuation).",
                "Spegne il PC al termine del lavoro.": "Shuts down the PC when the job is done.",
                "Carica l'intero file su Gemini invece di tradurre riga per riga.": "Uploads the entire file to Gemini instead of translating line by line.",
                "Righe per richiesta.": "Rows per request.",
                "Richieste per minuto massime.": "Maximum requests per minute.",
                "Limite righe per file.": "Row limit per file.",
                "Righe precedenti da inviare come contesto.": "Previous rows to send as context.",
                "A capo automatico dopo N caratteri.": "Word wrap after N characters.",
                "Carattere per l'a capo (es. \\n).": "Newline character (e.g., \\n).",
                "File CSV con termini forzati (Originale,Traduzione).": "CSV file with forced terms (Original,Translation).",
                "Allega un file di testo con regole dettagliate di formattazione e tono di voce (es. dare del Voi, stile UI).": "Attach a text file with detailed formatting and tone of voice rules.",
                "File JSON dove salvare/caricare le traduzioni.": "JSON file where to save/load translations.",
                "Lancia il processo in modalità simulazione.": "Starts the process in simulation mode.",
                "Crea un file cache JSON confrontando i file originali e tradotti.": "Creates a JSON cache file comparing original and translated files.",
                "Usa l'AI per estrarre una lista di termini univoci dai file di input.": "Uses AI to extract a list of unique terms from input files.",
                "Visualizza l'ultimo prompt inviato all'AI.": "Displays the last prompt sent to AI.",
                "Forza il salvataggio immediato della cache su disco.": "Forces immediate saving of cache to disk.",
                "Avvia la traduzione con le impostazioni correnti.": "Starts translation with current settings.",
                "Mette in pausa il processo (completa il batch corrente).": "Pauses the process (completes the current batch).",
                "Interrompe il file corrente e passa al successivo.": "Stops the current file and moves to the next.",
                "Interrompe completamente il processo.": "Completely stops the process."
            }
        }
        
        # Caricamento lingue addizionali da json (se esiste)
        if os.path.exists("locales.json"):
            try:
                with open("locales.json", "r", encoding="utf-8") as f:
                    ext_langs = json.load(f)
                    for lang, trans_dict in ext_langs.items():
                        if lang in self.translations:
                            self.translations[lang].update(trans_dict)
                        else:
                            self.translations[lang] = trans_dict
            except Exception: pass
        # -------------------------------

        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.pause_event = threading.Event(); self.pause_event.set()
        self.skip_event = threading.Event()
        
        self.api_file_path = None
        self.current_args = None
        self.nav_buttons = {}
        self.current_page = None
        self.is_running = False
        self.is_initialized = False
        
        self.spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.spinner_idx = 0

        self._configure_styles()
        self._init_layout()
        self.is_initialized = True
        
        if os.path.exists("api_key.txt"):
            self._load_api_file_internal("api_key.txt")
        
        self.root.after(100, self._poll_log_queue)
        self.root.after(1000, self._update_stats)
        self.root.after(100, self._update_spinner)
        self.root.after(2000, self._check_update_thread)
        self.root.after(100, self._update_ui_states)

    def tr(self, text):
        if self.current_lang == "it": return text
        return self.translations.get(self.current_lang, {}).get(text, text)

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Base Styles
        style.configure('TFrame', background=C_MAIN_BG)
        style.configure('Card.TFrame', background=C_CARD_BG)
        style.configure('TLabel', background=C_MAIN_BG, foreground=C_TEXT_MAIN, font=F_BODY)
        style.configure('Card.TLabel', background=C_CARD_BG, foreground=C_TEXT_MAIN, font=F_BODY)
        style.configure('CardHeader.TLabel', background=C_CARD_BG, foreground=C_ACCENT, font=F_H2)
        
        # Buttons
        style.configure('TButton', font=F_BODY, borderwidth=0, background="#3E3E42", foreground=C_TEXT_MAIN, padding=4)
        style.map('TButton', background=[('active', '#4E4E52'), ('disabled', '#2D2D30')], foreground=[('disabled', '#666666')])
        
        BTN_F = ("Segoe UI", 11, "bold")
        style.configure('Action.TButton', background="#238636", foreground="white", font=BTN_F, padding=12)
        style.map('Action.TButton', background=[('active', "#2EA043"), ('disabled', '#2D2D30')], foreground=[('disabled', '#666666')])
        
        style.configure('Danger.TButton', background="#DA3633", foreground="white", font=BTN_F, padding=12)
        style.map('Danger.TButton', background=[('active', "#F85149"), ('disabled', '#2D2D30')], foreground=[('disabled', '#666666')])
        
        style.configure('Warn.TButton', background="#D29922", foreground="white", font=BTN_F, padding=12)
        style.map('Warn.TButton', background=[('active', "#E3B341"), ('disabled', '#2D2D30')], foreground=[('disabled', '#666666')])
        
        style.configure('Secondary.TButton', background="#21262D", foreground=C_TEXT_MAIN, font=BTN_F, padding=12)
        style.map('Secondary.TButton', background=[('active', '#4E4E52'), ('disabled', '#2D2D30')], foreground=[('disabled', '#666666')])
        
        # Inputs
        style.configure('TEntry', fieldbackground=C_INPUT_BG, foreground=C_TEXT_MAIN, padding=8, relief="flat", borderwidth=1, bordercolor=C_BORDER)
        style.map('TEntry', bordercolor=[('focus', C_ACCENT)])
        
        style.configure('TCombobox', fieldbackground=C_INPUT_BG, background=C_INPUT_BG, foreground=C_TEXT_MAIN, padding=8, relief="flat", borderwidth=1, bordercolor=C_BORDER, arrowcolor=C_TEXT_MAIN)
        style.map('TCombobox', 
                  fieldbackground=[('readonly', C_INPUT_BG)], 
                  selectbackground=[('readonly', C_INPUT_BG), ('focus', C_INPUT_BG)], 
                  selectforeground=[('readonly', C_TEXT_MAIN), ('focus', C_TEXT_MAIN)], 
                  background=[('active', '#3E3E42')])

        # Dropdown Menu (Listbox interno) Styling
        self.root.option_add('*TCombobox*Listbox.background', '#2D2D30')
        self.root.option_add('*TCombobox*Listbox.foreground', C_TEXT_MAIN)
        self.root.option_add('*TCombobox*Listbox.selectBackground', C_ACCENT)
        self.root.option_add('*TCombobox*Listbox.selectForeground', 'white')
        self.root.option_add('*TCombobox*Listbox.font', f"{{{FONT_FAM}}} 10")
        self.root.option_add('*TCombobox*Listbox.relief', 'flat')

        # Modern Checkbox & Radio
        style.configure("Card.TCheckbutton", background=C_CARD_BG, foreground=C_TEXT_MAIN, font=F_BODY, focuscolor=C_CARD_BG)
        style.map("Card.TCheckbutton", 
                  background=[('active', C_CARD_BG)],
                  indicatorbackground=[('selected', C_ACCENT), ('!selected', C_INPUT_BG)],
                  indicatorcolor=[('selected', C_ACCENT), ('!selected', C_INPUT_BG)])

        style.configure("Card.TRadiobutton", background=C_CARD_BG, foreground=C_TEXT_MAIN, font=F_BODY, focuscolor=C_CARD_BG)
        style.map("Card.TRadiobutton", 
                  background=[('active', C_CARD_BG)],
                  indicatorbackground=[('selected', C_ACCENT), ('!selected', C_INPUT_BG)],
                  indicatorcolor=[('selected', C_ACCENT), ('!selected', C_INPUT_BG)])

        # Minimal Scrollbar e Flat Progressbar
        style.configure("Vertical.TScrollbar", background="#1B1B1B", bordercolor=C_MAIN_BG, arrowcolor=C_MAIN_BG, troughcolor=C_MAIN_BG, arrowsize=5, relief="flat")
        style.map("Vertical.TScrollbar", background=[('active', "#2E2E2E")])
        
        style.configure("Flat.Horizontal.TProgressbar", thickness=6, borderwidth=0, troughcolor=C_MAIN_BG, background=C_ACCENT, troughrelief="flat")

        style.configure("Treeview", background=C_INPUT_BG, foreground=C_TEXT_MAIN, fieldbackground=C_INPUT_BG, borderwidth=0, rowheight=35)
        style.map('Treeview', background=[('selected', C_ACCENT)])
        style.configure("Treeview.Heading", background=C_CARD_BG, foreground=C_TEXT_MAIN, font=F_BODY)

    def _init_layout(self):
        # --- SIDEBAR ---
        self.sidebar = tk.Frame(self.root, bg=C_SIDEBAR_BG, width=260)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        # Logo
        f_logo = tk.Frame(self.sidebar, bg=C_SIDEBAR_BG, pady=40)
        f_logo.pack(fill="x")
        tk.Label(f_logo, text="ALUMEN", bg=C_SIDEBAR_BG, fg="white", font=("Segoe UI", 26, "bold")).pack()
        tk.Label(f_logo, text="AI TRANSLATION SUITE", bg=C_SIDEBAR_BG, fg=C_ACCENT, font=("Segoe UI", 9, "bold", "italic")).pack()
        
        # Navigation
        f_nav = tk.Frame(self.sidebar, bg=C_SIDEBAR_BG)
        f_nav.pack(fill="x", padx=0, pady=20)
        
        self.nav_buttons['conf'] = self._make_nav_btn(f_nav, self.tr("⚙️  Configurazione"), "conf")
        self.nav_buttons['adv'] = self._make_nav_btn(f_nav, self.tr("🧠  Avanzate"), "adv")
        self.nav_buttons['api'] = self._make_nav_btn(f_nav, self.tr("🔑  Gestione API"), "api")
        self.nav_buttons['tools'] = self._make_nav_btn(f_nav, self.tr("🛠️  Strumenti"), "tools")
        self.nav_buttons['log'] = self._make_nav_btn(f_nav, self.tr("🚀  Esecuzione"), "log")
        
        # Footer
        tk.Label(self.sidebar, text=f"Core v{AlumenCore.CURRENT_SCRIPT_VERSION}", bg=C_SIDEBAR_BG, fg="#666666", font=F_SMALL).pack(side="bottom", pady=15)
        
        # Selettore Lingua / Language Selector
        f_lang = tk.Frame(self.sidebar, bg=C_SIDEBAR_BG)
        f_lang.pack(side="bottom", pady=(0, 10))
        tk.Label(f_lang, text="🌐", bg=C_SIDEBAR_BG, fg=C_TEXT_SIDEBAR).pack(side="left")
        self.cmb_lang = ttk.Combobox(f_lang, values=list(self.translations.keys()), width=5, state="readonly")
        self.cmb_lang.set(self.current_lang)
        self.cmb_lang.pack(side="left", padx=5)
        self.cmb_lang.bind("<<ComboboxSelected>>", self._change_language)

        # --- MAIN CONTENT ---
        self.main_area = tk.Frame(self.root, bg=C_MAIN_BG)
        self.main_area.pack(side="right", fill="both", expand=True)
        self.main_area.grid_rowconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)
        
        self.frames = {}
        for page in ["conf", "adv", "api", "tools", "log"]:
            fr = tk.Frame(self.main_area, bg=C_MAIN_BG)
            fr.grid(row=0, column=0, sticky="nsew")
            self.frames[page] = fr
            
        self._build_page_conf(self.frames["conf"])
        self._build_page_adv(self.frames["adv"])
        self._build_page_api(self.frames["api"]) # Nuova funzione
        self._build_page_tools(self.frames["tools"])
        self._build_page_log(self.frames["log"])
        
        # Status Bar
        self.status_var = tk.StringVar(value=self.tr("Pronto"))
        self.status_bar = tk.Frame(self.main_area, bg=C_ACCENT, height=30)
        self.status_bar.place(relx=0, rely=1, anchor="sw", relwidth=1)
        tk.Label(self.status_bar, textvariable=self.status_var, bg=C_ACCENT, fg="white", font=F_SMALL, padx=10).pack(side="left")
        
        self._show_frame("conf")

    def _change_language(self, event=None):
        new_lang = self.cmb_lang.get()
        if new_lang != self.current_lang:
            self.current_lang = new_lang
            for widget in self.root.winfo_children(): widget.destroy()
            self._init_layout()

    def _make_nav_btn(self, parent, text, page_key):
        btn = tk.Button(parent, text=text, bg=C_SIDEBAR_BG, fg=C_TEXT_SIDEBAR, font=F_SIDEBAR, 
                        bd=0, relief=tk.FLAT, padx=10, pady=15, anchor="center", cursor="hand2",
                        activebackground=C_SIDEBAR_BTN_ACTIVE, activeforeground="white",
                        command=lambda: self._show_frame(page_key))
        btn.pack(fill="x", pady=1)
        
        # Hover Effect per i bottoni laterali
        def on_enter(e):
            if self.current_page != page_key: btn.configure(bg="#1F1F1F")
        def on_leave(e):
            if self.current_page != page_key: btn.configure(bg=C_SIDEBAR_BG)
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def _show_frame(self, page_name):
        self.current_page = page_name
        self.frames[page_name].tkraise()
        for key, btn in self.nav_buttons.items():
            if key == page_name:
                btn.configure(bg=C_SIDEBAR_BTN_ACTIVE, fg=C_TEXT_SIDEBAR_ACT, font=("Segoe UI", 11, "bold"))
            else:
                btn.configure(bg=C_SIDEBAR_BG, fg=C_TEXT_SIDEBAR, font=("Segoe UI", 11, "normal"))
        
        # Aggiorna la lista API se si apre la scheda API
        if page_name == "api":
            self._refresh_api_list()

    def _create_card(self, parent, title):
        # Card Wrapper (Shadow effect via border)
        card = tk.Frame(parent, bg=C_CARD_BG, highlightbackground=C_BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, 20), padx=5)
        
        # Accent Strip
        tk.Frame(card, bg=C_ACCENT, height=2).pack(fill="x")
        
        # Header
        header = tk.Frame(card, bg=C_CARD_BG, pady=15, padx=20)
        header.pack(fill="x")
        tk.Label(header, text=title, bg=C_CARD_BG, fg=C_TEXT_MAIN, font=F_H2).pack(side="left")
        
        # Content
        content = tk.Frame(card, bg=C_CARD_BG, padx=20)
        content.pack(fill="both", expand=True, pady=(0, 20))
        
        # Hover Effect "intelligente" per non sfarfallare passando sui widget figli
        def on_enter(e): card.config(highlightbackground="#555555")
        def on_leave(e):
            x, y = card.winfo_pointerxy()
            cx, cy, cw, ch = card.winfo_rootx(), card.winfo_rooty(), card.winfo_width(), card.winfo_height()
            if not (cx <= x <= cx + cw and cy <= y <= cy + ch):
                card.config(highlightbackground=C_BORDER)
        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)
        return content

    def _make_grid_frame(self, parent, r, c):
        f = tk.Frame(parent, bg=C_CARD_BG)
        f.grid(row=r, column=c, padx=15, pady=8, sticky="ew")
        parent.grid_columnconfigure(c, weight=1)
        return f

    # --- PAGE 1: CONFIGURAZIONE ---
    def _build_page_conf(self, parent):
        sf = ScrollableFrame(parent)
        sf.pack(fill="both", expand=True)
        container = ttk.Frame(sf.scrollable_frame, padding=40)
        container.pack(fill="both", expand=True)
        
        tk.Label(container, text=self.tr("Configurazione Progetto"), bg=C_MAIN_BG, fg=C_TEXT_MAIN, font=F_H1).pack(anchor="w", pady=(0, 30))
        
        # Init vars
        self.var_ai_provider = tk.StringVar(value="gemini")
        self.var_ollama_enabled = tk.BooleanVar(value=False)

        # CARD: AI ENGINE
        c_ai = self._create_card(container, self.tr("Motore di Traduzione"))
        
        f_sel = tk.Frame(c_ai, bg=C_CARD_BG)
        f_sel.pack(fill="x", pady=(0, 15))
        ttk.Radiobutton(f_sel, text=self.tr("Google Gemini (Cloud)"), variable=self.var_ai_provider, value="gemini", style="Card.TRadiobutton", command=self._toggle_ai_provider).pack(side="left", padx=(0, 20))
        ttk.Radiobutton(f_sel, text=self.tr("Ollama (Locale)"), variable=self.var_ai_provider, value="ollama", style="Card.TRadiobutton", command=self._toggle_ai_provider).pack(side="left", padx=10)

        # Gemini Panel
        self.f_gemini = tk.Frame(c_ai, bg=C_CARD_BG)
        self.f_gemini.pack(fill="x")
        
        f_k = tk.Frame(self.f_gemini, bg=C_CARD_BG)
        f_k.pack(fill="x", pady=(0, 10))
        ttk.Label(f_k, text=self.tr("API Key"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        
        f_k_in = tk.Frame(f_k, bg=C_CARD_BG)
        f_k_in.pack(fill="x", pady=(5,0))
        self.ent_api = ttk.Entry(f_k_in)
        self.ent_api.pack(side="left", fill="x", expand=True)
        ToolTip(self.ent_api, self.tr("Inserisci qui la tua API Key di Google Gemini."))
        
        self.f_file_loaded = tk.Frame(f_k_in, bg=C_CARD_BG)
        self.lbl_file_loaded = ttk.Label(self.f_file_loaded, text="", foreground=C_SUCCESS, font=("Segoe UI", 9, "bold"), style='Card.TLabel')
        self.lbl_file_loaded.pack(side="left", padx=10)
        ttk.Button(self.f_file_loaded, text="✕", width=3, command=self._clear_api_file).pack(side="left")
        
        ttk.Button(f_k_in, text=self.tr("📂 Load .txt"), command=self._load_api_file).pack(side="right", padx=(10,0))
        
        f_m = tk.Frame(self.f_gemini, bg=C_CARD_BG)
        f_m.pack(fill="x")
        ttk.Label(f_m, text=self.tr("Modello"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        f_m_in = tk.Frame(f_m, bg=C_CARD_BG)
        f_m_in.pack(fill="x", pady=(5,0))
        self.cmb_model = ttk.Combobox(f_m_in, state="readonly")
        self.cmb_model['values'] = ("gemini-2.0-flash [Default]",)
        self.cmb_model.current(0)
        self.cmb_model.pack(side="left", fill="x", expand=True)
        ToolTip(self.cmb_model, self.tr("Seleziona il modello AI da utilizzare."))
        ttk.Button(f_m_in, text="🔄", width=4, command=self._refresh_models_auto).pack(side="right", padx=(10,0))

        # Ollama Panel
        self.f_ollama = tk.Frame(c_ai, bg=C_CARD_BG)
        
        f_oh = tk.Frame(self.f_ollama, bg=C_CARD_BG)
        f_oh.pack(fill="x", pady=(0, 10))
        ttk.Label(f_oh, text=self.tr("Host URL"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_ollama_host = ttk.Entry(f_oh)
        self.ent_ollama_host.insert(0, AlumenCore.DEFAULT_OLLAMA_HOST)
        self.ent_ollama_host.pack(fill="x", pady=(5,0))
        ToolTip(self.ent_ollama_host, self.tr("Indirizzo del server Ollama (default: http://localhost:11434)."))
        
        f_om = tk.Frame(self.f_ollama, bg=C_CARD_BG)
        f_om.pack(fill="x")
        ttk.Label(f_om, text=self.tr("Modello Locale"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        f_om_in = tk.Frame(f_om, bg=C_CARD_BG)
        f_om_in.pack(fill="x", pady=(5,0))
        self.cmb_ollama_model = ttk.Combobox(f_om_in, state="readonly")
        self.cmb_ollama_model.pack(side="left", fill="x", expand=True)
        ToolTip(self.cmb_ollama_model, self.tr("Seleziona il modello Ollama installato."))
        ttk.Button(f_om_in, text="🔄", width=4, command=self._refresh_ollama_models).pack(side="right", padx=(10,0))

        # CARD: TASK
        c_task = self._create_card(container, self.tr("Parametri Traduzione"))
        
        f_lng = tk.Frame(c_task, bg=C_CARD_BG)
        f_lng.pack(fill="x", pady=(0, 15))
        
        f_l1 = tk.Frame(f_lng, bg=C_CARD_BG)
        f_l1.pack(side="left", fill="x", expand=True)
        ttk.Label(f_l1, text=self.tr("Lingua Sorgente"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_src = ttk.Entry(f_l1)
        self.ent_src.insert(0, "inglese")
        self.ent_src.pack(fill="x", pady=(5,0))
        ToolTip(self.ent_src, self.tr("Lingua originale del testo (es. inglese, giapponese)."))
        
        tk.Label(f_lng, text="➜", bg=C_CARD_BG, fg=C_ACCENT, font=("Segoe UI", 14)).pack(side="left", padx=20, pady=(15,0))
        
        f_l2 = tk.Frame(f_lng, bg=C_CARD_BG)
        f_l2.pack(side="left", fill="x", expand=True)
        ttk.Label(f_l2, text=self.tr("Lingua Target"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_tgt = ttk.Entry(f_l2)
        self.ent_tgt.insert(0, "italiano")
        self.ent_tgt.pack(fill="x", pady=(5,0))
        ToolTip(self.ent_tgt, self.tr("Lingua in cui tradurre il testo."))

        ttk.Label(c_task, text=self.tr("Contesto Gioco / Progetto"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w", pady=(10, 0))
        self.ent_gamename = PlaceholderEntry(c_task, "Es. 'The Witcher 3' o 'App Gestionale'")
        self.ent_gamename.pack(fill="x", pady=(5,0))
        ToolTip(self.ent_gamename, self.tr("Nome del progetto per dare contesto all'AI e migliorare la coerenza."))

        # CARD: FILES
        c_file = self._create_card(container, self.tr("Gestione File"))
        
        # Input
        f_in = tk.Frame(c_file, bg=C_CARD_BG)
        f_in.pack(fill="x", pady=(0, 10))
        ttk.Label(f_in, text=self.tr("Cartella Input"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        f_in_row = tk.Frame(f_in, bg=C_CARD_BG)
        f_in_row.pack(fill="x", pady=(5,0))
        self.ent_input = ttk.Entry(f_in_row)
        self.ent_input.insert(0, "input")
        self.ent_input.pack(side="left", fill="x", expand=True)
        ttk.Button(f_in_row, text=self.tr("Sfoglia"), command=lambda: self._browse_folder(self.ent_input, is_input=True)).pack(side="right", padx=(10,0))
        ToolTip(self.ent_input, self.tr("Cartella contenente i file da tradurre."))
        
        # Output
        f_out = tk.Frame(c_file, bg=C_CARD_BG)
        f_out.pack(fill="x", pady=(0, 15))
        ttk.Label(f_out, text=self.tr("Cartella Output"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        f_out_row = tk.Frame(f_out, bg=C_CARD_BG)
        f_out_row.pack(fill="x", pady=(5,0))
        self.ent_output = ttk.Entry(f_out_row)
        self.ent_output.insert(0, "output")
        self.ent_output.pack(side="left", fill="x", expand=True)
        ttk.Button(f_out_row, text=self.tr("Sfoglia"), command=lambda: self._browse_folder(self.ent_output)).pack(side="right", padx=(10,0))
        ToolTip(self.ent_output, self.tr("Cartella dove verranno salvati i file tradotti."))
        
        # Format
        f_opt = tk.Frame(c_file, bg=C_CARD_BG)
        f_opt.pack(fill="x")
        
        f_fmt = tk.Frame(f_opt, bg=C_CARD_BG)
        f_fmt.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(f_fmt, text=self.tr("Formato File"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.cmb_fmt = ttk.Combobox(f_fmt, values=["csv", "json", "xlsx", "po", "srt"], width=10, state="readonly")
        self.cmb_fmt.current(0)
        self.cmb_fmt.bind("<<ComboboxSelected>>", self._update_ui_states)
        self.cmb_fmt.pack(fill="x", pady=(5,0))
        ToolTip(self.cmb_fmt, self.tr("Seleziona il formato dei file da elaborare."))
        
        f_enc = tk.Frame(f_opt, bg=C_CARD_BG)
        f_enc.pack(side="left", fill="x", expand=True)
        ttk.Label(f_enc, text=self.tr("Encoding"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_encoding = PlaceholderEntry(f_enc, "utf-8", width=10)
        self.ent_encoding.pack(fill="x", pady=(5,0))
        ToolTip(self.ent_encoding, self.tr("Codifica dei file (es. utf-8, cp1252)."))

        # CARD: TELEGRAM
        c_tg = self._create_card(container, self.tr("Notifiche Telegram"))
        self.var_tg_enabled = tk.BooleanVar(value=False)
        cb_tg = ttk.Checkbutton(c_tg, text=self.tr("Abilita Notifiche"), variable=self.var_tg_enabled, style="Card.TCheckbutton", command=self._toggle_telegram_ui)
        cb_tg.pack(anchor="w", pady=(0, 10))
        ToolTip(cb_tg, self.tr("Abilita l'invio di log e stato via Telegram."))
        
        f_tg = tk.Frame(c_tg, bg=C_CARD_BG)
        f_tg.pack(fill="x")
        
        f_tg1 = tk.Frame(f_tg, bg=C_CARD_BG)
        f_tg1.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(f_tg1, text=self.tr("Bot Token"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_tg_token = ttk.Entry(f_tg1)
        self.ent_tg_token.pack(fill="x", pady=(5,0))
        ToolTip(self.ent_tg_token, self.tr("Token del bot Telegram (da BotFather)."))
        
        f_tg2 = tk.Frame(f_tg, bg=C_CARD_BG)
        f_tg2.pack(side="left", fill="x", expand=True)
        ttk.Label(f_tg2, text=self.tr("Chat ID"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_tg_chatid = ttk.Entry(f_tg2)
        self.ent_tg_chatid.pack(fill="x", pady=(5,0))
        ToolTip(self.ent_tg_chatid, self.tr("ID della chat o del canale dove ricevere le notifiche."))
        
        self.btn_tg_save = ttk.Button(f_tg, text="💾", width=4, command=self._save_telegram_config)
        self.btn_tg_save.pack(side="left", padx=(10,0), pady=(20,0))

        self._toggle_ai_provider()

    # --- PAGE 2: AVANZATE ---
    def _build_page_adv(self, parent):
        sf = ScrollableFrame(parent)
        sf.pack(fill="both", expand=True)
        container = ttk.Frame(sf.scrollable_frame, padding=40)
        container.pack(fill="both", expand=True)
        
        tk.Label(container, text=self.tr("Impostazioni Avanzate"), bg=C_MAIN_BG, fg=C_TEXT_MAIN, font=F_H1).pack(anchor="w", pady=(0, 30))
        
        # CARD: FORMATO
        c_spec = self._create_card(container, self.tr("Specifiche Formato"))
        
        # CSV
        f_csv = tk.Frame(c_spec, bg=C_CARD_BG)
        f_csv.pack(fill="x", pady=(0, 10))
        
        # Grid Layout 2x2 for CSV
        f_00 = self._make_grid_frame(f_csv, 0, 0)
        ttk.Label(f_00, text=self.tr("Delimitatore CSV"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_delim = PlaceholderEntry(f_00, ",", width=5)
        self.ent_delim.pack(fill="x", pady=(2,0))
        ToolTip(self.ent_delim, self.tr("Carattere che separa le colonne nel file CSV (es. virgola ',' o punto e virgola ';')."))

        f_01 = self._make_grid_frame(f_csv, 0, 1)
        ttk.Label(f_01, text=self.tr("Indice Col. Origine (0=A)"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_col = PlaceholderEntry(f_01, "3", width=5)
        self.ent_col.pack(fill="x", pady=(2,0))
        ToolTip(self.ent_col, self.tr("Indice numerico della colonna da tradurre. La prima colonna è 0."))

        f_10 = self._make_grid_frame(f_csv, 1, 0)
        ttk.Label(f_10, text=self.tr("Indice Col. Destinazione"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_col_out = PlaceholderEntry(f_10, "3", width=5)
        self.ent_col_out.pack(fill="x", pady=(2,0))
        ToolTip(self.ent_col_out, self.tr("Indice numerico della colonna in cui salvare la traduzione. Se uguale all'origine, sovrascriverà i testi originali."))

        f_11 = self._make_grid_frame(f_csv, 1, 1)
        ttk.Label(f_11, text=self.tr("Limite Max Colonne"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_maxcols = PlaceholderEntry(f_11, "None", width=5)
        self.ent_maxcols.pack(fill="x", pady=(2,0))
        ToolTip(self.ent_maxcols, self.tr("Ignora le righe che hanno più di N colonne. Utile per saltare righe di commento mal formattate."))

        ttk.Separator(c_spec, orient="horizontal").pack(fill="x", pady=15)

        # JSON
        f_json = tk.Frame(c_spec, bg=C_CARD_BG)
        f_json.pack(fill="x")
        f_j_in = tk.Frame(f_json, bg=C_CARD_BG)
        f_j_in.pack(side="left", fill="x", expand=True)
        ttk.Label(f_j_in, text=self.tr("Chiavi JSON da Tradurre"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_jkeys = PlaceholderEntry(f_j_in, "es. title, description, text")
        self.ent_jkeys.pack(fill="x", pady=(2,0))
        ToolTip(self.ent_jkeys, self.tr("Elenco delle chiavi JSON che contengono testo da tradurre (separate da virgola). Obbligatorio per elaborare i JSON."))
        
        self.var_jmatch = tk.BooleanVar(value=False)
        cb_j = ttk.Checkbutton(f_json, text=self.tr("Corrispondenza Percorso Esatto"), variable=self.var_jmatch, style="Card.TCheckbutton")
        cb_j.pack(side="left", padx=20, pady=(15,0))
        ToolTip(cb_j, self.tr("Se attivo, controlla l'intera gerarchia della chiave (es. 'dialogue.npc.text' invece di considerare qualsiasi chiave 'text')."))

        ttk.Separator(c_spec, orient="horizontal").pack(fill="x", pady=15)

        # EXCEL (XLSX)
        f_xlsx = tk.Frame(c_spec, bg=C_CARD_BG)
        f_xlsx.pack(fill="x")
        
        f_x1 = tk.Frame(f_xlsx, bg=C_CARD_BG)
        f_x1.pack(side="left", fill="x", expand=True)
        ttk.Label(f_x1, text=self.tr("Lettera Col. Origine (es. A,C)"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_xlsx_src = PlaceholderEntry(f_x1, "A", width=5)
        self.ent_xlsx_src.pack(fill="x", pady=(2,0))
        ToolTip(self.ent_xlsx_src, self.tr("Lettera della colonna originale. Usa la virgola per indicarne multiple (es. A,C,E)."))

        f_x2 = tk.Frame(f_xlsx, bg=C_CARD_BG)
        f_x2.pack(side="left", fill="x", expand=True, padx=(20, 0))
        ttk.Label(f_x2, text=self.tr("Lettera Col. Destinaz. (es. B,D)"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_xlsx_tgt = PlaceholderEntry(f_x2, "B", width=5)
        self.ent_xlsx_tgt.pack(fill="x", pady=(2,0))
        ToolTip(self.ent_xlsx_tgt, self.tr("Lettera di destinazione. Usa la virgola (es. B,D,F) per abbinarle alle origini."))

        # CARD: PROMPT
        c_ctx = self._create_card(container, self.tr("Prompt Engineering"))
        
        ttk.Label(c_ctx, text=self.tr("Custom Prompt (SOVRASCRIVE regole base)"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_prompt = PlaceholderEntry(c_ctx, "ATTENZIONE: Sostituisce il prompt base. Devi includere '{text_to_translate}'")
        self.ent_prompt.pack(fill="x", pady=(5, 15))
        ToolTip(self.ent_prompt, self.tr("⚠️ Sostituisce in blocco il prompt di base di Alumen. Usa solo per esperimenti estremi. Richiede {text_to_translate}."))
        
        ttk.Label(c_ctx, text=self.tr("Contesto Fisso (Aggiunta rapida)"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_pctx = PlaceholderEntry(c_ctx, "Es. 'Il protagonista è una donna', 'Ambientazione sci-fi'")
        self.ent_pctx.pack(fill="x", pady=(5, 15))
        ToolTip(self.ent_pctx, self.tr("Aggiunge una singola frase informativa alla fine delle regole standard per chiarire la trama."))
        
        f_chk_ctx = tk.Frame(c_ctx, bg=C_CARD_BG)
        f_chk_ctx.pack(fill="x")
        self.var_file_ctx = tk.BooleanVar(value=False)
        self.var_full_sample = tk.BooleanVar(value=False)
        cb_fc = ttk.Checkbutton(f_chk_ctx, text=self.tr("Analisi Preliminare File (Auto-Context)"), variable=self.var_file_ctx, style="Card.TCheckbutton", command=self._update_ui_states)
        cb_fc.pack(side="left", padx=(0,20))
        ToolTip(cb_fc, self.tr("Legge le prime righe del file per generare un contesto automatico."))
        
        self.cb_full_sample = ttk.Checkbutton(f_chk_ctx, text=self.tr("Full Sample (Più lento)"), variable=self.var_full_sample, style="Card.TCheckbutton")
        self.cb_full_sample.pack(side="left")
        ToolTip(self.cb_full_sample, self.tr("Usa tutto il file per generare il contesto (più costoso/lento)."))

        # CARD: LOGICA
        c_perf = self._create_card(container, self.tr("Logica & Performance"))
        
        f_chk = tk.Frame(c_perf, bg=C_CARD_BG)
        f_chk.pack(fill="x", pady=(0, 20))
        
        for i in range(3): f_chk.columnconfigure(i, weight=1, uniform="chk")
        
        self.var_cache = tk.BooleanVar(value=True)
        self.var_rotate = tk.BooleanVar(value=True)
        self.var_dry = tk.BooleanVar(value=False) # Manteniamo la variabile ma non la checkbox qui
        self.var_transonly = tk.BooleanVar(value=False)
        self.var_server = tk.BooleanVar(value=False)
        self.var_resume = tk.BooleanVar(value=False)
        self.var_filelog = tk.BooleanVar(value=False)
        self.var_reflect = tk.BooleanVar(value=False)
        self.var_fuzzy = tk.BooleanVar(value=False)
        self.var_shutdown = tk.BooleanVar(value=False)
        self.var_upload = tk.BooleanVar(value=False)
        
        checks = [
            ("Salva Cache", self.var_cache, "Salva le traduzioni per non ripeterle."),
            ("Auto-Rotazione API", self.var_rotate, "Passa alla chiave successiva se una finisce la quota."),
            # ("Dry Run (Preventivo)", self.var_dry, "Simula il processo per stimare i costi."), # SPOSTATO
            ("Solo Output .txt", self.var_transonly, "Genera solo un file di testo con le traduzioni."),
            ("Server Mode", self.var_server, "Riprova all'infinito in caso di errore (no blacklist)."),
            ("Resume (Salta fatti)", self.var_resume, "Salta le righe già tradotte nel file di output."),
            ("File Log (log.txt)", self.var_filelog, "Salva il log su file."),
            ("Agentic Reflection", self.var_reflect, "L'AI ricontrolla la propria traduzione (2x costo)."),
            ("Fuzzy Match Cache", self.var_fuzzy, "Usa la cache anche per frasi simili (maiuscole/punteggiatura)."),
            ("Spegnimento Auto", self.var_shutdown, "Spegne il PC al termine del lavoro."),
            ("Upload a Gemini", self.var_upload, "Carica l'intero file su Gemini invece di tradurre riga per riga.")
        ]
        for i, (txt, var, tip) in enumerate(checks):
            cmd = self._update_ui_states if txt == "Salva Cache" else None
            cb = ttk.Checkbutton(f_chk, text=self.tr(txt), variable=var, style="Card.TCheckbutton", command=cmd)
            cb.grid(row=i//3, column=i%3, padx=10, pady=8, sticky="w")
            ToolTip(cb, self.tr(tip))

        f_num = tk.Frame(c_perf, bg=C_CARD_BG)
        f_num.pack(fill="x", pady=(0, 15))
        
        # Grid Layout 2x3 for Numeric Params
        f_n00 = self._make_grid_frame(f_num, 0, 0)
        ttk.Label(f_n00, text=self.tr("Batch Size"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_batch = PlaceholderEntry(f_n00, "30", width=6)
        self.ent_batch.pack(fill="x", pady=(2,0))
        ToolTip(self.ent_batch, self.tr("Righe per richiesta."))

        f_n01 = self._make_grid_frame(f_num, 0, 1)
        ttk.Label(f_n01, text=self.tr("RPM Limit"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_rpm = PlaceholderEntry(f_n01, "Max", width=6)
        self.ent_rpm.pack(fill="x", pady=(2,0))
        ToolTip(self.ent_rpm, self.tr("Richieste per minuto massime."))

        f_n10 = self._make_grid_frame(f_num, 1, 0)
        ttk.Label(f_n10, text=self.tr("Max Entries"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_maxentr = PlaceholderEntry(f_n10, "None", width=6)
        self.ent_maxentr.pack(fill="x", pady=(2,0))
        ToolTip(self.ent_maxentr, self.tr("Limite righe per file."))

        f_n11 = self._make_grid_frame(f_num, 1, 1)
        ttk.Label(f_n11, text=self.tr("Ctx Window"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_ctxwin = PlaceholderEntry(f_n11, "0", width=6)
        self.ent_ctxwin.pack(fill="x", pady=(2,0))
        ToolTip(self.ent_ctxwin, self.tr("Righe precedenti da inviare come contesto."))

        f_n20 = self._make_grid_frame(f_num, 2, 0)
        ttk.Label(f_n20, text=self.tr("Wrap At"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_wrap = PlaceholderEntry(f_n20, "None", width=6)
        self.ent_wrap.pack(fill="x", pady=(2,0))
        ToolTip(self.ent_wrap, self.tr("A capo automatico dopo N caratteri."))

        f_n21 = self._make_grid_frame(f_num, 2, 1)
        ttk.Label(f_n21, text=self.tr("Newline Char"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        self.ent_newline = PlaceholderEntry(f_n21, "\\n", width=6)
        self.ent_newline.pack(fill="x", pady=(2,0))
        ToolTip(self.ent_newline, self.tr("Carattere per l'a capo (es. \\n)."))

        # Glossario & Cache
        ttk.Separator(c_perf, orient="horizontal").pack(fill="x", pady=10)
        
        f_files = tk.Frame(c_perf, bg=C_CARD_BG)
        f_files.pack(fill="x")
        
        f_glo = tk.Frame(f_files, bg=C_CARD_BG)
        f_glo.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(f_glo, text=self.tr("Glossario CSV"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        f_glo_in = tk.Frame(f_glo, bg=C_CARD_BG)
        f_glo_in.pack(fill="x", pady=(2,0))
        self.ent_gloss = ttk.Entry(f_glo_in)
        self.ent_gloss.pack(side="left", fill="x", expand=True)
        if os.path.exists("glossary.csv"): self.ent_gloss.insert(0, "glossary.csv")
        ttk.Button(f_glo_in, text="...", width=3, command=lambda: self._browse_file(self.ent_gloss)).pack(side="right", padx=(5,0))
        ToolTip(self.ent_gloss, self.tr("File CSV con termini forzati (Originale,Traduzione)."))
        
        # --- MODIFICA: STYLE GUIDE ---
        f_style = tk.Frame(f_files, bg=C_CARD_BG)
        f_style.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(f_style, text=self.tr("Style Guide (.txt - Manuale Regole)"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        f_style_in = tk.Frame(f_style, bg=C_CARD_BG)
        f_style_in.pack(fill="x", pady=(2,0))
        self.ent_style = ttk.Entry(f_style_in)
        self.ent_style.pack(side="left", fill="x", expand=True)
        ttk.Button(f_style_in, text="...", width=3, command=lambda: self._browse_file(self.ent_style)).pack(side="right", padx=(5,0))
        ToolTip(self.ent_style, self.tr("Allega un file di testo con regole dettagliate di formattazione e tono di voce (es. dare del Voi, stile UI)."))
        # -----------------------------

        f_ca = tk.Frame(f_files, bg=C_CARD_BG)
        f_ca.pack(side="left", fill="x", expand=True)
        ttk.Label(f_ca, text=self.tr("File Cache JSON"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        f_ca_in = tk.Frame(f_ca, bg=C_CARD_BG)
        f_ca_in.pack(fill="x", pady=(2,0))
        self.ent_cache_file = ttk.Entry(f_ca_in)
        self.ent_cache_file.pack(side="left", fill="x", expand=True)
        if os.path.exists(AlumenCore.DEFAULT_CACHE_FILE): self.ent_cache_file.insert(0, AlumenCore.DEFAULT_CACHE_FILE)
        self.btn_cache_browse = ttk.Button(f_ca_in, text="...", width=3, command=lambda: self._browse_file(self.ent_cache_file))
        self.btn_cache_browse.pack(side="right", padx=(5,0))
        ToolTip(self.btn_cache_browse, self.tr("File JSON dove salvare/caricare le traduzioni."))

    # --- PAGE 3: API MANAGEMENT (NUOVA) ---
    def _build_page_api(self, parent):
        sf = ScrollableFrame(parent)
        sf.pack(fill="both", expand=True)
        container = ttk.Frame(sf.scrollable_frame, padding=40)
        container.pack(fill="both", expand=True)
        
        tk.Label(container, text=self.tr("Gestione Chiavi API"), bg=C_MAIN_BG, fg=C_TEXT_MAIN, font=F_H1).pack(anchor="w", pady=(0, 30))
        
        # CARD: LISTA API
        c_list = self._create_card(container, self.tr("Chiavi Caricate"))
        
        # Treeview
        cols = ("idx", "key", "status", "calls")
        self.tree_api = ttk.Treeview(c_list, columns=cols, show='headings', height=10)
        self.tree_api.heading("status", text=self.tr("Stato"))
        self.tree_api.heading("calls", text=self.tr("Chiamate"))
        
        self.tree_api.column("idx", width=40, anchor="center")
        self.tree_api.column("key", width=150, anchor="center")
        self.tree_api.column("status", width=100, anchor="center")
        self.tree_api.column("calls", width=80, anchor="center")
        
        self.tree_api.pack(fill="x", pady=(0, 10))
        
        self.tree_api.tag_configure('evenrow', background=C_INPUT_BG)
        self.tree_api.tag_configure('oddrow', background='#2A2A2E')

        # Actions Row
        f_act = tk.Frame(c_list, bg=C_CARD_BG)
        f_act.pack(fill="x")
        
        self.ent_new_api = PlaceholderEntry(f_act, "Incolla nuova API Key qui...")
        self.ent_new_api.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ttk.Button(f_act, text=self.tr("➕ Aggiungi"), style='Action.TButton', command=self._api_add).pack(side="left")
        ttk.Button(f_act, text=self.tr("🗑️ Rimuovi Selez."), command=self._api_remove).pack(side="left", padx=5)
        ttk.Button(f_act, text=self.tr("🚫 Blacklist"), style='Warn.TButton', command=self._api_blacklist).pack(side="left", padx=5)
        ttk.Button(f_act, text=self.tr("✅ Reset Tutte"), command=self._api_reset).pack(side="right")
        
        ttk.Button(c_list, text=self.tr("🔄 Aggiorna Lista"), command=self._refresh_api_list).pack(anchor="e", pady=(10,0))

    # --- PAGE 4: TOOLS ---
    def _build_page_tools(self, parent):
        sf = ScrollableFrame(parent)
        sf.pack(fill="both", expand=True)
        container = ttk.Frame(sf.scrollable_frame, padding=40)
        container.pack(fill="both", expand=True)
        
        tk.Label(container, text=self.tr("Strumenti di Utilità"), bg=C_MAIN_BG, fg=C_TEXT_MAIN, font=F_H1).pack(anchor="w", pady=(0, 30))

        # --- MODIFICA: CARD DRY RUN ---
        c_dry = self._create_card(container, self.tr("Analisi e Preventivo"))
        ttk.Label(c_dry, text=self.tr("Esegui una simulazione per calcolare token e costi stimati senza tradurre."), style='Card.TLabel').pack(anchor="w", pady=(0,10))
        
        f_dry_act = tk.Frame(c_dry, bg=C_CARD_BG)
        f_dry_act.pack(fill="x")
        
        # Checkbox sincronizzata con la variabile globale
        cb_dry = ttk.Checkbutton(f_dry_act, text=self.tr("Abilita Modalità Dry Run"), variable=self.var_dry, style="Card.TCheckbutton")
        cb_dry.pack(side="left")
        
        btn_dry = ttk.Button(f_dry_act, text=self.tr("Avvia Analisi Dry Run"), style='Action.TButton', command=self._run_dry_run_tool)
        btn_dry.pack(side="right")
        ToolTip(btn_dry, self.tr("Lancia il processo in modalità simulazione."))
        # ------------------------------

        # EXTRACTOR
        c_ex = self._create_card(container, self.tr("Estrattore Cache"))
        
        f_ex_paths = tk.Frame(c_ex, bg=C_CARD_BG)
        f_ex_paths.pack(fill="x", pady=(0, 15))
        
        f_src = tk.Frame(f_ex_paths, bg=C_CARD_BG)
        f_src.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(f_src, text=self.tr("Cartella Originali"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        f_src_in = tk.Frame(f_src, bg=C_CARD_BG)
        f_src_in.pack(fill="x", pady=(2,0))
        self.ent_ex_src = ttk.Entry(f_src_in)
        self.ent_ex_src.pack(side="left", fill="x", expand=True)
        ttk.Button(f_src_in, text="📂", width=3, command=lambda: self._browse_folder(self.ent_ex_src)).pack(side="right", padx=(5,0))
        
        f_tgt = tk.Frame(f_ex_paths, bg=C_CARD_BG)
        f_tgt.pack(side="left", fill="x", expand=True)
        ttk.Label(f_tgt, text=self.tr("Cartella Tradotti"), style='Card.TLabel', font=F_SMALL, foreground=C_TEXT_SEC).pack(anchor="w")
        f_tgt_in = tk.Frame(f_tgt, bg=C_CARD_BG)
        f_tgt_in.pack(fill="x", pady=(2,0))
        self.ent_ex_tgt = ttk.Entry(f_tgt_in)
        self.ent_ex_tgt.pack(side="left", fill="x", expand=True)
        ttk.Button(f_tgt_in, text="📂", width=3, command=lambda: self._browse_folder(self.ent_ex_tgt)).pack(side="right", padx=(5,0))
        
        f_ex_opts = tk.Frame(c_ex, bg=C_CARD_BG)
        f_ex_opts.pack(fill="x", pady=(0, 15))
        
        ttk.Label(f_ex_opts, text=self.tr("Formato:"), style='Card.TLabel').pack(side="left")
        self.cmb_ex_fmt = ttk.Combobox(f_ex_opts, values=["csv", "json", "po"], width=10, state="readonly")
        self.cmb_ex_fmt.current(0)
        self.cmb_ex_fmt.bind("<<ComboboxSelected>>", self._update_extractor_ui)
        self.cmb_ex_fmt.pack(side="left", padx=(10, 20))
        
        # Opzioni dinamiche
        self.f_ex_csv_opts = tk.Frame(f_ex_opts, bg=C_CARD_BG)
        self.f_ex_csv_opts.pack(side="left", fill="x", expand=True)
        self.ent_ex_col_src = PlaceholderEntry(self.f_ex_csv_opts, "3", width=5)
        self.ent_ex_col_tgt = PlaceholderEntry(self.f_ex_csv_opts, "3", width=5)
        
        f_c1 = tk.Frame(self.f_ex_csv_opts, bg=C_CARD_BG)
        f_c1.pack(side="left", expand=True, fill="x")
        ttk.Label(f_c1, text=self.tr("Col. Orig:"), style='Card.TLabel', font=F_SMALL).pack(side="left")
        self.ent_ex_col_src.pack(side="left", padx=(5, 15), fill="x", expand=True)
        
        f_c2 = tk.Frame(self.f_ex_csv_opts, bg=C_CARD_BG)
        f_c2.pack(side="left", expand=True, fill="x")
        ttk.Label(f_c2, text=self.tr("Col. Trad:"), style='Card.TLabel', font=F_SMALL).pack(side="left")
        self.ent_ex_col_tgt.pack(side="left", padx=(5, 0), fill="x", expand=True)

        self.f_ex_json_opts = tk.Frame(f_ex_opts, bg=C_CARD_BG)
        self.ent_ex_json_keys = PlaceholderEntry(self.f_ex_json_opts, "es. title, description")
        ttk.Label(self.f_ex_json_opts, text=self.tr("Keys:"), style='Card.TLabel', font=F_SMALL).pack(side="left")
        self.ent_ex_json_keys.pack(side="left", padx=(5, 0), fill="x", expand=True)

        btn_ex = ttk.Button(c_ex, text=self.tr("Esegui Estrazione"), style='Action.TButton', command=self._run_extractor_tool)
        btn_ex.pack(anchor="e")
        ToolTip(btn_ex, self.tr("Crea un file cache JSON confrontando i file originali e tradotti."))
        self._update_extractor_ui()

        # SCANNER
        c_scan = self._create_card(container, self.tr("Auto-Glossary Scanner"))
        ttk.Label(c_scan, text=self.tr("Analizza i file per trovare Nomi Propri e Termini Unici."), style='Card.TLabel').pack(anchor="w", pady=(0,10))
        f_scan = tk.Frame(c_scan, bg=C_CARD_BG)
        f_scan.pack(fill="x")
        ttk.Label(f_scan, text=self.tr("Formato File:"), style='Card.TLabel').pack(side="left")
        self.cmb_scan_fmt = ttk.Combobox(f_scan, values=["csv", "json", "po", "srt"], width=10, state="readonly")
        self.cmb_scan_fmt.current(0)
        self.cmb_scan_fmt.pack(side="left", padx=(10, 20))
        btn_sc = ttk.Button(f_scan, text=self.tr("Avvia Scansione"), style='Action.TButton', command=self._run_scanner_tool)
        btn_sc.pack(side="right")
        ToolTip(btn_sc, self.tr("Usa l'AI per estrarre una lista di termini univoci dai file di input."))

    # --- PAGE 5: LOG ---
    def _build_page_log(self, parent):
        container = ttk.Frame(parent, padding=30)
        container.pack(fill="both", expand=True)
        
        f_head = tk.Frame(container, bg=C_MAIN_BG)
        f_head.pack(fill="x", pady=(0, 15))
        tk.Label(f_head, text=self.tr("Console di Esecuzione"), bg=C_MAIN_BG, fg=C_TEXT_MAIN, font=F_H1).pack(side="left")
        
        # --- MODIFICA: Pulsante Vedi Prompt ---
        self.btn_view_prompt = ttk.Button(f_head, text=self.tr("👁️ Vedi Prompt"), command=self._show_last_prompt)
        self.btn_view_prompt.pack(side="right", padx=(10, 0))
        ToolTip(self.btn_view_prompt, self.tr("Visualizza l'ultimo prompt inviato all'AI."))
        # --------------------------------------

        self.btn_save_cache = ttk.Button(f_head, text=self.tr("💾 Salva Cache"), command=self._force_save_cache)
        self.btn_save_cache.pack(side="right")
        ToolTip(self.btn_save_cache, self.tr("Forza il salvataggio immediato della cache su disco."))
        
        # Stats Dashboard
        f_info = tk.Frame(container, bg=C_MAIN_BG)
        f_info.pack(fill="x", pady=(0, 20))
        
        for i in range(4): f_info.grid_columnconfigure(i, weight=1)
        
        def make_stat_card(parent, row, col, label, color, colspan=1):
            card = tk.Frame(parent, bg=C_CARD_BG, highlightbackground=C_BORDER, highlightthickness=1)
            card.grid(row=row, column=col, columnspan=colspan, padx=5, pady=5, sticky="nsew")
            l_val = tk.Label(card, text="0", bg=C_CARD_BG, font=("Segoe UI", 24, "bold"), fg=color)
            l_val.pack(pady=(15, 0))
            tk.Label(card, text=label, bg=C_CARD_BG, font=F_SMALL, fg=C_TEXT_SEC).pack(pady=(0, 15))
            return l_val

        self.lbl_stats_files = make_stat_card(f_info, 0, 0, self.tr("FILE COMPLETATI"), C_ACCENT)
        self.lbl_stats_entries = make_stat_card(f_info, 0, 1, self.tr("RIGHE TRADOTTE"), C_SUCCESS)
        self.lbl_stats_cache = make_stat_card(f_info, 0, 2, self.tr("VOCI IN CACHE"), C_WARN)
        self.lbl_stats_api_calls = make_stat_card(f_info, 0, 3, self.tr("CHIAMATE API"), "#9D88E3")
        
        self.lbl_stats_tokens_in = make_stat_card(f_info, 1, 0, self.tr("TOKEN INPUT"), "#4EABA6")
        self.lbl_stats_tokens_out = make_stat_card(f_info, 1, 1, self.tr("TOKEN OUTPUT"), "#4EABA6")
        self.lbl_stats_time = make_stat_card(f_info, 1, 2, self.tr("TEMPO TOTALE"), "#E0E0E0", colspan=2)

        # Terminal & Progress Wrapper
        c_term = tk.Frame(container, bg=C_CARD_BG, highlightbackground=C_BORDER, highlightthickness=1)
        c_term.pack(fill="both", expand=True, pady=(0, 10))

        # Terminal Header (macOS style)
        f_term_head = tk.Frame(c_term, bg="#2D2D30", height=28)
        f_term_head.pack(fill="x")
        f_term_head.pack_propagate(False)

        f_dots = tk.Frame(f_term_head, bg="#2D2D30")
        f_dots.pack(side="left", padx=10)
        tk.Label(f_dots, text="⬤", fg="#FF5F56", bg="#2D2D30", font=("Arial", 10)).pack(side="left", padx=2)
        tk.Label(f_dots, text="⬤", fg="#FFBD2E", bg="#2D2D30", font=("Arial", 10)).pack(side="left", padx=2)
        tk.Label(f_dots, text="⬤", fg="#27C93F", bg="#2D2D30", font=("Arial", 10)).pack(side="left", padx=2)

        tk.Label(f_term_head, text=self.tr("Alumen Console Output"), bg="#2D2D30", fg=C_TEXT_SEC, font=F_SMALL).pack(side="left", padx=10)

        # Progress Bar under header
        f_prog = tk.Frame(c_term, bg=C_CARD_BG, pady=8, padx=15)
        f_prog.pack(fill="x")
        f_prog.columnconfigure(1, weight=1)
        
        tk.Label(f_prog, text=self.tr("Progresso:"), bg=C_CARD_BG, font=F_SMALL, fg=C_TEXT_MAIN).grid(row=0, column=0, sticky="w", padx=(0,10))
        self.progress_bar = ttk.Progressbar(f_prog, orient="horizontal", mode="determinate", style="Flat.Horizontal.TProgressbar")
        self.progress_bar.grid(row=0, column=1, sticky="ew")
        self.lbl_file_status = tk.Label(f_prog, text=self.tr("In attesa..."), bg=C_CARD_BG, font=F_SMALL, fg=C_TEXT_SEC)
        self.lbl_file_status.grid(row=0, column=2, sticky="e", padx=(10,0))

        # Terminal Text Area
        self.txt_log = scrolledtext.ScrolledText(c_term, state='disabled', font=F_MONO, 
                                                 bg="#0D0D0D", fg="#D4D4D4", relief="flat", padx=15, pady=15, insertbackground="white")
        self.txt_log.pack(fill="both", expand=True)
        
        # Syntax highlighting tags
        self.txt_log.tag_config("error", foreground="#FF5F56")
        self.txt_log.tag_config("success", foreground="#27C93F")
        self.txt_log.tag_config("warn", foreground="#FFBD2E")
        self.txt_log.tag_config("info", foreground="#58A6FF")
        self.txt_log.tag_config("dim", foreground="#666666")
        
        # Action Control Bar
        f_act_wrap = tk.Frame(container, bg=C_MAIN_BG, pady=15)
        f_act_wrap.pack(fill="x")

        f_act = tk.Frame(f_act_wrap, bg=C_MAIN_BG)
        f_act.pack(fill="x")
        
        for i in range(4): f_act.columnconfigure(i, weight=1, uniform="btn")

        self.btn_run = ttk.Button(f_act, text=self.tr("▶  AVVIA PROCESSO"), style='Action.TButton', command=self._start_process)
        self.btn_run.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ToolTip(self.btn_run, self.tr("Avvia la traduzione con le impostazioni correnti."))
        
        self.btn_pause = ttk.Button(f_act, text=self.tr("⏸  PAUSA"), style='Warn.TButton', command=self._toggle_pause, state='disabled')
        self.btn_pause.grid(row=0, column=1, sticky="ew", padx=5)
        ToolTip(self.btn_pause, self.tr("Mette in pausa il processo (completa il batch corrente)."))
        
        self.btn_skip = ttk.Button(f_act, text=self.tr("⏭  SALTA FILE"), style='Secondary.TButton', command=self._skip_file, state='disabled')
        self.btn_skip.grid(row=0, column=2, sticky="ew", padx=5)
        ToolTip(self.btn_skip, self.tr("Interrompe il file corrente e passa al successivo."))
        
        self.btn_stop = ttk.Button(f_act, text=self.tr("⏹  STOP"), style='Danger.TButton', command=self._stop_process)
        self.btn_stop.grid(row=0, column=3, sticky="ew", padx=(5, 0))
        ToolTip(self.btn_stop, self.tr("Interrompe completamente il processo."))

    # --- LOGIC ---
    def _toggle_ai_provider(self):
        provider = self.var_ai_provider.get()
        if provider == "gemini":
            self.f_ollama.pack_forget()
            self.f_gemini.pack(fill="x", pady=(10, 0))
            self.var_ollama_enabled.set(False)
        else:
            self.f_gemini.pack_forget()
            self.f_ollama.pack(fill="x", pady=(10, 0))
            self.var_ollama_enabled.set(True)

    def _check_update_thread(self):
        def _w():
            new_ver = AlumenCore.check_for_updates()
            if new_ver: 
                self.status_var.set(self.tr("Aggiornamento disponibile: v") + str(new_ver))
                messagebox.showinfo(self.tr("Aggiornamento"), f"Versione {new_ver} " + self.tr(" disponibile su GitHub!"))
        threading.Thread(target=_w, daemon=True).start()

    def _update_ui_states(self, event=None):
        if not self.is_initialized: return # Evita crash all'avvio
        
        state_cache = 'normal' if self.var_cache.get() else 'disabled'
        self.ent_cache_file.config(state=state_cache)
        if hasattr(self, 'btn_cache_browse'):
            self.btn_cache_browse.config(state=state_cache)
        self.btn_save_cache.config(state=state_cache)
        
        if hasattr(self, 'cb_full_sample'): # Controllo di sicurezza aggiunto
            if self.var_file_ctx.get(): self.cb_full_sample.config(state='normal')
            else:
                self.cb_full_sample.config(state='disabled')
                self.var_full_sample.set(False)
            
        fmt = self.cmb_fmt.get()
        state_csv = 'normal' if fmt in ['csv', 'xlsx'] else 'disabled'
        if isinstance(self.ent_delim, PlaceholderEntry): self.ent_delim.config(state='normal' if fmt == 'csv' else 'disabled')
        self.ent_col.config(state=state_csv)
        self.ent_col_out.config(state=state_csv)
        self.ent_maxcols.config(state=state_csv)
        
        # Excel specific
        state_xlsx = 'normal' if fmt == 'xlsx' else 'disabled'
        if hasattr(self, 'ent_xlsx_src'):
            self.ent_xlsx_src.config(state=state_xlsx)
            self.ent_xlsx_tgt.config(state=state_xlsx)
        
        state_json = 'normal' if fmt == 'json' else 'disabled'
        if isinstance(self.ent_jkeys, ttk.Entry): self.ent_jkeys.config(state=state_json)

    def _toggle_telegram_ui(self):
        enable = self.var_tg_enabled.get()
        state = 'normal' if enable else 'disabled'
        self.ent_tg_token.config(state=state)
        self.ent_tg_chatid.config(state=state)
        self.btn_tg_save.config(state=state)
        if enable and not self.ent_tg_token.get(): self._load_telegram_config_internal()

    def _load_telegram_config_internal(self):
        if os.path.exists("telegram_config.json"):
            try:
                with open("telegram_config.json", "r") as f:
                    data = json.load(f)
                    self.ent_tg_token.config(state='normal')
                    self.ent_tg_chatid.config(state='normal')
                    self.ent_tg_token.delete(0, tk.END)
                    self.ent_tg_token.insert(0, data.get("bot_token", ""))
                    self.ent_tg_chatid.delete(0, tk.END)
                    self.ent_tg_chatid.insert(0, data.get("chat_id", ""))
            except: pass

    def _save_telegram_config(self):
        t = self.ent_tg_token.get().strip()
        c = self.ent_tg_chatid.get().strip()
        if not t or not c:
            messagebox.showwarning(self.tr("Attenzione"), self.tr("Inserisci Token e Chat ID"))
            return
        try:
            with open("telegram_config.json", "w") as f:
                json.dump({"bot_token": t, "chat_id": c}, f, indent=4)
            messagebox.showinfo(self.tr("Fatto"), self.tr("Salvataggio OK"))
        except Exception as e: messagebox.showerror(self.tr("Errore"), str(e))

    def _load_api_file(self):
        f = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if f: self._load_api_file_internal(f)
    def _load_api_file_internal(self, filepath):
        self.api_file_path = filepath
        fname = os.path.basename(filepath)
        self.ent_api.pack_forget()
        self.f_file_loaded.pack(side="left", fill="x", expand=True, padx=10)
        self.lbl_file_loaded.config(text=f"📄 {fname}")
        try:
            with open(filepath, "r") as f:
                k = f.readline().strip()
                if k: self._refresh_models_auto(k)
        except: pass
    def _clear_api_file(self):
        self.api_file_path = None
        self.f_file_loaded.pack_forget()
        self.ent_api.pack(side="left", fill="x", expand=True, padx=10)
        self.ent_api.delete(0, tk.END)
    def _refresh_models_auto(self, override_key=None):
        key = override_key if override_key else self.ent_api.get().split(',')[0].strip()
        if not key: return
        self.status_var.set(self.tr("Recupero modelli..."))
        def _w():
            ms = AlumenCore.fetch_available_models(key)
            def _u():
                if ms and not str(ms[0]).startswith("Errore"):
                    curr = self.cmb_model.get()
                    self.cmb_model['values'] = tuple(ms)
                    if curr not in ms: self.cmb_model.current(0)
                    self.status_var.set(self.tr("Modelli aggiornati"))
                else: self.status_var.set(self.tr("Errore recupero modelli"))
            self.root.after(0, _u)
        threading.Thread(target=_w, daemon=True).start()

    def _refresh_ollama_models(self):
        host = self.ent_ollama_host.get()
        if not host: return
        self.status_var.set(self.tr("Connessione a Ollama..."))
        def _w():
            models = AlumenCore.fetch_ollama_models(host)
            def _u():
                self.cmb_ollama_model['values'] = tuple(models)
                if models: 
                    self.cmb_ollama_model.current(0)
                    self.status_var.set(self.tr("Modelli Ollama caricati"))
                else: self.status_var.set(self.tr("Nessun modello Ollama trovato"))
            self.root.after(0, _u)
        threading.Thread(target=_w, daemon=True).start()

    def _browse_folder(self, entry_field, is_input=False):
        d = filedialog.askdirectory()
        if d: 
            entry_field.delete(0, tk.END)
            entry_field.insert(0, d)
            if is_input:
                self.ent_output.delete(0, tk.END)
                self.ent_output.insert(0, "output")
    def _browse_file(self, entry_field):
        f = filedialog.askopenfilename()
        if f:
            if isinstance(entry_field, PlaceholderEntry): entry_field.set_text(f)
            else: entry_field.delete(0, tk.END); entry_field.insert(0, f)
    def _poll_log_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.txt_log.configure(state='normal')
            
            tag = None
            msg_l = msg.lower()
            if "errore" in msg_l or "🛑" in msg: tag = "error"
            elif "✅" in msg or "completato" in msg_l: tag = "success"
            elif "⚠️" in msg or "attenzione" in msg_l or "skip" in msg_l: tag = "warn"
            elif "ℹ️" in msg or "➡️" in msg: tag = "info"
            elif "---" in msg: tag = "dim"
            
            if tag: self.txt_log.insert(tk.END, msg + "\n", tag)
            else: self.txt_log.insert(tk.END, msg + "\n")
            
            self.txt_log.see(tk.END)
            self.txt_log.configure(state='disabled')
        self.root.after(100, self._poll_log_queue)
    def _update_stats(self):
        files = AlumenCore.total_files_translated
        entries = AlumenCore.total_entries_translated
        cache_size = len(AlumenCore.translation_cache)
        
        # --- MODIFICA: Lettura Token e API ---
        tok_in = AlumenCore.total_input_tokens
        tok_out = AlumenCore.total_output_tokens
        api_calls = sum(AlumenCore.api_call_counts.values())
        
        elapsed = int(AlumenCore.get_elapsed_time())
        
        h, r = divmod(elapsed, 3600)
        m, s = divmod(r, 60)
        time_str = f"{h}h {m}m {s}s"
        # -------------------------------------

        self.lbl_stats_files.config(text=f"{files}")
        self.lbl_stats_entries.config(text=f"{entries}")
        self.lbl_stats_cache.config(text=f"{cache_size}")
        
        # --- MODIFICA: Aggiornamento Label Token e API ---
        if hasattr(self, 'lbl_stats_tokens_in'):
            self.lbl_stats_tokens_in.config(text=f"{tok_in}")
            self.lbl_stats_tokens_out.config(text=f"{tok_out}")
            self.lbl_stats_api_calls.config(text=f"{api_calls}")
            self.lbl_stats_time.config(text=time_str)
        # -------------------------------------------------
        
        # --- MODIFICA: Aggiornamento Progress Bar File ---
        if hasattr(self, 'progress_bar'):
            total = AlumenCore.current_file_total_entries
            processed = AlumenCore.current_file_processed_entries
            if total > 0:
                perc = (processed / total) * 100
                self.progress_bar['value'] = perc
                
                # Stima tempo rimanente (molto grezza)
                if processed > 0 and elapsed > 0:
                    avg_time_per_entry = elapsed / (entries if entries > 0 else 1) # Media globale
                    remaining_entries = total - processed
                    est_seconds = int(remaining_entries * avg_time_per_entry)
                    m_rem, s_rem = divmod(est_seconds, 60)
                    self.lbl_file_status.config(text=f"{processed}/{total} ({perc:.1f}%) - " + self.tr("Stima fine file: ") + f"{m_rem}m {s_rem}s")
                else:
                    self.lbl_file_status.config(text=f"{processed}/{total} ({perc:.1f}%)")
            else:
                self.progress_bar['value'] = 0
                self.lbl_file_status.config(text="In attesa...")
        # -------------------------------------------------
        
        # Aggiorna lista API se siamo nella tab API
        if self.current_page == "api":
            self._refresh_api_list()

        if self.is_running: self.status_var.set(self.tr("In esecuzione...") + f" {files}" + self.tr(" file completati"))
        self.root.after(1000, self._update_stats)

    def _update_spinner(self):
        if self.is_running:
            self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
            spin = self.spinner_chars[self.spinner_idx]
            files = AlumenCore.total_files_translated
            self.status_var.set(f"{spin} " + self.tr("In esecuzione...") + f" {files}" + self.tr(" file completati"))
        self.root.after(100, self._update_spinner)

    def _force_save_cache(self):
        if self.current_args and self.var_cache.get():
            AlumenCore.check_and_save_cache(self.current_args, force=True)
            self.status_var.set(self.tr("Cache salvata su disco"))
        else:
            class MockArgs: persistent_cache = True; cache_file = None
            AlumenCore.check_and_save_cache(MockArgs(), force=True)
    
    def _toggle_pause(self):
        if not self.is_running: return
        if self.pause_event.is_set():
            self.pause_event.clear() # Pause
            AlumenCore.pause_start_timestamp = time.time()
            self.btn_pause.config(text=self.tr("▶ RIPRENDI"), style='Action.TButton')
            self.status_var.set(self.tr("Processo in PAUSA"))
            self.log_queue.put(self.tr("⏸️ Richiesta di PAUSA inviata...")) # Feedback immediato
        else:
            self.pause_event.set() # Resume
            AlumenCore.total_paused_time += (time.time() - AlumenCore.pause_start_timestamp)
            self.btn_pause.config(text=self.tr("⏸ PAUSA"), style='Warn.TButton')
            self.status_var.set(self.tr("Processo RIPRESO"))
            self.log_queue.put(self.tr("▶️ Richiesta di RIPRESA inviata...")) # Feedback immediato
    def _skip_file(self):
        if not self.is_running: return
        self.skip_event.set()
        self.status_var.set(self.tr("Salto file corrente..."))
        self.log_queue.put(self.tr("⏭️ Richiesta di SKIP FILE inviata...")) # Feedback immediato
    def _stop_process(self):
        if self.stop_event.is_set(): return
        self.stop_event.set()
        AlumenCore.final_elapsed_time = AlumenCore.get_elapsed_time()
        self.log_queue.put(self.tr("🛑 Richiesta di STOP inviata...")) # Feedback immediato
        self.is_running = False
        self.btn_pause.config(state='disabled')
        self.btn_skip.config(state='disabled')
        self.status_var.set(self.tr("Processo INTERROTTO"))

    # --- MODIFICA: Funzione per mostrare l'ultimo prompt ---
    def _show_last_prompt(self):
        prompt = AlumenCore.last_translation_prompt
        if not prompt:
            messagebox.showinfo(self.tr("Info"), self.tr("Nessun prompt inviato finora."))
            return
        
        top = tk.Toplevel(self.root)
        top.title(self.tr("Ultimo Prompt Inviato"))
        top.geometry("700x500")
        top.configure(bg=C_MAIN_BG)
        
        st = scrolledtext.ScrolledText(top, bg="#0D0D0D", fg="#2ecc71", font=F_MONO, padx=15, pady=15)
        st.pack(fill="both", expand=True)
        st.insert(tk.END, prompt)
        st.configure(state='disabled')
    # -------------------------------------------------------

    # --- API MANAGEMENT LOGIC ---
    def _refresh_api_list(self):
        if not hasattr(self, 'tree_api'): return
        
        # Salva selezione corrente
        selected_item = self.tree_api.selection()
        selected_idx = None
        if selected_item:
            try:
                selected_idx = self.tree_api.item(selected_item[0])['values'][0]
            except: pass

        # Pulisci
        for item in self.tree_api.get_children():
            self.tree_api.delete(item)
        
        keys = AlumenCore.available_api_keys
        curr_idx = AlumenCore.current_api_key_index
        bl = AlumenCore.blacklisted_api_key_indices
        counts = AlumenCore.api_call_counts
        
        for i, k in enumerate(keys):
            short_k = f"...{k[-6:]}" if len(k) > 6 else k
            status = self.tr("In Attesa")
            if i == curr_idx: status = self.tr("🟢 ATTIVA")
            if i in bl: status = self.tr("🔴 BLACKLIST")
            
            calls = counts.get(i, 0)

            tags = ('evenrow',) if i % 2 == 0 else ('oddrow',)
            item_id = self.tree_api.insert('', 'end', values=(i, short_k, status, calls), tags=tags)
            
            # Ripristina selezione
            if selected_idx is not None and i == selected_idx:
                self.tree_api.selection_set(item_id)

    def _api_add(self):
        k = self.ent_new_api.get_valid_value().strip()
        if not k: return
        AlumenCore.add_api_key(k)
        self.ent_new_api.delete(0, tk.END)
        self._refresh_api_list()
        messagebox.showinfo(self.tr("Info"), self.tr("API Key aggiunta."))

    def _api_remove(self):
        sel = self.tree_api.selection()
        if not sel: return
        item = self.tree_api.item(sel[0])
        idx = item['values'][0]
        AlumenCore.remove_api_key(str(idx))
        self._refresh_api_list()

    def _api_blacklist(self):
        sel = self.tree_api.selection()
        if not sel: return
        item = self.tree_api.item(sel[0])
        idx = int(item['values'][0])
        
        # Toggle logic: se è già blacklisted, rimuovi. Altrimenti aggiungi.
        if idx in AlumenCore.blacklisted_api_key_indices:
            AlumenCore.blacklisted_api_key_indices.discard(idx)
        else:
            AlumenCore.blacklisted_api_key_indices.add(idx)
            # Se era quella attiva, ruota
            if idx == AlumenCore.current_api_key_index:
                AlumenCore.rotate_api_key(reason_override="Manuale da GUI")
        
        self._refresh_api_list()

    def _api_reset(self):
        AlumenCore.clear_blacklisted_keys()
        self._refresh_api_list()
        messagebox.showinfo(self.tr("Info"), self.tr("Blacklist resettata."))
    # ----------------------------

    def _run_dry_run_tool(self):
        # Forza il flag dry_run a True e avvia il processo
        self.var_dry.set(True)
        self._start_process()

    def _update_extractor_ui(self, event=None):
        fmt = self.cmb_ex_fmt.get()
        self.f_ex_csv_opts.pack_forget()
        self.f_ex_json_opts.pack_forget()
        if fmt == 'csv': self.f_ex_csv_opts.pack(side="left", fill="x", expand=True)
        elif fmt == 'json': self.f_ex_json_opts.pack(side="left", padx=(5, 0), fill="x", expand=True)

    def _run_extractor_tool(self):
        s = self.ent_ex_src.get()
        t = self.ent_ex_tgt.get()
        if not s or not t: messagebox.showerror(self.tr("Errore"), self.tr("Seleziona cartelle!")); return
        
        fmt = self.cmb_ex_fmt.get()
        try: col_s = int(self.ent_ex_col_src.get_valid_value())
        except: col_s = 3
        try: col_t = int(self.ent_ex_col_tgt.get_valid_value())
        except: col_t = 3
        json_keys = self.ent_ex_json_keys.get_valid_value()

        self._show_frame("log")
        self.status_var.set(self.tr("Estrazione cache in corso..."))
        threading.Thread(target=lambda: AlumenCore.run_cache_extractor(s, t, fmt, col_s, col_t, "utf-8", json_keys=json_keys), daemon=True).start()
    def _run_scanner_tool(self):
        inp = self.ent_input.get()
        api = self.ent_api.get()
        if not api and not self.api_file_path: messagebox.showerror(self.tr("Errore"), self.tr("API Key necessaria")); return
        fmt = self.cmb_scan_fmt.get()
        self.status_var.set(self.tr("Scansione termini in corso..."))
        def _w():
            t = AlumenCore.run_term_scanner(inp, fmt, "utf-8")
            self.log_queue.put(f"{self.tr('Termini trovati (formato ')}{fmt}):\n{t}")
            self.status_var.set(self.tr("Scansione completata"))
        self._show_frame("log")
        threading.Thread(target=_w, daemon=True).start()

    def _start_process(self):
        class Args: pass
        a = Args()
        a.api_file = self.api_file_path
        a.api = None if a.api_file else self.ent_api.get()
        
        a.use_ollama = self.var_ollama_enabled.get()
        a.ollama_url = self.ent_ollama_host.get()
        a.ollama_model = self.cmb_ollama_model.get() if a.use_ollama else None
        a.model_name = self.cmb_model.get()

        if not a.use_ollama and not a.api and not a.api_file: messagebox.showerror(self.tr("Errore"), self.tr("Manca API Key!")); return
        if a.use_ollama and not a.ollama_model: messagebox.showerror(self.tr("Errore"), self.tr("Seleziona un modello Ollama!")); return

        a.input = self.ent_input.get() # Fix: Aggiunto attributo input
        a.output_dir = self.ent_output.get()
        a.file_type = self.cmb_fmt.get()
        a.source_lang = self.ent_src.get()
        a.target_lang = self.ent_tgt.get()
        val = self.ent_encoding.get_valid_value()
        a.encoding = val if val else "utf-8"
        a.game_name = self.ent_gamename.get_valid_value()
        val = self.ent_delim.get_valid_value()
        a.delimiter = val if val else ","
        try: a.translate_col = int(self.ent_col.get_valid_value())
        except: a.translate_col = 3
        try: a.output_col = int(self.ent_col_out.get_valid_value())
        except: a.output_col = 3
        a.json_keys = self.ent_jkeys.get_valid_value()
        a.match_full_json_path = self.var_jmatch.get()
        a.glossary = self.ent_gloss.get()
        a.style_guide = self.ent_style.get() # Fix: Aggiunto parametro style_guide
        a.cache_file = self.ent_cache_file.get()
        a.custom_prompt = self.ent_prompt.get_valid_value()
        a.prompt_context = self.ent_pctx.get_valid_value()
        val_nl = self.ent_newline.get_valid_value()
        a.newline_char = val_nl if val_nl else "\\n"
        try: a.batch_size = int(self.ent_batch.get_valid_value())
        except: a.batch_size = 30
        try: a.rpm = int(self.ent_rpm.get_valid_value())
        except: a.rpm = None
        try: a.wrap_at = int(self.ent_wrap.get_valid_value())
        except: a.wrap_at = None
        try: a.context_window = int(self.ent_ctxwin.get_valid_value())
        except: a.context_window = 0
        try: a.max_cols = int(self.ent_maxcols.get_valid_value())
        except: a.max_cols = None
        try: a.max_entries = int(self.ent_maxentr.get_valid_value())
        except: a.max_entries = None
        a.persistent_cache = self.var_cache.get()
        a.rotate_on_limit_or_error = self.var_rotate.get()
        a.dry_run = self.var_dry.get()
        a.translation_only_output = self.var_transonly.get()
        a.server = self.var_server.get()
        a.telegram = self.var_tg_enabled.get()
        a.telegram_token = self.ent_tg_token.get()
        a.telegram_chat_id = self.ent_tg_chatid.get()
        a.resume = self.var_resume.get()
        a.enable_file_log = self.var_filelog.get()
        a.enable_file_context = self.var_file_ctx.get()
        a.full_context_sample = self.var_full_sample.get()
        a.reflect = self.var_reflect.get()
        a.fuzzy_match = self.var_fuzzy.get()
        a.shutdown = self.var_shutdown.get() # Fix: Aggiunto parametro shutdown
        a.upload_to_gemini = self.var_upload.get()
        a.interactive = True # Fix: Abilita modalità interattiva per supportare pausa/skip
        
        # Excel params
        a.xlsx_source_col = self.ent_xlsx_src.get_valid_value() if hasattr(self, 'ent_xlsx_src') else "A"
        a.xlsx_target_col = self.ent_xlsx_tgt.get_valid_value() if hasattr(self, 'ent_xlsx_tgt') else "B"

        if a.file_type == "json" and not a.json_keys and not a.dry_run:
            messagebox.showerror(self.tr("Errore"), self.tr("JSON richiede chiavi!"))
            return

        self.current_args = a
        self.stop_event.clear()
        self.pause_event.set() 
        self.skip_event.clear()
        self.is_running = True
        self.btn_pause.config(state='normal', text=self.tr("⏸ PAUSA"), style='Warn.TButton')
        self.btn_skip.config(state='normal')
        self.txt_log.configure(state='normal')
        self.txt_log.delete(1.0, tk.END)
        self.txt_log.configure(state='disabled')
        self._show_frame("log")
        self.status_var.set(self.tr("Avvio traduzione..."))
        
        # Avviso di avvio
        messagebox.showinfo(self.tr("Processo Avviato"), self.tr("La traduzione è iniziata. Puoi monitorare l'avanzamento nella scheda 'Esecuzione'."))
        
        # Funzione wrapper per il thread che include la callback finale
        def thread_wrapper():
            AlumenCore.run_core_process(a, self.log_queue, self.stop_event, self.pause_event, self.skip_event)
            self.root.after(0, self._on_process_finished)

        t = threading.Thread(target=thread_wrapper, daemon=True)
        t.start()

    def _on_process_finished(self):
        """Callback eseguita nel thread principale alla fine del processo."""
        AlumenCore.final_elapsed_time = AlumenCore.get_elapsed_time()
        self.is_running = False
        self.status_var.set(self.tr("Pronto"))
        messagebox.showinfo(self.tr("Processo Terminato"), self.tr("Il lavoro è stato completato."))

    def _collect_args(self):
        class Args: pass
        a = Args()
        a.game_name = self.ent_gamename.get_valid_value() if self.ent_gamename.get_valid_value() else "un videogioco generico"
        a.source_lang = self.ent_src.get()
        a.target_lang = self.ent_tgt.get()
        a.custom_prompt = self.ent_prompt.get_valid_value()
        a.use_ollama = self.var_ollama_enabled.get()
        a.ollama_model = self.cmb_ollama_model.get() if a.use_ollama else None
        a.ollama_url = self.ent_ollama_host.get()
        a.prompt_context = self.ent_pctx.get_valid_value()
        a.glossary = self.ent_gloss.get()
        a.enable_file_context = self.var_file_ctx.get()
        try: a.context_window = int(self.ent_ctxwin.get_valid_value())
        except: a.context_window = 0
        return a

    def _show_prompt_preview(self):
        args = self._collect_args()
        preview_text = AlumenCore.generate_prompt_preview(args)
        top = tk.Toplevel(self.root)
        top.title(self.tr("Prompt Preview"))
        top.geometry("800x650")
        top.configure(bg=C_MAIN_BG)
        st = scrolledtext.ScrolledText(top, bg="#0D0D0D", fg="#2ecc71", font=F_MONO, padx=15, pady=15)
        st.pack(fill="both", expand=True)
        st.insert(tk.END, preview_text)
        st.configure(state='disabled')

if __name__ == "__main__":
    root = tk.Tk()
    app = AlumenGUI(root)
    root.mainloop()