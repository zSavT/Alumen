# --- START OF FILE AlumenGUI.py ---
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import queue
import os
import AlumenCore  # Importa il cervello

class AlumenGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Alumen v2.0 - GUI Edition")
        self.root.geometry("800x650")
        
        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        # --- STILE ---
        style = ttk.Style()
        style.theme_use('clam')
        
        # --- TITOLO ---
        lbl_title = tk.Label(root, text="Alumen 2.0 Translator", font=("Helvetica", 16, "bold"), bg="#f0f0f0", fg="#333")
        lbl_title.pack(fill="x", pady=10)
        
        # --- NOTEBOOK (TABS) ---
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
        
        # Loop per leggere la coda dei log dal Core
        self.root.after(100, self._poll_log_queue)

    def _build_main_tab(self):
        f = self.tab_main
        
        # API KEY
        lf_api = ttk.LabelFrame(f, text="API & Google Gemini", padding=10)
        lf_api.pack(fill="x", pady=10, padx=10)
        
        ttk.Label(lf_api, text="API Keys (separate da virgola):").pack(anchor="w")
        self.ent_api = ttk.Entry(lf_api, width=70)
        self.ent_api.pack(fill="x", pady=5)
        # Carica da file se esiste
        if os.path.exists("api_key.txt"):
            with open("api_key.txt", "r") as kf: self.ent_api.insert(0, kf.read().strip())

        # FILES
        lf_file = ttk.LabelFrame(f, text="File & Percorsi", padding=10)
        lf_file.pack(fill="x", pady=10, padx=10)
        
        # Input Folder
        sub1 = ttk.Frame(lf_file)
        sub1.pack(fill="x", pady=5)
        ttk.Label(sub1, text="Cartella Input:").pack(side="left")
        self.ent_input = ttk.Entry(sub1)
        self.ent_input.insert(0, "input")
        self.ent_input.pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(sub1, text="Sfoglia...", command=self._browse_folder).pack(side="left")
        
        # Formato
        sub2 = ttk.Frame(lf_file)
        sub2.pack(fill="x", pady=5)
        ttk.Label(sub2, text="Formato File:").pack(side="left")
        self.cmb_fmt = ttk.Combobox(sub2, values=["csv", "json", "xlsx"], state="readonly", width=10)
        self.cmb_fmt.current(0)
        self.cmb_fmt.pack(side="left", padx=5)
        
        # Lingue
        sub3 = ttk.Frame(lf_file)
        sub3.pack(fill="x", pady=10)
        ttk.Label(sub3, text="Da Lingua:").pack(side="left")
        self.ent_src = ttk.Entry(sub3, width=15)
        self.ent_src.insert(0, "inglese")
        self.ent_src.pack(side="left", padx=5)
        ttk.Label(sub3, text="A Lingua:").pack(side="left")
        self.ent_tgt = ttk.Entry(sub3, width=15)
        self.ent_tgt.insert(0, "italiano")
        self.ent_tgt.pack(side="left", padx=5)

    def _build_adv_tab(self):
        f = self.tab_adv
        
        # CSV Specific
        lf_csv = ttk.LabelFrame(f, text="Opzioni CSV", padding=10)
        lf_csv.pack(fill="x", pady=10, padx=10)
        
        fr_c1 = ttk.Frame(lf_csv)
        fr_c1.pack(fill="x")
        ttk.Label(fr_c1, text="Delimitatore:").pack(side="left")
        self.ent_delim = ttk.Entry(fr_c1, width=5)
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
