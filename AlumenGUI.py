# --- START OF FILE AlumenGUI.py ---
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import queue
import os
import json
import AlumenCore

# --- STILI ---
COLOR_BG_SIDEBAR = "#2c3e50"
COLOR_BG_SIDEBAR_ACTIVE = "#3e5871"
COLOR_BG_MAIN = "#f4f6f9"
COLOR_BG_CARD = "#ffffff"
COLOR_TEXT_HEADER = "#2c3e50"
COLOR_TEXT_SUBHEADER = "#16a085"
COLOR_TEXT_NORMAL = "#34495e"
COLOR_TEXT_SIDEBAR = "#ecf0f1"
COLOR_TEXT_PLACEHOLDER = "#95a5a6"
COLOR_BTN_ACTION = "#27ae60"
COLOR_BTN_WARN = "#f39c12"
COLOR_BTN_DANGER = "#c0392b"
COLOR_BTN_TOOL = "#8e44ad"
COLOR_BORDER = "#e0e0e0"

FONT_HEADER_PAGE = ("Segoe UI", 22, "bold")
FONT_HEADER_SECTION = ("Segoe UI", 11, "bold")
FONT_NORMAL = ("Segoe UI", 10)
FONT_SIDEBAR = ("Segoe UI", 11)
FONT_STATS = ("Segoe UI", 12, "bold")

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
                       background="#34495e", foreground="#ecf0f1",
                       relief=tk.FLAT, borderwidth=0, font=("Segoe UI", 9), padx=8, pady=4)
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
            self.config(foreground=COLOR_TEXT_NORMAL)
            self.is_active = True
    def _foc_out(self, event):
        if not self.get():
            self.insert(0, self.placeholder)
            self.config(foreground=COLOR_TEXT_PLACEHOLDER)
            self.is_active = False
        else:
            self.is_active = True
    def get_valid_value(self):
        return self.get() if self.is_active else ""
    def set_text(self, text):
        self.delete(0, tk.END)
        self.config(foreground=COLOR_TEXT_NORMAL)
        self.insert(0, text)
        self.is_active = True

class AlumenGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Alumen v2.2.1 - AI Translator")
        self.root.geometry("1200x950")
        self.root.configure(bg=COLOR_BG_MAIN)
        
        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.pause_event = threading.Event(); self.pause_event.set()
        self.skip_api_event = threading.Event()
        self.skip_event = threading.Event()
        
        self.api_file_path = None
        self.current_args = None
        self.nav_buttons = {}
        self.is_running = False
        
        self._configure_styles()
        self._init_layout()
        
        if os.path.exists("api_key.txt"):
            self._load_api_file_internal("api_key.txt")
        
        self.root.after(100, self._poll_log_queue)
        self.root.after(1000, self._update_stats)
        self.root.after(2000, self._check_update_thread)
        
        # Trigger iniziale stati UI
        self.root.after(100, self._update_ui_states)

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=COLOR_BG_MAIN)
        style.configure('Card.TFrame', background=COLOR_BG_CARD)
        style.configure('TLabel', background=COLOR_BG_MAIN, foreground=COLOR_TEXT_NORMAL, font=FONT_NORMAL)
        style.configure('Card.TLabel', background=COLOR_BG_CARD, foreground=COLOR_TEXT_NORMAL, font=FONT_NORMAL)
        style.configure('Card.TLabelframe', background=COLOR_BG_CARD, relief="solid", borderwidth=1, bordercolor=COLOR_BORDER)
        style.configure('Card.TLabelframe.Label', background=COLOR_BG_CARD, foreground=COLOR_TEXT_SUBHEADER, font=FONT_HEADER_SECTION)
        
        style.configure('TButton', font=("Segoe UI", 9), borderwidth=0, padding=6, background="#bdc3c7", foreground="#2c3e50")
        style.map('TButton', background=[('active', '#aab7b8')])
        
        style.configure('Action.TButton', background=COLOR_BTN_ACTION, foreground="white", font=("Segoe UI", 9, "bold"))
        style.map('Action.TButton', background=[('active', "#2ecc71")])
        
        style.configure('Danger.TButton', background=COLOR_BTN_DANGER, foreground="white", font=("Segoe UI", 9, "bold"))
        style.map('Danger.TButton', background=[('active', "#e74c3c")])
        
        style.configure('Warn.TButton', background=COLOR_BTN_WARN, foreground="white", font=("Segoe UI", 9, "bold"))
        style.map('Warn.TButton', background=[('active', "#e67e22")])
        
        style.configure('Tool.TButton', background=COLOR_BTN_TOOL, foreground="white", font=("Segoe UI", 9, "bold"))
        style.map('Tool.TButton', background=[('active', "#9b59b6")])
        
        style.configure('TEntry', padding=5, relief="flat", borderwidth=1, bordercolor=COLOR_BORDER)
        style.configure("Card.TCheckbutton", background=COLOR_BG_CARD, foreground=COLOR_TEXT_NORMAL, font=FONT_NORMAL)

    def _init_layout(self):
        self.sidebar = tk.Frame(self.root, bg=COLOR_BG_SIDEBAR, width=260)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        # Bottone Debug
        self.btn_debug = tk.Button(self.sidebar, text="🔍", bg=COLOR_BG_SIDEBAR, fg="#576574", bd=0, font=("Segoe UI", 12), command=self._show_prompt_preview, cursor="hand2", activebackground=COLOR_BG_SIDEBAR, activeforeground="#576574")
        self.btn_debug.place(x=220, y=680)
        ToolTip(self.btn_debug, "Preview Prompt")
        
        tk.Label(self.sidebar, text="ALUMEN", bg=COLOR_BG_SIDEBAR, fg="white", font=("Segoe UI", 24, "bold")).pack(pady=(50, 5))
        tk.Label(self.sidebar, text="AI TRANSLATION SUITE", bg=COLOR_BG_SIDEBAR, fg="#95a5a6", font=("Segoe UI", 9, "bold", "italic")).pack(pady=(0, 60))
        
        menu_container = tk.Frame(self.sidebar, bg=COLOR_BG_SIDEBAR)
        menu_container.pack(fill="x", padx=0)
        
        self.nav_buttons['conf'] = self._make_sidebar_btn(menu_container, "⚙️   Configurazione", "conf")
        self.nav_buttons['adv'] = self._make_sidebar_btn(menu_container, "🧠   Avanzate", "adv")
        self.nav_buttons['tools'] = self._make_sidebar_btn(menu_container, "🛠️   Strumenti", "tools")
        self.nav_buttons['log'] = self._make_sidebar_btn(menu_container, "🚀   Log & Esecuzione", "log")
        
        tk.Label(self.sidebar, text=f"v{AlumenCore.CURRENT_SCRIPT_VERSION}", bg=COLOR_BG_SIDEBAR, fg="#576574", font=("Segoe UI", 8)).pack(side="bottom", pady=20)
        
        self.main_area = tk.Frame(self.root, bg=COLOR_BG_MAIN)
        self.main_area.pack(side="right", fill="both", expand=True)
        self.main_area.grid_rowconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)
        
        self.frames = {}
        for page in ["conf", "adv", "tools", "log"]:
            fr = tk.Frame(self.main_area, bg=COLOR_BG_MAIN)
            fr.grid(row=0, column=0, sticky="nsew")
            self.frames[page] = fr
            
        self._build_page_conf(self.frames["conf"])
        self._build_page_adv(self.frames["adv"])
        self._build_page_tools(self.frames["tools"])
        self._build_page_log(self.frames["log"])
        
        self._show_frame("conf")

    def _make_sidebar_btn(self, parent, text, page_key):
        btn = tk.Button(parent, text=text, bg=COLOR_BG_SIDEBAR, fg=COLOR_TEXT_SIDEBAR, font=FONT_SIDEBAR, bd=0, relief=tk.FLAT, padx=30, pady=15, anchor="w", cursor="hand2", activebackground=COLOR_BG_SIDEBAR_ACTIVE, activeforeground="white", command=lambda: self._show_frame(page_key))
        btn.pack(fill="x", pady=1)
        return btn

    def _show_frame(self, page_name):
        self.frames[page_name].tkraise()
        for key, btn in self.nav_buttons.items():
            if key == page_name: btn.configure(bg=COLOR_BG_SIDEBAR_ACTIVE, fg="white", font=("Segoe UI", 11, "bold"))
            else: btn.configure(bg=COLOR_BG_SIDEBAR, fg=COLOR_TEXT_SIDEBAR, font=("Segoe UI", 11, "normal"))

    def _create_card(self, parent, title):
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill="x", pady=(0, 20))
        lf = ttk.LabelFrame(wrapper, text=f"  {title}  ", style='Card.TLabelframe', padding=20)
        lf.pack(fill="x")
        return lf

    # --- PAGINA CONFIGURAZIONE ---
    def _build_page_conf(self, parent):
        container = ttk.Frame(parent, padding=40)
        container.pack(fill="both", expand=True)
        tk.Label(container, text="Configurazione Principale", bg=COLOR_BG_MAIN, fg=COLOR_TEXT_HEADER, font=FONT_HEADER_PAGE).pack(anchor="w", pady=(0, 25))
        
        # API
        lf_api = self._create_card(container, "Connessione Google Gemini")
        f_k = ttk.Frame(lf_api, style='Card.TFrame')
        f_k.pack(fill="x", pady=(0, 15))
        ttk.Label(f_k, text="API Keys:", style='Card.TLabel', width=16).pack(side="left")
        self.ent_api = ttk.Entry(f_k)
        self.ent_api.pack(side="left", fill="x", expand=True, padx=10)
        
        self.f_file_loaded = ttk.Frame(f_k, style='Card.TFrame')
        self.lbl_file_loaded = ttk.Label(self.f_file_loaded, text="", foreground=COLOR_BTN_ACTION, font=("Segoe UI", 9, "bold"), style='Card.TLabel')
        self.lbl_file_loaded.pack(side="left", padx=5)
        # Icona cestino standard
        btn_clear_api = ttk.Button(self.f_file_loaded, text="🗑", width=3, command=self._clear_api_file)
        btn_clear_api.pack(side="left", padx=5)
        ToolTip(btn_clear_api, "Rimuovi il file API e torna all'inserimento manuale.")
        
        self.btn_load_file = ttk.Button(f_k, text="📂 Carica .txt", command=self._load_api_file)
        self.btn_load_file.pack(side="right")
        ToolTip(self.btn_load_file, "Carica una o più API key da un file .txt (una per riga).")
        
        f_m = ttk.Frame(lf_api, style='Card.TFrame')
        f_m.pack(fill="x")
        ttk.Label(f_m, text="Modello AI:", style='Card.TLabel', width=16).pack(side="left")
        self.cmb_model = ttk.Combobox(f_m, state="readonly")
        self.cmb_model['values'] = ("gemini-2.0-flash [Default]",)
        self.cmb_model.current(0)
        self.cmb_model.pack(side="left", fill="x", expand=True, padx=10)
        btn_refresh_models = ttk.Button(f_m, text="🔄 Aggiorna", command=self._refresh_models_auto)
        btn_refresh_models.pack(side="right")
        ToolTip(btn_refresh_models, "Recupera la lista dei modelli AI disponibili usando la prima API key.")

        # FILE INPUT/OUTPUT
        lf_file = self._create_card(container, "File Input / Output")
        f_in = ttk.Frame(lf_file, style='Card.TFrame')
        f_in.pack(fill="x", pady=(0, 10))
        ttk.Label(f_in, text="Cartella Input:", width=16, style='Card.TLabel').pack(side="left")
        self.ent_input = ttk.Entry(f_in)
        self.ent_input.insert(0, "input")
        self.ent_input.pack(side="left", fill="x", expand=True, padx=10)
        btn_browse_in = ttk.Button(f_in, text="📂", width=4, command=lambda: self._browse_folder(self.ent_input, is_input=True))
        btn_browse_in.pack(side="right")
        ToolTip(btn_browse_in, "Sfoglia cartella")
        
        f_out = ttk.Frame(lf_file, style='Card.TFrame')
        f_out.pack(fill="x", pady=(0, 15))
        ttk.Label(f_out, text="Cartella Output:", width=16, style='Card.TLabel').pack(side="left")
        self.ent_output = ttk.Entry(f_out)
        self.ent_output.insert(0, "output")
        self.ent_output.pack(side="left", fill="x", expand=True, padx=10)
        btn_browse_out = ttk.Button(f_out, text="📂", width=4, command=lambda: self._browse_folder(self.ent_output))
        btn_browse_out.pack(side="right")
        ToolTip(btn_browse_out, "Sfoglia cartella")
        
        f_opt = ttk.Frame(lf_file, style='Card.TFrame')
        f_opt.pack(fill="x", pady=(5, 10))
        ttk.Label(f_opt, text="Formato:", style='Card.TLabel', width=16).pack(side="left")
        self.cmb_fmt = ttk.Combobox(f_opt, values=["csv", "json", "xlsx", "po", "srt"], width=8, state="readonly")
        self.cmb_fmt.current(0)
        self.cmb_fmt.bind("<<ComboboxSelected>>", self._update_ui_states)
        self.cmb_fmt.pack(side="left", padx=(10, 30))
        ttk.Label(f_opt, text="Encoding:", style='Card.TLabel').pack(side="left")
        self.ent_encoding = PlaceholderEntry(f_opt, "utf-8", width=8)
        self.ent_encoding.pack(side="left", padx=5)

        f_lng = ttk.Frame(lf_file, style='Card.TFrame')
        f_lng.pack(fill="x")
        ttk.Label(f_lng, text="Da:", style='Card.TLabel', width=16).pack(side="left")
        self.ent_src = ttk.Entry(f_lng, width=15)
        self.ent_src.insert(0, "inglese")
        self.ent_src.pack(side="left", padx=(10, 20))
        ttk.Label(f_lng, text="A:", style='Card.TLabel').pack(side="left")
        self.ent_tgt = ttk.Entry(f_lng, width=15)
        self.ent_tgt.insert(0, "italiano")
        self.ent_tgt.pack(side="left", padx=10)
        
        f_game = ttk.Frame(lf_file, style='Card.TFrame')
        f_game.pack(fill="x", pady=(10,0))
        ttk.Label(f_game, text="Nome Gioco:", style='Card.TLabel', width=16).pack(side="left")
        self.ent_gamename = PlaceholderEntry(f_game, "un videogioco generico")
        self.ent_gamename.pack(side="left", fill="x", expand=True, padx=10)

        # TELEGRAM CONFIG
        lf_tg = self._create_card(container, "Configurazione Telegram (Opzionale)")
        self.var_tg_enabled = tk.BooleanVar(value=False)
        cb_tg = ttk.Checkbutton(lf_tg, text="Abilita Telegram", variable=self.var_tg_enabled, style="Card.TCheckbutton", command=self._toggle_telegram_ui)
        cb_tg.pack(anchor="w", padx=5, pady=(0, 10))
        f_tg1 = ttk.Frame(lf_tg, style='Card.TFrame')
        f_tg1.pack(fill="x", pady=(0, 10))
        ttk.Label(f_tg1, text="Bot Token:", width=16, style='Card.TLabel').pack(side="left")
        self.ent_tg_token = ttk.Entry(f_tg1)
        self.ent_tg_token.pack(side="left", fill="x", expand=True, padx=10)
        f_tg2 = ttk.Frame(lf_tg, style='Card.TFrame')
        f_tg2.pack(fill="x", pady=(0, 15))
        ttk.Label(f_tg2, text="Chat ID:", width=16, style='Card.TLabel').pack(side="left")
        self.ent_tg_chatid = ttk.Entry(f_tg2)
        self.ent_tg_chatid.pack(side="left", fill="x", expand=True, padx=10)
        self.btn_tg_save = ttk.Button(f_tg2, text="💾 Salva Config Telegram", style='Action.TButton', command=self._save_telegram_config)
        self.btn_tg_save.pack(side="right")
        ToolTip(self.btn_tg_save, "Salva il token e il chat ID in 'telegram_config.json' per caricarli automaticamente.")
        
        self._toggle_telegram_ui() # Applica stato iniziale

    # --- PAGINA AVANZATE ---
    def _build_page_adv(self, parent):
        container = ttk.Frame(parent, padding=40)
        container.pack(fill="both", expand=True)
        tk.Label(container, text="Opzioni Avanzate", bg=COLOR_BG_MAIN, fg=COLOR_TEXT_HEADER, font=FONT_HEADER_PAGE).pack(anchor="w", pady=(0, 25))
        
        # CARD 1: FORMATO
        lf_spec = self._create_card(container, "Parametri CSV & Excel")
        f_csv = ttk.Frame(lf_spec, style='Card.TFrame')
        f_csv.pack(fill="x", pady=(0, 10))
        ttk.Label(f_csv, text="Delimitatore:", style='Card.TLabel').pack(side="left")
        self.ent_delim = PlaceholderEntry(f_csv, ",", width=5)
        self.ent_delim.pack(side="left", padx=(5, 20))
        ttk.Label(f_csv, text="Col. Input (0=A):", style='Card.TLabel').pack(side="left")
        self.ent_col = PlaceholderEntry(f_csv, "3", width=5)
        self.ent_col.pack(side="left", padx=(5, 20))
        ttk.Label(f_csv, text="Col. Output:", style='Card.TLabel').pack(side="left")
        self.ent_col_out = PlaceholderEntry(f_csv, "3", width=5)
        self.ent_col_out.pack(side="left", padx=(5, 20))
        ttk.Label(f_csv, text="Max Cols:", style='Card.TLabel').pack(side="left")
        self.ent_maxcols = PlaceholderEntry(f_csv, "None", width=5)
        self.ent_maxcols.pack(side="left", padx=5)
        
        # CARD 2: JSON
        lf_json = self._create_card(container, "Parametri JSON")
        f_j1 = ttk.Frame(lf_json, style='Card.TFrame')
        f_j1.pack(fill="x", pady=5)
        ttk.Label(f_j1, text="JSON Keys:", style='Card.TLabel', width=10).pack(side="left")
        self.ent_jkeys = PlaceholderEntry(f_j1, "es. title, description")
        self.ent_jkeys.pack(side="left", fill="x", expand=True, padx=5)
        self.var_jmatch = tk.BooleanVar(value=False)
        ttk.Checkbutton(f_j1, text="Match Full Path", variable=self.var_jmatch, style="Card.TCheckbutton").pack(side="right")

        # CARD 3: CONTESTO
        lf_ctx = self._create_card(container, "Contesto & Prompt")
        f_pr = ttk.Frame(lf_ctx, style='Card.TFrame')
        f_pr.pack(fill="x", pady=5)
        ttk.Label(f_pr, text="Custom Prompt:", style='Card.TLabel', width=15).pack(side="left")
        self.ent_prompt = PlaceholderEntry(f_pr, "Istruzioni aggiuntive per l'AI")
        self.ent_prompt.pack(side="left", fill="x", expand=True, padx=5)
        f_pr2 = ttk.Frame(lf_ctx, style='Card.TFrame')
        f_pr2.pack(fill="x", pady=5)
        ttk.Label(f_pr2, text="Prompt Context:", style='Card.TLabel', width=15).pack(side="left")
        self.ent_pctx = PlaceholderEntry(f_pr2, "Contesto extra fisso")
        self.ent_pctx.pack(side="left", fill="x", expand=True, padx=5)
        f_chk_ctx = ttk.Frame(lf_ctx, style='Card.TFrame')
        f_chk_ctx.pack(fill="x", pady=5)
        self.var_file_ctx = tk.BooleanVar(value=False)
        self.var_full_sample = tk.BooleanVar(value=False)
        self.cb_file_ctx = ttk.Checkbutton(f_chk_ctx, text="Enable File Context (Analisi Preliminare)", variable=self.var_file_ctx, style="Card.TCheckbutton", command=self._update_ui_states)
        self.cb_file_ctx.pack(side="left", padx=(0,20))
        ToolTip(self.cb_file_ctx, "Analizza le prime frasi di ogni file per generare un contesto dinamico per l'AI.")
        self.cb_full_sample = ttk.Checkbutton(f_chk_ctx, text="Full Context Sample (Analisi Completa)", variable=self.var_full_sample, style="Card.TCheckbutton")
        self.cb_full_sample.pack(side="left")
        ToolTip(self.cb_full_sample, "Usa l'intero contenuto del file per generare il contesto. Più accurato ma più lento e costoso.")

        # CARD 4: LOGICA
        lf_perf = self._create_card(container, "Logica & Performance")
        f_chk = ttk.Frame(lf_perf, style='Card.TFrame')
        f_chk.pack(fill="x", pady=(0, 15))
        self.var_cache = tk.BooleanVar(value=True)
        self.var_rotate = tk.BooleanVar(value=True)
        self.var_dry = tk.BooleanVar(value=False)
        self.var_transonly = tk.BooleanVar(value=False)
        self.var_server = tk.BooleanVar(value=False)
        self.var_resume = tk.BooleanVar(value=False)
        self.var_filelog = tk.BooleanVar(value=False)
        self.var_reflect = tk.BooleanVar(value=False)
        self.var_fuzzy = tk.BooleanVar(value=False)
        
        c1 = ttk.Checkbutton(f_chk, text="Salva Cache", variable=self.var_cache, style="Card.TCheckbutton", command=self._update_ui_states)
        c1.grid(row=0, column=0, padx=10, sticky="w")
        ToolTip(c1, "Salva le traduzioni in un file per riutilizzarle in futuro e non sprecare API calls.")
        c2 = ttk.Checkbutton(f_chk, text="Auto-Rotazione API", variable=self.var_rotate, style="Card.TCheckbutton")
        c2.grid(row=0, column=1, padx=10, sticky="w")
        ToolTip(c2, "In caso di errore o limite di quota, passa automaticamente alla API key successiva.")
        c3 = ttk.Checkbutton(f_chk, text="Dry Run (Preventivo)", variable=self.var_dry, style="Card.TCheckbutton")
        c3.grid(row=0, column=2, padx=10, sticky="w")
        ToolTip(c3, "Simula il processo, analizza i file e stima i costi senza tradurre nulla.")
        c4 = ttk.Checkbutton(f_chk, text="Solo Output Tradotto (.txt)", variable=self.var_transonly, style="Card.TCheckbutton")
        c4.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        ToolTip(c4, "Crea un file .txt contenente solo le stringhe tradotte, invece di ricreare il file originale.")
        c5 = ttk.Checkbutton(f_chk, text="Server Mode (No Blacklist)", variable=self.var_server, style="Card.TCheckbutton")
        c5.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        ToolTip(c5, "Impedisce di mettere in blacklist le API key. Utile per server che devono riprovare all'infinito.")
        c7 = ttk.Checkbutton(f_chk, text="Resume (Salta esistenti)", variable=self.var_resume, style="Card.TCheckbutton")
        c7.grid(row=1, column=2, padx=10, pady=5, sticky="w")
        ToolTip(c7, "Se un file di output esiste già, salta le righe/voci già tradotte.")
        c8 = ttk.Checkbutton(f_chk, text="File Log (log.txt)", variable=self.var_filelog, style="Card.TCheckbutton")
        c8.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        ToolTip(c8, "Salva un log dettagliato di tutte le operazioni nel file 'log.txt'.")
        c9 = ttk.Checkbutton(f_chk, text="Agentic Reflection (Alta Qualità)", variable=self.var_reflect, style="Card.TCheckbutton")
        c9.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        ToolTip(c9, "L'AI corregge la propria traduzione. Raddoppia i costi ma aumenta la qualità.")
        
        f_fuzzy = ttk.Frame(f_chk, style='Card.TFrame')
        f_fuzzy.grid(row=2, column=2, padx=10, pady=5, sticky="w")
        c10 = ttk.Checkbutton(f_fuzzy, text="Fuzzy Match", variable=self.var_fuzzy, style="Card.TCheckbutton", command=self._update_ui_states)
        c10.grid(row=2, column=2, padx=10, pady=5, sticky="w")
        ToolTip(c10, "Usa la cache per stringhe simili (richiede 'thefuzz').")
        self.ent_fuzzy_threshold = PlaceholderEntry(f_fuzzy, "90", width=4)
        self.ent_fuzzy_threshold.grid(row=2, column=3, padx=(5,0), sticky="w")
        ToolTip(self.ent_fuzzy_threshold, "Percentuale di similarità (basata su distanza di Levenshtein). Valore 0-100.")
        
        f_num = ttk.Frame(lf_perf, style='Card.TFrame')
        f_num.pack(fill="x", pady=(0, 15))
        ttk.Label(f_num, text="Batch Size:", style='Card.TLabel').pack(side="left")
        self.ent_batch = PlaceholderEntry(f_num, "30", width=5)
        self.ent_batch.pack(side="left", padx=(5, 20))
        ttk.Label(f_num, text="RPM:", style='Card.TLabel').pack(side="left")
        self.ent_rpm = PlaceholderEntry(f_num, "Max", width=5)
        self.ent_rpm.pack(side="left", padx=(5, 15))

        ttk.Label(f_num, text="Max Entries:", style='Card.TLabel').pack(side="left")
        self.ent_maxentr = PlaceholderEntry(f_num, "None", width=8)
        self.ent_maxentr.pack(side="left", padx=(5, 15))
        ToolTip(self.ent_maxentr, "Salta i file che hanno più di N voci da tradurre. Utile per evitare file enormi.")

        ttk.Label(f_num, text="Ctx Win:", style='Card.TLabel').pack(side="left")
        self.ent_ctxwin = PlaceholderEntry(f_num, "0", width=5)
        self.ent_ctxwin.pack(side="left", padx=(5, 15))
        ToolTip(self.ent_ctxwin, "Finestra di contesto dinamica. Invia le ultime N traduzioni all'AI per migliorare la coerenza. (Default: 0)")


        f_wrap = ttk.Frame(lf_perf, style='Card.TFrame')
        f_wrap.pack(fill="x", pady=(0, 15))
        ttk.Label(f_wrap, text="Wrap At:", style='Card.TLabel').pack(side="left")
        self.ent_wrap = PlaceholderEntry(f_wrap, "None", width=5)
        self.ent_wrap.pack(side="left", padx=(5, 20))
        ttk.Label(f_wrap, text="Newline Char:", style='Card.TLabel').pack(side="left")
        self.ent_newline = PlaceholderEntry(f_wrap, "\\n", width=5)
        self.ent_newline.pack(side="left", padx=5)

        f_glo = ttk.Frame(lf_perf, style='Card.TFrame')
        f_glo.pack(fill="x", pady=(0, 10))
        ttk.Label(f_glo, text="Glossario CSV:", style='Card.TLabel', width=15).pack(side="left")
        self.ent_gloss = ttk.Entry(f_glo)
        self.ent_gloss.pack(side="left", fill="x", expand=True, padx=5)
        if os.path.exists("glossary.csv"): self.ent_gloss.insert(0, "glossary.csv")
        btn_browse_gloss = ttk.Button(f_glo, text="...", width=4, command=lambda: self._browse_file(self.ent_gloss))
        btn_browse_gloss.pack(side="left")
        ToolTip(btn_browse_gloss, "Sfoglia file")
        
        f_cache = ttk.Frame(lf_perf, style='Card.TFrame')
        f_cache.pack(fill="x")
        ttk.Label(f_cache, text="File Cache JSON:", style='Card.TLabel', width=15).pack(side="left")
        self.ent_cache_file = ttk.Entry(f_cache)
        self.ent_cache_file.pack(side="left", fill="x", expand=True, padx=5)
        ToolTip(self.ent_cache_file, "Percorso del file di cache. Default: alumen_cache.json")
        if os.path.exists(AlumenCore.DEFAULT_CACHE_FILE): self.ent_cache_file.insert(0, AlumenCore.DEFAULT_CACHE_FILE)
        self.btn_cache_browse = ttk.Button(f_cache, text="...", width=4, command=lambda: self._browse_file(self.ent_cache_file))
        self.btn_cache_browse.pack(side="left")
        ToolTip(self.btn_cache_browse, "Sfoglia file")

    # --- PAGE TOOLS ---
    def _build_page_tools(self, parent):
        container = ttk.Frame(parent, padding=40)
        container.pack(fill="both", expand=True)
        tk.Label(container, text="Strumenti di Utilità", bg=COLOR_BG_MAIN, fg=COLOR_TEXT_HEADER, font=FONT_HEADER_PAGE).pack(anchor="w", pady=(0, 25))

        # TOOL 1: EXTRACTOR
        lf_ex = self._create_card(container, "Estrattore Cache (Importa Traduzioni)")
        f_ex1 = ttk.Frame(lf_ex, style='Card.TFrame')
        f_ex1.pack(fill="x", pady=5)
        ttk.Label(f_ex1, text="Cartella Originali:", style='Card.TLabel', width=15).pack(side="left")
        self.ent_ex_src = ttk.Entry(f_ex1)
        self.ent_ex_src.pack(side="left", fill="x", expand=True, padx=5)
        btn_ex_browse_src = ttk.Button(f_ex1, text="📂", width=4, command=lambda: self._browse_folder(self.ent_ex_src))
        btn_ex_browse_src.pack(side="right")
        ToolTip(btn_ex_browse_src, "Sfoglia cartella")
        f_ex2 = ttk.Frame(lf_ex, style='Card.TFrame')
        f_ex2.pack(fill="x", pady=5)
        ttk.Label(f_ex2, text="Cartella Tradotti:", style='Card.TLabel', width=15).pack(side="left")
        self.ent_ex_tgt = ttk.Entry(f_ex2)
        self.ent_ex_tgt.pack(side="left", fill="x", expand=True, padx=5)
        btn_ex_browse_tgt = ttk.Button(f_ex2, text="📂", width=4, command=lambda: self._browse_folder(self.ent_ex_tgt))
        btn_ex_browse_tgt.pack(side="right")
        ToolTip(btn_ex_browse_tgt, "Sfoglia cartella")
        
        f_ex_opts = ttk.Frame(lf_ex, style='Card.TFrame')
        f_ex_opts.pack(fill="x", pady=5)
        ttk.Label(f_ex_opts, text="Formato:", style='Card.TLabel', width=16).pack(side="left")
        self.cmb_ex_fmt = ttk.Combobox(f_ex_opts, values=["csv", "json", "po"], width=8, state="readonly")
        self.cmb_ex_fmt.current(0)
        self.cmb_ex_fmt.bind("<<ComboboxSelected>>", self._update_extractor_ui)
        self.cmb_ex_fmt.pack(side="left", padx=10)
        
        # --- Contenitore opzioni specifiche formato ---
        self.f_ex_csv_opts = ttk.Frame(lf_ex, style='Card.TFrame')
        self.f_ex_csv_opts.pack(fill="x", pady=5)
        ttk.Label(self.f_ex_csv_opts, text="Col. Originale:", style='Card.TLabel', width=16).pack(side="left")
        self.ent_ex_col_src = PlaceholderEntry(self.f_ex_csv_opts, "3", width=5)
        self.ent_ex_col_src.pack(side="left", padx=(10, 20))
        ttk.Label(self.f_ex_csv_opts, text="Col. Tradotta:", style='Card.TLabel').pack(side="left")
        self.ent_ex_col_tgt = PlaceholderEntry(self.f_ex_csv_opts, "3", width=5)
        self.ent_ex_col_tgt.pack(side="left", padx=10)

        self.f_ex_json_opts = ttk.Frame(lf_ex, style='Card.TFrame')
        # f_ex_json_opts non viene packato subito
        ttk.Label(self.f_ex_json_opts, text="JSON Keys:", style='Card.TLabel', width=16).pack(side="left")
        self.ent_ex_json_keys = PlaceholderEntry(self.f_ex_json_opts, "es. title, description")
        self.ent_ex_json_keys.pack(side="left", fill="x", expand=True, padx=10)

        f_ex3 = ttk.Frame(lf_ex, style='Card.TFrame')
        f_ex3.pack(fill="x", pady=10)
        ttk.Button(f_ex3, text="🛠️ Estrai Cache", style='Tool.TButton', command=self._run_extractor_tool).pack(side="right")
        self._update_extractor_ui() # Stato iniziale

        # TOOL 2: SCANNER
        lf_scan = self._create_card(container, "Auto-Glossary Scanner (AI)")
        ttk.Label(lf_scan, text="Scansiona i file per trovare nomi propri.", style='Card.TLabel').pack(anchor="w", pady=(0,10))
        f_scan_opts = ttk.Frame(lf_scan, style='Card.TFrame')
        f_scan_opts.pack(fill="x")
        ttk.Label(f_scan_opts, text="Formato File:", style='Card.TLabel', width=16).pack(side="left")
        self.cmb_scan_fmt = ttk.Combobox(f_scan_opts, values=["csv", "json", "po", "srt"], width=8, state="readonly")
        self.cmb_scan_fmt.current(0)
        self.cmb_scan_fmt.pack(side="left", padx=10)
        self.btn_scan = ttk.Button(f_scan_opts, text="🕵️ Scansiona", style='Tool.TButton', command=self._run_scanner_tool)
        self.btn_scan.pack(side="left", padx=20)

    # --- PAGE LOG ---
    def _build_page_log(self, parent):
        container = ttk.Frame(parent, padding=40)
        container.pack(fill="both", expand=True)
        f_head = tk.Frame(container, bg=COLOR_BG_MAIN)
        f_head.pack(fill="x", pady=(0, 20))
        tk.Label(f_head, text="Esecuzione Processo", bg=COLOR_BG_MAIN, fg=COLOR_TEXT_HEADER, font=FONT_HEADER_PAGE).pack(side="left")
        
        self.btn_show_stats = ttk.Button(f_head, text="📊 MOSTRA STATS", command=self._show_stats_window)
        self.btn_show_stats.pack(side="right", padx=(0, 10))
        self.btn_save_cache = ttk.Button(f_head, text="💾 Salva Cache", command=self._force_save_cache)
        ToolTip(self.btn_save_cache, "Forza il salvataggio immediato della cache su disco.")        
        self.btn_save_cache.pack(side="right")
        f_info = tk.Frame(container, bg=COLOR_BG_CARD, padx=20, pady=10)
        f_info.pack(fill="x", pady=(0, 15))
        self.lbl_stats_files = tk.Label(f_info, text="File: 0", bg=COLOR_BG_CARD, font=FONT_STATS, fg=COLOR_BTN_ACTION)
        self.lbl_stats_files.pack(side="left", padx=20)
        self.lbl_stats_entries = tk.Label(f_info, text="Righe: 0", bg=COLOR_BG_CARD, font=FONT_STATS, fg=COLOR_BTN_ACTION)
        self.lbl_stats_entries.pack(side="left", padx=20)
        self.lbl_stats_cache = tk.Label(f_info, text="Cache: 0", bg=COLOR_BG_CARD, font=FONT_STATS, fg="#f39c12")
        self.lbl_stats_cache.pack(side="left", padx=20)
        frame_log = tk.Frame(container, bg="#bdc3c7", bd=1)
        frame_log.pack(fill="both", expand=True)
        self.txt_log = scrolledtext.ScrolledText(frame_log, state='disabled', font=("Consolas", 10), 
                                                 bg="#1e272e", fg="#ecf0f1", relief="flat", padx=10, pady=10)
        self.txt_log.pack(fill="both", expand=True)
        f_act = tk.Frame(container, bg=COLOR_BG_MAIN, pady=20)
        f_act.pack(fill="x")
        self.btn_run = ttk.Button(f_act, text="▶  AVVIA", style='Action.TButton', command=self._start_process)
        self.btn_run.pack(side="left", fill="x", expand=True, padx=5)
        self.btn_pause = ttk.Button(f_act, text="⏸  PAUSA", style='Warn.TButton', command=self._toggle_pause, state='disabled')
        self.btn_pause.pack(side="left", fill="x", expand=True, padx=5)
        self.btn_skip_file = ttk.Button(f_act, text="⏭  SALTA FILE", command=self._skip_file, state='disabled')
        self.btn_skip_file.pack(side="left", fill="x", expand=True, padx=5)
        self.btn_skip_api = ttk.Button(f_act, text="🔄  SALTA API", command=self._skip_api, state='disabled')
        self.btn_skip_api.pack(side="left", fill="x", expand=True, padx=5)
        self.btn_stop = ttk.Button(f_act, text="⏹  STOP", style='Danger.TButton', command=self._stop_process)
        self.btn_stop.pack(side="left", fill="x", expand=True, padx=5)

    # --- LOGIC HANDLERS ---
    def _check_update_thread(self):
        def _w():
            new_ver = AlumenCore.check_for_updates()
            if new_ver: messagebox.showinfo("Aggiornamento", f"Versione {new_ver} disponibile su GitHub!")
        threading.Thread(target=_w, daemon=True).start()

    def _update_ui_states(self, event=None):
        state_cache = 'normal' if self.var_cache.get() else 'disabled'
        self.ent_cache_file.config(state=state_cache)
        self.btn_cache_browse.config(state=state_cache)
        self.btn_save_cache.config(state=state_cache)
        
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
        
        state_json = 'normal' if fmt == 'json' else 'disabled'
        if isinstance(self.ent_jkeys, ttk.Entry): self.ent_jkeys.config(state=state_json)

        state_fuzzy = 'normal' if self.var_fuzzy.get() else 'disabled'
        if isinstance(self.ent_fuzzy_threshold, PlaceholderEntry):
            self.ent_fuzzy_threshold.config(state=state_fuzzy)

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
                    self.ent_tg_token.config(state='normal') # Forza enable per scrivere
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
            messagebox.showwarning("Attenzione", "Inserisci Token e Chat ID")
            return
        try:
            with open("telegram_config.json", "w") as f:
                json.dump({"bot_token": t, "chat_id": c}, f, indent=4)
            messagebox.showinfo("Fatto", "Salvataggio OK")
        except Exception as e: messagebox.showerror("Errore", str(e))

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
        def _w():
            ms = AlumenCore.fetch_available_models(key)
            def _u():
                if ms and not str(ms[0]).startswith("Errore"):
                    curr = self.cmb_model.get()
                    self.cmb_model['values'] = tuple(ms)
                    if curr not in ms: self.cmb_model.current(0)
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
            self.txt_log.insert(tk.END, msg + "\n")
            self.txt_log.see(tk.END)
            self.txt_log.configure(state='disabled')
        self.root.after(100, self._poll_log_queue)
    def _update_stats(self):
        files = AlumenCore.total_files_translated
        entries = AlumenCore.total_entries_translated
        cache_size = len(AlumenCore.translation_cache)
        self.lbl_stats_files.config(text=f"File: {files}")
        self.lbl_stats_entries.config(text=f"Righe: {entries}")
        self.lbl_stats_cache.config(text=f"Cache: {cache_size}")
        self.root.after(1000, self._update_stats)
    def _force_save_cache(self):
        if self.current_args and self.var_cache.get():
            AlumenCore.check_and_save_cache(self.current_args, force=True)
        else:
            class MockArgs: persistent_cache = True; cache_file = None
            AlumenCore.check_and_save_cache(MockArgs(), force=True)
    
    def _toggle_pause(self):
        if not self.is_running: return
        if self.pause_event.is_set():
            self.pause_event.clear() # Pause
            self.btn_pause.config(text="▶ RIPRENDI", style='Action.TButton')
        else:
            self.pause_event.set() # Resume
            self.btn_pause.config(text="⏸ PAUSA", style='Warn.TButton')
    def _skip_file(self):
        if not self.is_running: return
        self.skip_event.set()
    def _skip_api(self):
        if not self.is_running: return
        self.skip_api_event.set()
    def _stop_process(self):
        if self.stop_event.is_set(): return
        self.stop_event.set()
        self.log_queue.put("🛑 Richiesta di Stop...")
        self.is_running = False
        self.btn_pause.config(state='disabled')
        self.btn_skip_file.config(state='disabled')
        self.btn_skip_api.config(state='disabled')

    def _update_extractor_ui(self, event=None):
        fmt = self.cmb_ex_fmt.get()
        self.f_ex_csv_opts.pack_forget()
        self.f_ex_json_opts.pack_forget()
        if fmt == 'csv': self.f_ex_csv_opts.pack(fill="x", pady=5)
        elif fmt == 'json': self.f_ex_json_opts.pack(fill="x", pady=5)

    def _run_extractor_tool(self):
        s = self.ent_ex_src.get()
        t = self.ent_ex_tgt.get()
        if not s or not t: messagebox.showerror("Errore", "Seleziona cartelle!"); return
        
        fmt = self.cmb_ex_fmt.get()
        try: col_s = int(self.ent_ex_col_src.get_valid_value())
        except: col_s = 3
        try: col_t = int(self.ent_ex_col_tgt.get_valid_value())
        except: col_t = 3
        json_keys = self.ent_ex_json_keys.get_valid_value()

        self._show_frame("log")
        threading.Thread(target=lambda: AlumenCore.run_cache_extractor(s, t, fmt, col_s, col_t, "utf-8", json_keys=json_keys), daemon=True).start()
    def _run_scanner_tool(self):
        inp = self.ent_input.get()
        api = self.ent_api.get()
        if not api and not self.api_file_path: messagebox.showerror("Errore", "API Key necessaria"); return
        fmt = self.cmb_scan_fmt.get()
        def _w():
            t = AlumenCore.run_term_scanner(inp, fmt, "utf-8")
            self.log_queue.put(f"Termini trovati (formato {fmt}):\n{t}")
        self._show_frame("log")
        threading.Thread(target=_w, daemon=True).start()

    def _start_process(self):
        class Args: pass
        a = Args()
        a.api_file = self.api_file_path
        a.api = None if a.api_file else self.ent_api.get()
        if not a.api and not a.api_file: messagebox.showerror("Errore", "Manca API Key!"); return
        a.model_name = self.cmb_model.get()
        a.input = self.ent_input.get()
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
        a.resume = self.var_resume.get()
        a.enable_file_log = self.var_filelog.get()
        a.enable_file_context = self.var_file_ctx.get()
        a.full_context_sample = self.var_full_sample.get()
        a.reflect = self.var_reflect.get()
        a.fuzzy_match = self.var_fuzzy.get()
        try: a.fuzzy_threshold = int(self.ent_fuzzy_threshold.get_valid_value())
        except: a.fuzzy_threshold = 90
        a.interactive = False # La GUI non è interattiva in senso CLI


        if a.file_type == "json" and not a.json_keys and not a.dry_run:
            messagebox.showerror("Errore", "JSON richiede chiavi!")
            return

        self.current_args = a
        self.stop_event.clear()
        self.pause_event.set() 
        self.skip_api_event.clear()
        self.skip_event.clear()
        self.is_running = True
        self.btn_pause.config(state='normal', text="⏸ PAUSA", style='Warn.TButton')
        self.btn_skip_file.config(state='normal')
        self.btn_skip_api.config(state='normal')
        self.txt_log.configure(state='normal')
        self.txt_log.delete(1.0, tk.END)
        self.txt_log.configure(state='disabled')
        self._show_frame("log")
        t = threading.Thread(target=AlumenCore.run_core_process, args=(a, self.log_queue, self.stop_event, self.pause_event, self.skip_event, self.skip_api_event), daemon=True)
        t.start()

    def _collect_args(self):
        # Helper per preview (copia della logica start_process)
        class Args: pass
        a = Args()
        a.game_name = self.ent_gamename.get_valid_value() if self.ent_gamename.get_valid_value() else "un videogioco generico"
        a.source_lang = self.ent_src.get()
        a.target_lang = self.ent_tgt.get()
        a.custom_prompt = self.ent_prompt.get_valid_value()
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
        top.title("Prompt Preview")
        top.geometry("800x650")
        top.configure(bg="#1e272e")
        st = scrolledtext.ScrolledText(top, bg="#1e272e", fg="#2ecc71", font=("Consolas", 11), padx=15, pady=15)
        st.pack(fill="both", expand=True)
        st.insert(tk.END, preview_text)
        st.configure(state='disabled')

    def _show_stats_window(self):
        stats_text = AlumenCore._get_full_stats_text(is_telegram=False, for_gui=True)
        top = tk.Toplevel(self.root)
        top.title("Statistiche Dettagliate")
        top.geometry("700x500")
        top.configure(bg="#1e272e")
        st = scrolledtext.ScrolledText(top, bg="#1e272e", fg="#fafafa", font=("Consolas", 10), padx=15, pady=15, relief="flat")
        st.pack(fill="both", expand=True)
        st.insert(tk.END, stats_text)
        st.configure(state='disabled')


if __name__ == "__main__":
    root = tk.Tk()
    app = AlumenGUI(root)
    root.mainloop()