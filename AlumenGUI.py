# --- START OF FILE AlumenGUI.py ---
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import queue
import os
import AlumenCore

# --- Classe ToolTip ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        "Display text in tooltip window"
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                       background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                       font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

# --- Main GUI ---
class AlumenGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Alumen v2.2 - Smart Translator")
        self.root.geometry("850x750")
        
        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        style = ttk.Style()
        style.theme_use('clam')
        
        # Header
        header = tk.Label(root, text="Alumen AI Translator", font=("Segoe UI", 18, "bold"), bg="#e6f7ff", fg="#005a9e")
        header.pack(fill="x")
        ToolTip(header, "Suite di traduzione basata su Google Gemini 2.0")
        
        # Tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.tab_main = ttk.Frame(self.notebook)
        self.tab_adv = ttk.Frame(self.notebook)
        self.tab_log = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_main, text="⚙️ Configurazione")
        self.notebook.add(self.tab_adv, text="🧠 Avanzate")
        self.notebook.add(self.tab_log, text="📜 Esecuzione")
        
        self._build_main_tab()
        self._build_adv_tab()
        self._build_log_tab()
        
        # Auto-fetch trigger: Se la key esiste già, aggiorna i modelli all'avvio
        if self.ent_api.get():
            self.root.after(500, self._refresh_models_auto)
            
        self.root.after(100, self._poll_log_queue)

    def _build_main_tab(self):
        f = self.tab_main
        
        # --- API ---
        lf_api = ttk.LabelFrame(f, text="Connessione Google Gemini", padding=10)
        lf_api.pack(fill="x", pady=10, padx=10)
        
        lbl_key = ttk.Label(lf_api, text="API Keys (separate da virgola):")
        lbl_key.pack(anchor="w")
        self.ent_api = ttk.Entry(lf_api, width=70)
        self.ent_api.pack(fill="x", pady=5)
        ToolTip(self.ent_api, "Incolla qui le tue chiavi API di Google AI Studio.\nSe ne metti più di una, Alumen le userà a rotazione per evitare blocchi.")
        
        # Bind event: quando si lascia il campo API key, aggiorna la lista modelli
        self.ent_api.bind("<FocusOut>", lambda e: self._refresh_models_auto())
        
        if os.path.exists("api_key.txt"):
            with open("api_key.txt", "r") as kf: self.ent_api.insert(0, kf.read().strip())

        # Model Selector
        fr_mod = ttk.Frame(lf_api)
        fr_mod.pack(fill="x", pady=5)
        lbl_mod = ttk.Label(fr_mod, text="Modello AI:")
        lbl_mod.pack(side="left")
        
        self.cmb_model = ttk.Combobox(fr_mod, width=50) # Più largo per le descrizioni
        self.cmb_model['values'] = ("gemini-2.0-flash [Default - Veloce]",)
        self.cmb_model.current(0)
        self.cmb_model.pack(side="left", padx=5)
        ToolTip(self.cmb_model, "Scegli il 'cervello' da usare.\nLa lista si aggiorna automaticamente in base alla tua API Key.")

        # --- FILES ---
        lf_file = ttk.LabelFrame(f, text="File e Cartelle", padding=10)
        lf_file.pack(fill="x", pady=10, padx=10)
        
        # Input
        sub1 = ttk.Frame(lf_file)
        sub1.pack(fill="x", pady=5)
        lbl_in = ttk.Label(sub1, text="Cartella Input:")
        lbl_in.pack(side="left")
        self.ent_input = ttk.Entry(sub1)
        self.ent_input.insert(0, "input")
        self.ent_input.pack(side="left", fill="x", expand=True, padx=5)
        ToolTip(self.ent_input, "La cartella dove si trovano i file da tradurre.")
        
        btn_br = ttk.Button(sub1, text="Sfoglia...", command=self._browse_folder)
        btn_br.pack(side="left")
        ToolTip(btn_br, "Seleziona la cartella dal computer.")
        
        # Format & Langs
        sub2 = ttk.Frame(lf_file)
        sub2.pack(fill="x", pady=5)
        
        lbl_fmt = ttk.Label(sub2, text="Formato:")
        lbl_fmt.pack(side="left")
        self.cmb_fmt = ttk.Combobox(sub2, values=["csv", "json", "po", "xlsx"], state="readonly", width=8)
        self.cmb_fmt.current(0)
        self.cmb_fmt.pack(side="left", padx=5)
        ToolTip(self.cmb_fmt, "Il tipo di file che vuoi tradurre (CSV, Excel, JSON, etc).")
        
        lbl_src = ttk.Label(sub2, text="Da Lingua:")
        lbl_src.pack(side="left", padx=10)
        self.ent_src = ttk.Entry(sub2, width=12)
        self.ent_src.insert(0, "inglese")
        self.ent_src.pack(side="left")
        ToolTip(self.ent_src, "La lingua originale dei file.")
        
        lbl_tgt = ttk.Label(sub2, text="A Lingua:")
        lbl_tgt.pack(side="left", padx=5)
        self.ent_tgt = ttk.Entry(sub2, width=12)
        self.ent_tgt.insert(0, "italiano")
        self.ent_tgt.pack(side="left")
        ToolTip(self.ent_tgt, "La lingua in cui vuoi tradurre.")

    def _build_adv_tab(self):
        f = self.tab_adv
        
        # CSV Options
        lf_csv = ttk.LabelFrame(f, text="Configurazione CSV", padding=10)
        lf_csv.pack(fill="x", pady=5, padx=10)
        
        fr_c = ttk.Frame(lf_csv)
        fr_c.pack(fill="x")
        
        lbl_del = ttk.Label(fr_c, text="Delimitatore:")
        lbl_del.pack(side="left")
        self.ent_delim = ttk.Entry(fr_c, width=5)
        self.ent_delim.insert(0, ",")
        self.ent_delim.pack(side="left", padx=5)
        ToolTip(self.ent_delim, "Il simbolo che separa le colonne (virgola per CSV standard, punto e virgola, etc).")
        
        lbl_col = ttk.Label(fr_c, text="Colonna Testo (0=A, 1=B...):")
        lbl_col.pack(side="left", padx=10)
        self.ent_col = ttk.Entry(fr_c, width=5)
        self.ent_col.insert(0, "3")
        self.ent_col.pack(side="left")
        ToolTip(self.ent_col, "Il numero della colonna che contiene il testo da tradurre (partendo da 0).")

        # JSON Options
        lf_json = ttk.LabelFrame(f, text="Configurazione JSON", padding=10)
        lf_json.pack(fill="x", pady=5, padx=10)
        
        lbl_jk = ttk.Label(lf_json, text="Chiavi da tradurre (es: name,description):")
        lbl_jk.pack(anchor="w")
        self.ent_jkeys = ttk.Entry(lf_json)
        self.ent_jkeys.pack(fill="x")
        ToolTip(self.ent_jkeys, "IMPORTANTE: Scrivi qui i nomi dei campi JSON che contengono il testo.\nEsempio: se il file è {'dialogo': 'Ciao'}, scrivi 'dialogo'.")
        
        # Quality & Perf
        lf_perf = ttk.LabelFrame(f, text="Qualità & Performance", padding=10)
        lf_perf.pack(fill="x", pady=5, padx=10)
        
        # Glossary
        fr_glo = ttk.Frame(lf_perf)
        fr_glo.pack(fill="x", pady=2)
        lbl_glo = ttk.Label(fr_glo, text="Glossario CSV:")
        lbl_glo.pack(side="left")
        self.ent_gloss = ttk.Entry(fr_glo)
        self.ent_gloss.pack(side="left", fill="x", expand=True, padx=5)
        ToolTip(self.ent_gloss, "Opzionale: Un file CSV con termini fissi da non sbagliare (es. 'Potion,Pozione').")
        ttk.Button(fr_glo, text="...", width=3, command=self._browse_file).pack(side="left")
        
        # Batch
        fr_bat = ttk.Frame(lf_perf)
        fr_bat.pack(fill="x", pady=5)
        lbl_bat = ttk.Label(fr_bat, text="Batch Size:")
        lbl_bat.pack(side="left")
        self.ent_batch = ttk.Entry(fr_bat, width=5)
        self.ent_batch.insert(0, "30")
        self.ent_batch.pack(side="left", padx=5)
        ToolTip(self.ent_batch, "Quante frasi inviare insieme a Google.\n30-50 è l'ideale per velocità. 1 per massima precisione.")
        
        # Cache Checkbox
        self.var_cache = tk.BooleanVar(value=True)
        chk_cache = ttk.Checkbutton(fr_bat, text="Usa Cache Persistente", variable=self.var_cache)
        chk_cache.pack(side="left", padx=20)
        ToolTip(chk_cache, "Se attivo, salva le traduzioni su disco.\nSe riavvii il programma, non pagherai di nuovo per le frasi già fatte.")

    def _build_log_tab(self):
        f = self.tab_log
        self.txt_log = scrolledtext.ScrolledText(f, state='disabled', font=("Consolas", 9), bg="#f4f4f4")
        self.txt_log.pack(fill="both", expand=True, padx=5, pady=5)
        
        fr_btn = ttk.Frame(f)
        fr_btn.pack(fill="x", pady=10)
        
        btn_run = ttk.Button(fr_btn, text="▶ AVVIA TRADUZIONE", command=self._start_process)
        btn_run.pack(side="left", fill="x", expand=True, padx=5)
        ToolTip(btn_run, "Clicca per iniziare il processo di traduzione.")
        
        btn_stop = ttk.Button(fr_btn, text="⏹ STOP", command=self._stop_process)
        btn_stop.pack(side="right", fill="x", expand=True, padx=5)
        ToolTip(btn_stop, "Ferma il processo in sicurezza (salva prima di uscire).")

    def _browse_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.ent_input.delete(0, tk.END)
            self.ent_input.insert(0, d)

    def _browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if f:
            self.ent_gloss.delete(0, tk.END)
            self.ent_gloss.insert(0, f)

    def _refresh_models_auto(self):
        """Scarica silenziosamente la lista modelli."""
        api_key_full = self.ent_api.get().strip()
        if not api_key_full: return # Non fare nulla se vuoto
        
        # Prendi solo la prima chiave
        api_key = api_key_full.split(',')[0].strip()
        
        def _worker():
            models = AlumenCore.fetch_available_models(api_key)
            # Aggiorna GUI nel thread principale
            def _update_ui():
                if models and not str(models[0]).startswith("Errore"):
                    current = self.cmb_model.get()
                    self.cmb_model['values'] = tuple(models)
                    # Se il modello corrente non è nella lista, seleziona il primo
                    if current not in models:
                        self.cmb_model.current(0)
            self.root.after(0, _update_ui)

        threading.Thread(target=_worker, daemon=True).start()

    def _poll_log_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.txt_log.configure(state='normal')
            self.txt_log.insert(tk.END, msg + "\n")
            self.txt_log.see(tk.END)
            self.txt_log.configure(state='disabled')
        self.root.after(100, self._poll_log_queue)

    def _stop_process(self):
        if self.stop_event.is_set(): return
        self.stop_event.set()
        self.log_queue.put("🛑 Richiesta di Stop inviata...")

    def _start_process(self):
        class Args: pass
        a = Args()
        
        a.api = self.ent_api.get()
        a.model_name = self.cmb_model.get() 
        a.input = self.ent_input.get()
        a.file_type = self.cmb_fmt.get()
        a.source_lang = self.ent_src.get()
        a.target_lang = self.ent_tgt.get()
        
        a.delimiter = self.ent_delim.get()
        try: a.translate_col = int(self.ent_col.get())
        except: a.translate_col = 3
        a.output_col = a.translate_col
        
        a.json_keys = self.ent_jkeys.get()
        a.match_full_json_path = False
        
        a.glossary = self.ent_gloss.get()
        try: a.batch_size = int(self.ent_batch.get())
        except: a.batch_size = 30
        a.persistent_cache = self.var_cache.get()
        
        a.rotate_on_limit_or_error = True
        a.rpm = None
        
        if not a.api:
            messagebox.showerror("Errore", "Inserisci la API Key!")
            return
        if a.file_type == "json" and not a.json_keys:
            messagebox.showerror("Errore", "Per i file JSON devi specificare le chiavi!")
            return

        self.stop_event.clear()
        self.txt_log.configure(state='normal')
        self.txt_log.delete(1.0, tk.END)
        self.txt_log.configure(state='disabled')
        self.notebook.select(self.tab_log)
        
        t = threading.Thread(target=AlumenCore.run_core_process, args=(a, self.log_queue, self.stop_event), daemon=True)
        t.start()

if __name__ == "__main__":
    root = tk.Tk()
    app = AlumenGUI(root)
    root.mainloop()        self.ent_delim = ttk.Entry(fr_c1, width=5)
        self.ent_delim.insert(0, ",")
        self.ent_delim.pack(side="left", padx=10)
        
        ttk.Label(fr_c1, text="Colonna Testo (0=A, 1=B...):").pack(side="left")
        self.ent_col = ttk.Entry(fr_c1, width=5)
        self.ent_col.insert(0, "3")
        self.ent_col.pack(side="left")

        # JSON Specific
        lf_json = ttk.LabelFrame(f, text="Opzioni JSON", padding=10)
        lf_json.pack(fill="x", pady=10, padx=10)
        ttk.Label(lf_json, text="Chiavi da tradurre (es: name,description):").pack(anchor="w")
        self.ent_jkeys = ttk.Entry(lf_json)
        self.ent_jkeys.pack(fill="x")
        
        # Glossario & Batch
        lf_gen = ttk.LabelFrame(f, text="Glossario & Performance", padding=10)
        lf_gen.pack(fill="x", pady=10, padx=10)
        
        fr_g = ttk.Frame(lf_gen)
        fr_g.pack(fill="x", pady=5)
        ttk.Label(fr_g, text="Glossario CSV:").pack(side="left")
        self.ent_gloss = ttk.Entry(fr_g)
        self.ent_gloss.pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(fr_g, text="...", width=3, command=self._browse_file).pack(side="left")
        
        fr_b = ttk.Frame(lf_gen)
        fr_b.pack(fill="x", pady=5)
        ttk.Label(fr_b, text="Batch Size:").pack(side="left")
        self.ent_batch = ttk.Entry(fr_b, width=5)
        self.ent_batch.insert(0, "30")
        self.ent_batch.pack(side="left", padx=10)
        
        self.var_cache = tk.BooleanVar(value=True)
        ttk.Checkbutton(fr_b, text="Usa Cache Persistente", variable=self.var_cache).pack(side="left", padx=10)

    def _build_log_tab(self):
        f = self.tab_log
        self.txt_log = scrolledtext.ScrolledText(f, state='disabled', font=("Consolas", 9))
        self.txt_log.pack(fill="both", expand=True, padx=5, pady=5)
        
        fr_btn = ttk.Frame(f)
        fr_btn.pack(fill="x", pady=10)
        
        btn_run = ttk.Button(fr_btn, text="▶ AVVIA TRADUZIONE", command=self._start_process)
        btn_run.pack(side="left", fill="x", expand=True, padx=5)
        
        btn_stop = ttk.Button(fr_btn, text="⏹ STOP", command=self._stop_process)
        btn_stop.pack(side="right", fill="x", expand=True, padx=5)

    # --- ACTIONS ---
    def _browse_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.ent_input.delete(0, tk.END)
            self.ent_input.insert(0, d)

    def _browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if f:
            self.ent_gloss.delete(0, tk.END)
            self.ent_gloss.insert(0, f)

    def _poll_log_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.txt_log.configure(state='normal')
            self.txt_log.insert(tk.END, msg + "\n")
            self.txt_log.see(tk.END)
            self.txt_log.configure(state='disabled')
        self.root.after(100, self._poll_log_queue)

    def _stop_process(self):
        if self.stop_event.is_set(): return
        self.stop_event.set()
        self.log_queue.put("🛑 Richiesta di Stop inviata...")

    def _start_process(self):
        # Creiamo un oggetto "args" finto per passarlo al Core
        class Args: pass
        a = Args()
        
        # Mapping Input GUI -> Args Core
        a.api = self.ent_api.get()
        a.input = self.ent_input.get()
        a.file_type = self.cmb_fmt.get()
        a.source_lang = self.ent_src.get()
        a.target_lang = self.ent_tgt.get()
        
        # CSV
        a.delimiter = self.ent_delim.get()
        try: a.translate_col = int(self.ent_col.get())
        except: a.translate_col = 3
        a.output_col = a.translate_col
        
        # JSON
        a.json_keys = self.ent_jkeys.get()
        a.match_full_json_path = False
        
        # General
        a.glossary = self.ent_gloss.get()
        try: a.batch_size = int(self.ent_batch.get())
        except: a.batch_size = 30
        a.persistent_cache = self.var_cache.get()
        
        # Defaults fissi per v2.0
        a.model_name = "gemini-2.0-flash"
        a.rotate_on_limit_or_error = True
        a.rpm = None
        
        # Validazione base
        if not a.api:
            messagebox.showerror("Errore", "Inserisci la API Key!")
            return
        if a.file_type == "json" and not a.json_keys:
            messagebox.showerror("Errore", "Per i file JSON devi specificare le chiavi!")
            return

        # Reset UI
        self.stop_event.clear()
        self.txt_log.configure(state='normal')
        self.txt_log.delete(1.0, tk.END)
        self.txt_log.configure(state='disabled')
        self.notebook.select(self.tab_log)
        
        # Avvia Thread
        t = threading.Thread(target=AlumenCore.run_core_process, args=(a, self.log_queue, self.stop_event), daemon=True)
        t.start()

if __name__ == "__main__":
    root = tk.Tk()
    app = AlumenGUI(root)
    root.mainloop()
