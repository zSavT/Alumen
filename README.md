# Alumen

**Alumen** è uno script Python da riga di comando progettato per automatizzare la traduzione di grandi quantità di testi contenuti in file CSV, JSON e PO. Sfrutta i modelli linguistici di Google **Gemini** per fornire traduzioni accurate e contestualizzate, con un focus su flessibilità e robustezza.

## Indice

- [Alumen](#alumen)
  - [Indice](#indice)
  - [Funzionalità Principali](#funzionalità-principali)
- [Storia\\Creazione Progetto](#storiacreazione-progetto)
  - [Utilizzo](#utilizzo)
    - [Prerequisiti - Installazione e Configurazione](#prerequisiti---installazione-e-configurazione)
      - [Argomenti da Riga di Comando](#argomenti-da-riga-di-comando)
        - [Configurazione API e Modello](#configurazione-api-e-modello)
        - [Configurazione File e Formato](#configurazione-file-e-formato)
        - [Input/Output e Formato CSV](#inputoutput-e-formato-csv)
        - [Input/Output e Formato JSON](#inputoutput-e-formato-json)
        - [Parametri di Traduzione](#parametri-di-traduzione)
        - [A Capo Automatico (Word Wrapping)](#a-capo-automatico-word-wrapping)
        - [Utilità e Modalità Interattiva](#utilità-e-modalità-interattiva)
    - [Modalità Interattiva](#modalità-interattiva)
    - [Esempi di Utilizzo](#esempi-di-utilizzo)
      - [1. Traduzione PO con Contesto Intelligente e Limiti](#1-traduzione-po-con-contesto-intelligente-e-limiti)
      - [2. Traduzione CSV standard con log e API multipla](#2-traduzione-csv-standard-con-log-e-api-multipla)
      - [3. Traduzione JSON con percorso completo e wrapping](#3-traduzione-json-con-percorso-completo-e-wrapping)
      - [4. Resume + wrapping](#4-resume--wrapping)
  - [Risultato e Statistiche Finali](#risultato-e-statistiche-finali)
  - [❗ Note Importanti](#-note-importanti)

## Funzionalità Principali

* **Supporto File Multiplo:** Elabora file `.csv`, `.json`, e `.po` (formato Gettext).
* **Traduzione Contesto-Consapevole:** Utilizza Gemini per traduzioni che mantengono il contesto del videogioco, preservando tag e placeholder.
* **Gestione API Avanzata:** Supporta la fornitura di chiavi multiple e la **rotazione automatica della chiave** in caso di errori o limiti RPM.
* **Contesto Intelligente del File (Novità!):** Analizza il contenuto di ogni file per determinare un contesto generale (es. "Dialoghi di un'ambientazione fantasy") da applicare a tutte le traduzioni di quel file.
* **Cache Persistente:** Salva le traduzioni per evitare chiamate API ripetute, accelerando le esecuzioni successive.
* **Modalità Interattiva:** Permette di mettere in pausa, riprendere o saltare la chiave API o il file corrente durante l'esecuzione.
* **Log e Statistiche Dettagliate:** Registra le operazioni su file di log e fornisce un riepilogo statistico completo alla fine.

# Storia\Creazione Progetto

Una primordiale versione dello script, è stata realizzata per la patch in italiano per il gioco [Valkyria Chronicles](https://github.com/zSavT/Valkyria-Chronicles-Patch-ITA.git) che traduceva in automatico i file di testo csv del gioco, al tempo lo script era scritto interamente da zero ed utilizzava le librerie di Google Deepl. Successivamente lo script è mutato per poter supportare la traduzione dei file del gioco [Yakuza 4](https://github.com/zSavT/Yakuza4-Patch-ITA.git), durante il processo di adattamento dello script, il "*motore*" della traduzione è cambiato e si è optato per il più versatile e potente Gemini, ovvero una vera e propria AI. Con il tempo ho optato per distaccare lo script e renderlo il più generico possibile, per adattarlo a qualsiasi tipologia di csv/progetto/gioco e questo grazie anche alla facilità dello stesso Gemini nel potenziamento dello script e della sua adattabilità.

## Utilizzo

### Prerequisiti - Installazione e Configurazione

1.  **Python:** Assicurati di avere Python 3.8 o superiore installato.
2.  **Librerie:** Installa le dipendenze necessarie:
    ```bash
    pip install google-genai polib argparse-color-formatter
    ```
3.  **Chiavi API:** Ottieni una o più chiavi API da Gemini. Puoi fornirle in due modi:
    * Tramite l'argomento `--api` (consigliato per script).
    * Inserendole, una per riga, in un file denominato `api_key.txt` nella stessa directory dello script.

#### Argomenti da Riga di Comando

##### Configurazione API e Modello
| Argomento | Descrizione | Default |
| :--- | :--- | :--- |
| **`--api`** | Specifica una o più chiavi API Gemini, separate da virgola. | - |
| **`--model-name`** | Nome del modello Gemini da utilizzare. | `gemini-2.5-flash` |

##### Configurazione File e Formato
| Argomento | Descrizione | Default |
| :--- | :--- | :--- |
| **`--input`** | Percorso della cartella base contenente i file da tradurre. | `input` |
| **`--file-type`** | Tipo di file da elaborare (`csv`, `json` o `po`). | `csv` |
| **`--encoding`** | Codifica caratteri dei file. | `utf-8` |

##### Input/Output e Formato CSV
| Argomento | Descrizione | Default |
| :--- | :--- | :--- |
| **`--delimiter`** | [Solo CSV] Carattere delimitatore. | `,` |
| **`--translate-col`** | [Solo CSV] Indice (0-based) della colonna da tradurre. | `3` |
| **`--output-col`** | [Solo CSV] Indice (0-based) della colonna per il testo tradotto. | `3` |
| **`--max-cols`** | [Solo CSV] Numero massimo di colonne attese per riga (controlli). | Nessun controllo |

##### Input/Output e Formato JSON
| Argomento | Descrizione | Default |
| :--- | :--- | :--- |
| **`--json-keys`** | **[Solo JSON, Obbligatorio]** Elenco di chiavi (separate da virgola) da tradurre. Supporta notazione a punto (es. `key1,path.to.key2`). | - |
| **`--match-full-json-path`** | [Solo JSON] Richiede la corrispondenza del percorso completo della chiave (es. `parent.child.key`). | `False` |

##### Parametri di Traduzione
| Argomento | Descrizione | Default |
| :--- | :--- | :--- |
| **`--game-name`** | Nome del gioco per contestualizzare la traduzione. | `un videogioco generico` |
| **`--source-lang`** | Lingua originale del testo. | `inglese` |
| **`--target-lang`** | Lingua di destinazione. | `italiano` |
| **`--prompt-context`** | Aggiunge un'informazione contestuale extra a ogni prompt. | - |
| **`--custom-prompt`** | Usa un prompt personalizzato. **OBBLIGATORIO:** includere `{text_to_translate}`. | - |
| **`--translation-only-output`** | L'output (per CSV/JSON) conterrà solo i testi tradotti, uno per riga. | `False` |
| **`--rpm`** | Numero massimo di richieste API a Gemini per minuto (Rate Limit). | Nessun limite (se non quello base dell'API) |
| **`--enable-file-context`** | **Abilita il Contesto Intelligente del File.** Analizza le prime 15 frasi del file per generare un contesto generale da usare in tutte le traduzioni del file. | `False` |
| **`--full-context-sample`** | **[Necessita `--enable-file-context`] Campione Completo per Contesto.** Utilizza **tutte** le frasi valide nel file (anziché solo le prime 15) per generare il contesto generale. | `False` |

##### A Capo Automatico (Word Wrapping)
| Argomento | Descrizione | Default |
| :--- | :--- | :--- |
| **`--wrap-at`** | Lunghezza massima della riga per a capo automatico. | - |
| **`--newline-char`** | Carattere da usare per l'a capo automatico. | `\n` |

##### Utilità e Modalità Interattiva
| Argomento | Descrizione | Default |
| :--- | :--- | :--- |
| **`--oneThread`** | Disabilita l'animazione di caricamento (utile in ambienti non interattivi). | `False` |
| **`--enable-file-log`** | Attiva la scrittura di un log (`log.txt`). | `False` |
| **`--interactive`** | Abilita comandi interattivi (`pause`, `resume`, `skip api`, `skip file`). | `False` |
| **`--resume`** | Tenta di riprendere la traduzione da file parziali (solo per JSON e PO che salvano in `finally`). | `False` |
| **`--rotate-on-limit-or-error`** | Passa alla API key successiva in caso di errore persistente o limite RPM raggiunto. | `False` |
| **`--persistent-cache`** | Attiva la cache persistente su file (`alumen_cache.json`). | `False` |

### Modalità Interattiva

Se avviato con `--interactive`, lo script rimane in ascolto sulla console per i seguenti comandi:

| Comando | Funzione |
| :--- | :--- |
| **`pause`** | Mette in pausa l'esecuzione dello script. |
| **`resume`** | Riprende l'esecuzione dopo una pausa. |
| **`skip api`** | Abbandona l'API key corrente e passa immediatamente alla successiva (se disponibile). |
| **`skip file`** | Interrompe l'elaborazione del file corrente e passa al successivo (i progressi parziali vengono salvati). |

### Esempi di Utilizzo

#### 1. Traduzione PO con Contesto Intelligente e Limiti
Avvia la traduzione di file PO, limitando le richieste, ruotando le api disponibili, abilitando il contesto intelligente, abilitando il logging e la cache su file.
```ps1
py .\Alumen.py --file-type "po" --game-name "Yakuza 4 Remastered" --rpm 15 --enable-file-log --interactive --rotate-on-limit-or-error --enable-file-context --full-context-sample --persistent-cache
````

#### 2\. Traduzione CSV standard con log e API multipla

Traduce un CSV specificando la colonna di input e output, utilizzando la prima API Key disponibile e salvando un log.

```ps1
python Alumen.py --file-type csv --translate-col 2 --output-col 4 --enable-file-log
```

#### 3\. Traduzione JSON con percorso completo e wrapping

Traduce chiavi specifiche in file JSON, richiedendo la corrispondenza del percorso completo e formattando l'output per non superare gli 80 caratteri.

```ps1
python Alumen.py --file-type json --json-keys "data.title,menu.help_text" --match-full-json-path --wrap-at 80 --newline-char "\r\n"
```

#### 4\. Resume + wrapping

Prova a continuare l'esecuzione interrotta in precedenza e formatta il testo tradotto.

```ps1
python Alumen.py --resume --wrap-at 80 --newline-char "<br>"
```

-----

## Risultato e Statistiche Finali

Alla fine dell'esecuzione (o in caso di interruzione con `CTRL+C`), lo script stampa un **Riepilogo Statistico Completo** per fornirti una panoramica dettagliata dell'intera sessione di traduzione:

| Statistica | Descrizione |
| :--- | :--- |
| **Tempo Totale di Esecuzione** | Il tempo complessivo impiegato dall'avvio alla chiusura dello script. |
| **Tempo Medio per File** | Il tempo medio di esecuzione calcolato per ogni file elaborato. |
| **File Tradotti** | Il numero totale di file (CSV, JSON, PO) che sono stati processati. |
| **Frasi/Entry Tradotte** | Il conteggio totale di singole stringhe di testo o entry (msgid/msgctxt) passate all'API per la traduzione. |
| **Cache Hit Totali** | Numero di traduzioni trovate nella cache (locale o persistente), che hanno evitato una chiamata API. |
| **API Call Totali** | Numero complessivo di richieste effettive inviate a Gemini. |
| **--- Dettaglio Utilizzo API Key ---** | Mostra quante chiamate sono state eseguite da ciascuna API key fornita. |

-----

## ❗ Note Importanti

  - **Quota API**: Usa `--rpm` per evitare di superare i limiti di richieste impostati da Gemini.
  - **Ripresa (`--resume`)**: Funziona bene se i file non vengono modificati tra le sessioni e sfrutta la logica di riscrittura parziale dei formati JSON e PO.
  - **Contesto Completo (`--full-context-sample`)**: Utilizzare campioni di contesto troppo lunghi può superare il limite massimo di token di un prompt, causando errori API (Generalmente 32K token per Gemini-2.5-Flash).
  - **Errori API Persistenti**: In caso di fallimenti continui, lo script entrerà in una routine di attesa e rotazione API, ma se tutte le API falliscono, la pausa sarà estesa per non sovraccaricare il sistema. Interrompere lo script con `CTRL + C` per uscire.