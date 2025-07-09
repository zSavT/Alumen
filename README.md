# Alumen

**Alumen** è uno script Python da riga di comando progettato per automatizzare la traduzione di grandi quantità di testi contenuti in file CSV e JSON. Sfrutta i modelli linguistici di Google Gemini per fornire traduzioni accurate e contestualizzate, con un focus su flessibilità e robustezza.

## Indice

- [Alumen](#alumen)
  - [Indice](#indice)
  - [Funzionalità Principali](#funzionalità-principali)
  - [Prerequisiti - Installazione e Configurazione](#prerequisiti---installazione-e-configurazione)
- [Utilizzo](#utilizzo)
    - [Argomenti da Riga di Comando](#argomenti-da-riga-di-comando)
      - [Configurazione API e Modello](#configurazione-api-e-modello)
    - [Configurazione File e Formato](#configurazione-file-e-formato)
      - [Input/Output e Formato CSV](#inputoutput-e-formato-csv)
      - [Input/Output e Formato JSON](#inputoutput-e-formato-json)
      - [Parametri di Traduzione](#parametri-di-traduzione)
      - [A Capo Automatico (Word Wrapping)](#a-capo-automatico-word-wrapping)
      - [Utilità e Modalità Interattiva](#utilità-e-modalità-interattiva)
  - [Modalità Interattiva](#modalità-interattiva)
  - [Ripresa delle Traduzioni (`--resume`)](#ripresa-delle-traduzioni---resume)
  - [Logging](#logging)
  - [Esempi di Utilizzo](#esempi-di-utilizzo)
    - [Traduzione solo testo, con gioco specifico:](#traduzione-solo-testo-con-gioco-specifico)
    - [API key + RPM + log + interattiva:](#api-key--rpm--log--interattiva)
    - [Resume + wrapping:](#resume--wrapping)
- [❗ Note Importanti](#-note-importanti)


## Funzionalità Principali

- Traduzione automatica da CSV e JSON
- Ricerca Ricorsiva nella cartella di input dei file da tradurre
- Supporto Multi-API Key con Rotazione
- Controllo delle Richieste per Minuto (RPM)
- Personalizzazione per Lingue
- Word Wrapping con carattere personalizzabile
- Modalità Interattiva
- Logging Dettagliato
- Ripresa esecuzione da un lavoro interrotto
- Alta configurazione prompt

## Prerequisiti - Installazione e Configurazione
Prerequisiti:
- [Python](https://www.python.org/downloads/) 3.11 o superiore
- Libreria `google-generativeai` e `argparse_color_formatter`
- Una o più API key valide di [Google Gemini](https://aistudio.google.com/apikey)

Download, installazione e configurazione:

1. **Clona la repository**
2. **Installa le dipendenze**:
   ```ps1
   pip install google-generativeai
   pip install argparse_color_formatter
   ```
  In alternativa, si può utilizzare il comando:
     ```ps1
        pip install -r requirements.txt
    ```

3. **Configura le API key**:

   - **Metodo 1: File `api_key.txt` (consigliato)**:
     ```
     AIzaSyXXXXXXXXXXXXXXXXXXXX1  
     AIzaSyXXXXXXXXXXXXXXXXXXXX2  
     ```

   - **Metodo 2: Flag `--api`**
     ```ps1
     python Alumen.py --api TUA_API_KEY_1,TUA_API_KEY_2
     ```

**Alumen** di base, controlla in modo ricorsivo tutti i file presenti nella cartella *input* (è possibile specificare un diverso percorso tramite l'apposito flag).


# Utilizzo

Tabella flag disponibili:

| Nome flag                    | Descrizione                                                | Valore di default           | Esempio di utilizzo                                             |
|-----------------------------|------------------------------------------------------------|-----------------------------|-----------------------------------------------------------------|
| `--api`                     | API key (una o più, separate da virgola)                   | Nessuno                     | `--api MIA_KEY1,MIA_KEY2`                                     |
| `--model-name`              | Modello Gemini da usare                                   | `gemini-2.5-flash`          | `--model-name gemini-pro`                                     |
| `--input`                   | Percorso cartella CSV                                      | `input`                     | `--input ./miei_csv`                                          |
| `--delimiter`               | Delimitatore CSV                                           | `,`                         | `--delimiter ;`                                               |
| `--translate-col`           | Indice colonna da tradurre (parte da 0 o 1)                | `3`                         | `--translate-col 2`                                           |
| `--output-col`              | Indice colonna output tradotto                             | `3`                         | `--output-col 4`                                              |
| `--file-type`               | Tipo di file da elaborare: 'csv' o 'json'.                 | `csv`                       | `--file-type json`                                            |
| `--match-full-json-path`    | [Solo JSON] Per le chiavi JSON, richiede la corrispondenza del percorso completo della chiave (es. 'parent.child.key'), invece del solo nome della chiave.                             | Nessuno (opzionale)         | `--match-full-json-path`                                                |
| `--json-keys`                | [Solo JSON, Obbligatorio] Elenco di chiavi (separate da virgola) da tradurre.                         | Nessuno                     | `--json-keys "name,description,item.lore"`                                       |
| `--max-cols`                | Numero massimo colonne ammesse                             | Nessuno (opzionale)         | `--max-cols 5`                                                |
| `--encoding`                | Codifica file in lettura/scrittura                         | `utf-8`                     | `--encoding iso-8859-1`                                       |
| `--game-name`               | Contesto specifico per il tono/termini della traduzione    | `un videogioco generico`    | `--game-name "The Witcher 3"`                                |
| `--prompt-context`          | Aggiunge un'informazione contestuale extra al prompt.      | Nessuno                     | `--prompt-context "Tradurre in un tono medievale."`           |
| `--custom-prompt`           | Usa un prompt personalizzato. OBBLIGATORIO: includere '{text_to_translate}'.                                     | Nessuno                  | `--custom-prompt "Traduci questo: {text_to_translate} in italiano."`                                      |
| `--source-lang`             | Lingua sorgente                                            | `inglese`                   | `--source-lang tedesco`                                       |
| `--target-lang`             | Lingua di destinazione                                     | `italiano`                  | `--target-lang spagnolo`                                      |
| `--translation-only-output` | Output con solo testo tradotto in `.txt`                   | Nessuno                     | `--translation-only-output`                                   |
| `--rpm`                     | Limite richieste per minuto                                | Nessuno                     | `--rpm 50`                                                     |
| `--wrap-at`                 | Numero massimo caratteri per riga                          | Nessuno                     | `--wrap-at 80`                                                |
| `--newline-char`            | Simbolo usato per newline (a capo)                         | Nessuno                     | `--newline-char "<br>"`                                      |
| `--oneThread`               | Disabilita l'animazione di caricamento                     | Nessuno                     | `--oneThread`                                                 |
| `--enable-file-log`         | Salva log su file `log.txt`                                | Nessuno                     | `--enable-file-log`                                           |
| `--interactive`             | Abilita modalità interattiva da tastiera durante esecuzione| Nessuno                     | `--interactive`                                               |
| `--resume`                  | Riprende esecuzione da un punto interrotto                 | Nessuno                     | `--resume`                                                    |
| `--rotate-on-limit-or-error`| Quando api va in errore o rpm termina, passa api successiva| Nessuno                     | `--rotate-on-limit-or-error`                                  |



### Argomenti da Riga di Comando

#### Configurazione API e Modello

- `--api`: API key (singola o multiple, separate da virgola)
- `--model-name`: Modello Gemini da usare (`gemini-2.5-flash` default)

### Configurazione File e Formato
- `--input`: Percorso della cartella base contenente i file da tradurre. Default: input
- `--file-type`: Tipo di file da elaborare: 'csv' o 'json'. Default: 'csv'
- `--encoding`: Codifica caratteri dei file. Default: 'utf-8'

#### Input/Output e Formato CSV

- `--delimiter`: Delimitatore CSV (default: `,`)
- `--translate-col`: Colonna da tradurre (default: `3`)
- `--output-col`: Colonna per output (default: `3`)
- `--max-cols`: Numero massimo colonne ammesse (opzionale)
- `--resume`: Riprende sessioni interrotte

#### Input/Output e Formato JSON

- `--json-keys`: Elenco di chiavi (separate da virgola) da tradurre. Supporta notazione a punto per chiavi annidate (es. 'key1,path.to.key2'). Obbligatorio per `--file-type json`.
- `--match-full-json-path`: Per le chiavi JSON, richiede la corrispondenza del percorso completo della chiave (es. 'parent.child.key'), invece del solo nome della chiave.

#### Parametri di Traduzione

- `--game-name`: Contesto gioco (default: `un videogioco generico`)
- `--source-lang`: Lingua originale (default: `inglese`)
- `--target-lang`: Lingua di destinazione (default: `italiano`)
- `--translation-only-output`: Output in formato `.txt` con sole traduzioni
- `--rpm`: Limite richieste/minuto (maggior info [qui](https://ai.google.dev/gemini-api/docs/rate-limits?hl=it))
- `--prompt-context`: Aggiunge un'informazione contestuale extra al prompt.
- `--custom-prompt`:  Usa un prompt personalizzato. OBBLIGATORIO: includere '{text_to_translate}'.

#### A Capo Automatico (Word Wrapping)

- `--wrap-at`: Numero massimo caratteri per riga
- `--newline-char`: Simbolo per newline (`\n`, `<br>`, ecc.)

#### Utilità e Modalità Interattiva

- `--oneThread`: Disabilita animazione caricamento
- `--enable-file-log`: Abilita logging su file
- `--interactive`: Abilita comandi runtime da tastiera
- `--rotate-on-limit-or-error`:  Quando api raggiunge il limite di rpm impostati o restituisce un messaggio di errore quota, si passa successivamente all'api successiva se disponibile per ottimizzare le tempistiche di elaborazione.


## Modalità Interattiva

Con `--interactive`, è possibile inserire comandi durante l’esecuzione:

- `skip api`: Passa alla prossima API key
- `skip file`: Salta il file corrente
- `pause`: Ferma l'esecuzione dello script
- `resume`: Riprende l'esecuzione dello script (Da non confondere con l'arg `--resume`)
- `help`: Mostra i comandi disponibili
- `exit` / `quit`: Termina l’interfaccia interattiva


## Ripresa delle Traduzioni (`--resume`)

Alumen può riprendere file interrotti:
- In CSV: Skippa righe già tradotte
- In `.txt` (`--translation-only-output`): Skippa righe corrispondenti


## Logging

Con `--enable-file-log`, viene generato `log.txt` che include:

- Sessione timestampata
- API key e modello usati
- File elaborati e tempi
- Errori API (senza dati sensibili)
- Comandi da modalità interattiva


## Esempi di Utilizzo


### Traduzione solo testo, con gioco specifico:
```ps1
python Alumen.py --input ./miei_csv --translation-only-output --game-name "The Witcher 3" --target-lang "spagnolo"
```
In questo caso lo script, controllerà tutti i file csv presenti nella cartella "miei_csv", il file di output avrà solo il testo tradotto e non copierà il file originale. Lo script tradurrà il testo in spagnolo, rispettando il contesto del gioco *The Witcher 3*.

### API key + RPM + log + interattiva:
```ps1
python Alumen.py --api MIA_CHIAVE --rpm 50 --enable-file-log --interactive
```
In questo caso lo script, è in modalità attiva, quindi sarà possibile effettuare delle piccole modifiche durante l'esecuzione dello script. Lo script utilizza API passata come parametro, creerà un file di log, con tutte le operazione effettuate e proverà ad eseguire massimo _50_ chiamate verso Gemini al minuto.

### Resume + wrapping:
```ps1
python Alumen.py --resume --wrap-at 80 --newline-char "<br>"
```
In questo caso lo script, proverà a continuare l'esecuzione interrotta manualmente in un esecuzione precedente e successivamente splitterà il testo tradotto ogni 80 caratteri aggiungedo come "testo a capo", il tag "`<br>`".



# ❗ Note Importanti

- **Quota API**: Usa `--rpm` per evitare il superamento i limiti impostati da [Gemini](https://ai.google.dev/gemini-api/docs/rate-limits?hl=it#free-tier).
- **Ripresa**: Funziona bene se i file non vengono modificati tra le sessioni.
- **Errori API Persistenti**: In caso di fallimenti continui, lo script entra in loop infinito senza alcun avviso o nota, per un possibile utilizzo in un server, finche le quote delle API non vengono resettate. Per un uso quotidiano/causale, si consiglia di interrompere lo script con `CTRL + C` e successivamente riprendere con `--resume` per continuare dove lo script ha operato come ultima traduzione. Il resume funziona solo con i file csv e non json.


