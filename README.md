
# Alumen - Suite di Traduzione AI Automatizzata

Alumen è un software open-source progettato per automatizzare la localizzazione di progetti software e videoludici. Utilizza i modelli linguistici di Google Gemini per tradurre massivamente file di testo mantenendo il contesto, la formattazione e le variabili di codice.

Il software è diviso in due componenti principali:
1.  **AlumenGUI.py**: Un'interfaccia grafica per configurare ed eseguire le traduzioni senza usare il terminale.
2.  **AlumenCore.py**: Il motore di traduzione da riga di comando, ideale per automazione e server.

Supporta nativamente i formati **CSV, Excel (XLSX), JSON, PO (Gettext) e SRT (Sottotitoli)**.

## Indice

1.  [Prerequisiti e Installazione](#prerequisiti-e-installazione)
2.  [Configurazione API Google](#configurazione-api-google)
3.  [Guida all'uso: Interfaccia Grafica (GUI)](#guida-alluso-interfaccia-grafica-gui)
4.  [Guida all'uso: Riga di Comando (CLI)](#guida-alluso-riga-di-comando-cli)
5.  [Funzionalità Avanzate](#funzionalità-avanzate)
    *   [Smart Batching](#smart-batching)
    *   [Agentic Reflection](#agentic-reflection)
    *   [Glossario e Guide di Stile](#glossario-e-guide-di-stile)
    *   [Dry Run (Preventivo)](#dry-run-preventivo)
6.  [Dettagli Formati File Supportati](#dettagli-formati-file-supportati)
7.  [Utility: Estrattore di Cache](#utility-estrattore-di-cache)
8.  [Utility: Integrazione Telegram](#utility-integrazione-telegram)

---

## Prerequisiti e Installazione

Alumen richiede che **Python 3.10** o versioni successive sia installato sul sistema.

### Installazione delle Librerie
Per utilizzare Alumen e tutte le sue funzionalità (incluso il supporto Excel e Telegram), è necessario installare le dipendenze tramite il terminale:

```bash
pip install google-generativeai polib openpyxl rich tenacity packaging "python-telegram-bot[job-queue]"
```

---

## Configurazione API Google

Alumen utilizza l'API di Google Gemini. È necessario ottenere una chiave API gratuita o a pagamento.

1.  Visitare Google AI Studio.
2.  Creare una nuova API Key.
3.  La chiave può essere fornita ad Alumen in due modi:
    *   Incollandola direttamente nell'interfaccia o nel comando.
    *   Creando un file chiamato `api_key.txt` nella stessa cartella dello script e incollando la chiave al suo interno. È possibile inserire più chiavi (una per riga) per permettere al software di ruotarle automaticamente in caso di esaurimento della quota.

---

## Guida all'uso: Interfaccia Grafica (GUI)

Per gli utenti che preferiscono un ambiente visivo, avviare lo script `AlumenGUI.py`:

```bash
python AlumenGUI.py
```

Si aprirà una finestra divisa in tre schede principali:

### 1. Scheda Configurazione
Qui si impostano i parametri fondamentali:
*   **API Keys:** Inserire le chiavi Google Gemini separate da virgola. Se presente il file `api_key.txt`, verrà caricato automaticamente.
*   **Cartella Input:** Selezionare la cartella che contiene i file da tradurre.
*   **Formato File:** Scegliere tra csv, json, xlsx, po, srt.
*   **Lingue:** Definire la lingua di origine (es. "Inglese") e quella di destinazione (es. "Italiano").
*   **Opzioni Specifiche:**
    *   *CSV:* Delimitatore e indice colonne.
    *   *JSON:* Chiavi da tradurre (obbligatorio per i file JSON).

### 2. Scheda Avanzate
Qui si gestiscono le opzioni per la qualità e le prestazioni:
*   **Glossario:** Selezionare un file CSV contenente termini che devono essere tradotti in modo fisso.
*   **Batch Size:** Numero di frasi inviate in una singola richiesta. Default: 30. Valori più alti aumentano la velocità ma consumano più token.
*   **Cache Persistente:** Se attivo, salva le traduzioni su disco. Se si riavvia il programma, le frasi già tradotte non verranno inviate nuovamente all'API.

### 3. Scheda Esecuzione
*   **Log:** Mostra in tempo reale le operazioni svolte dal software.
*   **Avvia Traduzione:** Lancia il processo.
*   **Stop:** Interrompe il processo in modo sicuro.

---

## Guida all'uso: Riga di Comando (CLI)

Per utilizzare il motore di traduzione direttamente da terminale (utile per server o script batch), avviare `AlumenCore.py`.

### Sintassi Base
```bash
python AlumenCore.py --input "percorso/cartella" --file-type csv --api "LA_TUA_KEY"
```

### Elenco Completo degli Argomenti

#### Configurazione Generale
*   `--input`: Cartella contenente i file da tradurre. Default: `input`.
*   `--api`: Chiavi API separate da virgola.
*   `--model-name`: Modello Gemini da usare. Default: `gemini-2.0-flash`.
*   `--enable-file-log`: Attiva la scrittura dei log su file `log.txt`.

#### Gestione File
*   `--file-type`: Formato dei file (`csv`, `json`, `xlsx`, `po`, `srt`).
*   `--encoding`: Codifica del testo (es. `utf-8`, `cp1252`). Default: `utf-8`.

#### Lingua e Traduzione
*   `--source-lang`: Lingua di partenza. Default: `inglese`.
*   `--target-lang`: Lingua di arrivo. Default: `italiano`.
*   `--glossary`: Percorso del file CSV del glossario.
*   `--style-guide`: Percorso di un file di testo contenente istruzioni di stile.

#### Prestazioni e Batching
*   `--batch-size`: Quante righe tradurre contemporaneamente. Default: 30.
*   `--rpm`: Limite di Richieste Per Minuto per evitare errori di quota.
*   `--persistent-cache`: Abilita il salvataggio/caricamento della cache da `alumen_cache.json`.
*   `--dry-run`: Esegue una simulazione. Legge i file e calcola costo e token senza tradurre nulla.
*   `--reflect`: Attiva la modalità di auto-riflessione (vedi sezione Funzionalità Avanzate).

#### Opzioni Specifiche per Formato
*   **CSV:**
    *   `--delimiter`: Carattere separatore (es. `,` o `;`).
    *   `--translate-col`: Numero colonna da leggere (0 per la prima colonna).
    *   `--output-col`: Numero colonna dove scrivere la traduzione.
*   **JSON:**
    *   `--json-keys`: Lista chiavi da tradurre (es. `name,description`). Obbligatorio.
    *   `--match-full-json-path`: Se attivo, cerca la chiave includendo i genitori (es. `items.sword.name`).
*   **Excel:**
    *   `--xlsx-source-col`: Lettera colonna origine (es. A).
    *   `--xlsx-target-col`: Lettera colonna destinazione (es. B).

---

## Funzionalità Avanzate

### Smart Batching
Tradizionalmente, i tool di traduzione inviano una frase alla volta. Alumen raggruppa fino a 50 frasi in un unico pacchetto (Batch).
*   **Vantaggio:** Velocità aumentata fino a 20 volte.
*   **Funzionamento:** Lo script calcola la lunghezza delle frasi. Se un gruppo di frasi supera il limite di token del modello, il pacchetto viene chiuso e inviato automaticamente per evitare errori, anche se non ha raggiunto il numero massimo di righe.

### Agentic Reflection
Attivabile con il flag `--reflect`.
Questa modalità utilizza un processo a due fasi per ogni blocco di testo:
1.  **Traduzione:** Il modello traduce il testo.
2.  **Critica:** Il modello rilegge la propria traduzione cercando errori grammaticali, incongruenze di genere o tono, e li corregge.
*   **Nota:** Questa modalità raddoppia i tempi di esecuzione e i costi API, ma garantisce la massima qualità possibile.

### Glossario e Guide di Stile
*   **Glossario:** Creare un file CSV con due colonne: `Termine Originale,Termine Tradotto`. Alumen inietterà queste regole nel cervello dell'AI, forzandola a usare la terminologia specifica (es. "Potion" -> "Pozione").
*   **Style Guide:** È possibile fornire un file `.txt` con istruzioni discorsive (es. "Usa un tono medievale", "Dai del Voi ai personaggi").

### Dry Run (Preventivo)
Il flag `--dry-run` è utile prima di iniziare un grande progetto. Lo script analizzerà tutti i file nella cartella di input e fornirà un report contenente:
*   Numero totale di caratteri.
*   Stima dei token totali.
*   Stima del costo economico (basato sui prezzi pubblici di Gemini Flash).
Il processo termina immediatamente dopo il report senza effettuare traduzioni.

---

## Dettagli Formati File Supportati

### CSV (Comma Separated Values)
Ideale per tabelle di dati. È possibile specificare quale colonna leggere e in quale scrivere. Se la colonna di destinazione è diversa da quella di origine, l'originale viene preservato.

### Excel (XLSX)
Supporto nativo per fogli di calcolo moderni. Lo script legge dalla colonna specificata (default A) e scrive nella colonna specificata (default B). Non altera formattazione o formule nelle altre celle.

### JSON
Supporta file JSON annidati. Poiché i JSON contengono anche dati di struttura, è **obbligatorio** specificare quali chiavi contengono testo traducibile usando l'argomento `--json-keys`.

### PO (Gettext)
Standard per la traduzione di software Linux e web. Alumen legge il `msgid` e scrive nel `msgstr`. Supporta contesti (`msgctxt`).

### SRT (Sottotitoli)
Formatta il file rispettando i timecode. Traduce solo i blocchi di testo, lasciando invariati i numeri di sequenza e le indicazioni temporali.

---

## Utility: Estrattore di Cache

Lo script `cache_extractor.py` permette di creare un file di cache partendo da traduzioni esistenti. Questo è utile se si possiede già la versione inglese e italiana di un gioco precedente e si vuole insegnare ad Alumen quelle traduzioni.

### Utilizzo
```bash
python cache_extractor.py --source-dir "cartella_originale" --target-dir "cartella_tradotta" --file-type csv --source-col 0 --target-col 1
```
Lo script genererà un file `alumen_cache.json` che potrà essere letto da `AlumenCore.py` abilitando l'opzione `--persistent-cache`.

---

## Utility: Integrazione Telegram

Alumen può essere controllato e monitorato da remoto tramite Telegram.

### Configurazione
1.  Creare un bot tramite `@BotFather` su Telegram e ottenere il Token.
2.  Ottenere il proprio Chat ID tramite `@userinfobot`.
3.  Creare un file `telegram_config.json` nella cartella dello script:
    ```json
    {
      "bot_token": "IL_TUO_TOKEN",
      "chat_id": "IL_TUO_CHAT_ID"
    }
    ```

### Utilizzo
Avviare `AlumenCore.py` o la GUI assicurandosi che l'opzione Telegram sia attiva (flag `--telegram` da riga di comando).
Il bot invierà notifiche sullo stato di avanzamento e accetterà comandi come:
*   `/status`: Mostra statistiche e file correntemente in lavorazione.
*   `/stop`: Richiede l'arresto sicuro dello script.
| Argomento | Descrizione | Default |
| :--- | :--- | :--- |
| **`--api`** | Specifica una o più chiavi API Gemini, separate da virgola. | - |
| **`--model-name`** | Nome del modello Gemini da utilizzare. | `gemini-2.5-flash` |

### Configurazione File e Formato

| Argomento | Descrizione | Default |
| :--- | :--- | :--- |
| **`--input`** | Percorso della cartella base contenente i file da tradurre. | `input` |
| **`--file-type`** | Tipo di file da elaborare (`csv`, `json` o `po`). | `csv` |
| **`--encoding`** | Codifica caratteri dei file. | `utf-8` |

### Input/Output e Formato CSV

| Argomento | Descrizione | Default |
| :--- | :--- | :--- |
| **`--delimiter`** | [Solo CSV] Carattere delimitatore. | `,` |
| **`--translate-col`** | [Solo CSV] Indice (0-based) della colonna da tradurre. | `3` |
| **`--output-col`** | [Solo CSV] Indice (0-based) della colonna per il testo tradotto. | `3` |
| **`--max-cols`** | [Solo CSV] Numero massimo di colonne attese per riga (controlli). | Nessun controllo |

### Input/Output e Formato JSON

| Argomento | Descrizione | Default |
| :--- | :--- | :--- |
| **`--json-keys`** | **[Solo JSON, Obbligatorio]** Elenco di chiavi (separate da virgola) da tradurre. Supporta notazione a punto (es. `key1,path.to.key2`). | - |
| **`--match-full-json-path`** | [Solo JSON] Richiede la corrispondenza del percorso completo della chiave (es. `parent.child.key`). | `False` |

### Parametri di Traduzione

| Argomento | Descrizione | Default |
| :--- | :--- | :--- |
| **`--game-name`** | Nome del gioco per contestualizzare la traduzione. | `un videogioco generico` |
| **`--source-lang`** | Lingua originale del testo. | `inglese` |
| **`--target-lang`** | Lingua di destinazione. | `italiano` |
| **`--prompt-context`** | Aggiunge un'informazione contestuale extra a ogni prompt. | - |
| **`--custom-prompt`** | Usa un prompt personalizzato. **OBBLIGATORIO:** includere `{text_to_translate}`. | - |
| **`--translation-only-output`** | L'output (per CSV/JSON) conterrà solo i testi tradotti, uno per riga. | `False` |
| **`--rpm`** | Numero massimo di richieste API a Gemini per minuto (Rate Limit). | Nessun limite |
| **`--enable-file-context`** | **Abilita il Contesto Intelligente del File.** Analizza le prime 15 frasi del file per generare un contesto. | `False` |
| **`--full-context-sample`** | **[Necessita `--enable-file-context`]** Utilizza **tutte** le frasi valide nel file per generare il contesto. | `False` |
| **`--context-window N`** | Crea una memoria a breve termine (deque) che inserisce nel prompt le traduzioni precedenti, N è il numero di traduzioni precedenti da passare. | 0 (nessun testo) |

### A Capo Automatico (Word Wrapping)

| Argomento | Descrizione | Default |
| :--- | :--- | :--- |
| **`--wrap-at`** | Lunghezza massima della riga per a capo automatico. | - |
| **`--newline-char`** | Carattere da usare per l'a capo automatico. | `\n` |

### Utilità e Modalità Interattiva

| Argomento | Descrizione | Default |
| :--- | :--- | :--- |
| **`--enable-file-log`** | Attiva la scrittura di un log (`log.txt`). | `False` |
| **`--interactive`** | Abilita comandi interattivi nella console. | `False` |
| **`--telegram`** | Abilita il logging e i comandi tramite un bot Telegram. | `False` |
| **`--resume`** | Tenta di riprendere la traduzione da file parziali (supportato per CSV). Per JSON/PO, riutilizza le traduzioni in cache. | `False` |
| **`--rotate-on-limit-or-error`** | Passa alla API key successiva in caso di errore o limite RPM. | `False` |
| **`--persistent-cache`** | Attiva la cache persistente su file (`alumen_cache.json`). | `False` |
| **`--server`** | non blacklista mai le API key per errori o limiti giornalieri, ma riprova all'infinito sulla stessa chiave. | `False` |

-----

## Modalità Interattiva

Se lo script viene avviato con `--interactive` (o `--telegram`), è possibile inviare comandi per gestire l'esecuzione.

| Comando | Descrizione |
| :--- | :--- |
| **`help`** | Mostra l'elenco di tutti i comandi disponibili. |
| **`pause`** | Mette in pausa l'elaborazione e mostra le statistiche. |
| **`resume`** | Riprende l'elaborazione. |
| **`stop`** | Richiede un'uscita pulita al termine del file corrente. |
| **`skip api`** | Salta l'API key in uso e forza una rotazione. |
| **`skip file`** | Salta il file corrente e passa al successivo. |
| **`stats`** | Mostra le statistiche di esecuzione aggiornate. |
| **`show file_progress`** | Mostra l'avanzamento all'interno del file corrente. |
| **`show rpm`** | Mostra le statistiche RPM correnti (limite, utilizzo, attesa). |
| **`context`** | Visualizza il contesto generato per il file in elaborazione. |
| **`prompt`** | Visualizza l'ultimo prompt di traduzione inviato a Gemini. |
| **`set model <nome>`** | Aggiorna al volo il modello Gemini da utilizzare. |
| **`set rpm <limite>`** | Imposta il limite di Richieste al Minuto (RPM). Usa `0` per disabilitarlo. |
| **`set max_entries <N>`** | Salta automaticamente i file con più di `N` entry da tradurre. Usa `0` per disabilitare. |
| **`add api <chiave>`** | Aggiunge una nuova chiave API alla sessione. |
| **`remove key <indice>`** | Rimuove una chiave API specificando il suo indice. |
| **`list keys`** | Mostra tutte le API key, il loro stato e il numero di chiamate. |
| **`blacklist <indice>`** | Aggiunge una chiave API alla lista nera. |
| **`clear blacklist`** | Rimuove tutte le chiavi dalla lista nera. |
| **`reload cache`** | Ricarica la cache persistente da disco. |
| **`clear cache`** | Svuota la cache di traduzione in memoria. |
| **`save cache`** | Salva immediatamente la cache in memoria su disco. |

-----

## Utility: Estrattore di Cache (`cache_extractor.py`)
Alumen include uno script di utilità, `cache_extractor.py`, progettato per un compito specifico: costruire un file `alumen_cache.json` partendo da una cartella di file sorgente (es. in inglese) e una cartella di file già tradotti (es. in italiano).

Questo è estremamente utile se si dispone già di un set di traduzioni (magari fatte a mano o con un altro strumento) e si desidera "importarle" nella cache di Alumen. In questo modo, quando Alumen verrà eseguito su quei file, troverà le traduzioni nella cache e non sprecherà chiamate API.

Lo script ha i suoi argomenti da riga di comando. L'uso base è:

È necessario specificare i parametri di formato (es. `--json-keys` per JSON, `--source-col/--target-col` per CSV) e i parametri di traduzione (es. `--game-name`) affinché le chiavi di cache generate corrispondano a quelle che Alumen cercherà.
Usa `python cache_extractor.py --help` per tutti i dettagli.

## Esempi di Utilizzo

#### 1\. Traduzione PO con Contesto, Limiti e Controllo Telegram

Avvia la traduzione di file PO, limitando le richieste, ruotando le API, abilitando il contesto intelligente e il controllo remoto via Telegram.

```ps1
py .\Alumen.py --file-type "po" --game-name "Yakuza 4 Remastered" --rpm 15 --enable-file-log --interactive --rotate-on-limit-or-error --enable-file-context --persistent-cache --telegram
```

#### 2\. Traduzione CSV standard con log e API multipla

Traduce un CSV specificando la colonna di input e output, utilizzando una delle API Key disponibili e salvando un log.

```ps1
python Alumen.py --file-type csv --translate-col 2 --output-col 4 --enable-file-log --api "key1...,key2..."
```

#### 3\. Traduzione JSON con percorso completo e wrapping

Traduce chiavi specifiche in file JSON, richiedendo la corrispondenza del percorso completo e formattando l'output per non superare gli 80 caratteri.

```ps1
python Alumen.py --file-type json --json-keys "data.title,menu.help_text" --match-full-json-path --wrap-at 80
```

#### 4\. Estrazione cache

Permette di estrarre la cache dai file già tradotti, considerando i file originali per i controlli e i valori non presenti nella cache, verranno salvati grazie all'append.

```ps1
python cache_extractor.py --source-dir input --target-dir tradotto --file-type po --source-lang inglese --target-lang italiano --game-name "Game Name" --append
```

-----

## Risultato e Statistiche Finali

Alla fine dell'esecuzione (o con il comando `stats`), lo script stampa un riepilogo statistico completo, formattato in tabelle chiare e leggibili grazie alla libreria `rich`.

| Statistica | Descrizione |
| :--- | :--- |
| **Tempo Totale di Esecuzione** | Il tempo complessivo impiegato dall'avvio alla chiusura. |
| **File Tradotti** | Il numero totale di file processati con successo. |
| **Frasi/Entry Tradotte** | Il conteggio totale di singole stringhe passate all'API o recuperate dalla cache. |
| **Cache Hit Totali** | Numero di traduzioni trovate nella cache, che hanno evitato una chiamata API. |
| **API Call Totali** | Numero complessivo di richieste effettive inviate a Gemini. |
| **Dettaglio Utilizzo API Key** | Una tabella che mostra quante chiamate sono state eseguite da ciascuna API key. |

-----

# ❗ Note Importanti

  - **Quota API**: Usa `--rpm` per evitare di superare i limiti di richieste di Gemini.
  - **Contesto Completo (`--full-context-sample`)**: Utilizzare questa opzione su file molto grandi può superare il limite massimo di token del prompt, causando errori API (Generalmente 32K token per Gemini).
  - **Errori API Persistenti**: Se tutte le chiavi API disponibili falliscono, lo script entrerà in una routine di attesa prolungata. È possibile interromperlo con `CTRL + C`.
