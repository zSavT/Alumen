# Alumen

**Alumen** è uno script Python da riga di comando progettato per automatizzare la traduzione di grandi quantità di testi contenuti in file CSV. Sfrutta i modelli linguistici di Google Gemini per fornire traduzioni accurate e contestualizzate, con un focus su flessibilità e robustezza.

## Indice

- [Alumen](#alumen)
  - [Indice](#indice)
  - [Funzionalità Principali](#funzionalità-principali)
  - [Prerequisiti - Installazione e Configurazione](#prerequisiti---installazione-e-configurazione)
- [Utilizzo](#utilizzo)
    - [Argomenti da Riga di Comando](#argomenti-da-riga-di-comando)
      - [Configurazione API e Modello](#configurazione-api-e-modello)
      - [Input/Output e Formato CSV](#inputoutput-e-formato-csv)
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

- Traduzione automatica da CSV
- Ricerca Ricorsiva nella cartella di input dei file da tradurre
- Supporto Multi-API Key con Rotazione
- Controllo delle Richieste per Minuto (RPM)
- Personalizzazione per Lingue
- Word Wrapping con carattere personalizzabile
- Modalità Interattiva
- Logging Dettagliato
- Ripresa esecuzione da un lavoro interrotto
- Alta configurazione

## Prerequisiti - Installazione e Configurazione
Prerequisiti:
- [Python](https://www.python.org/downloads/) 3.11 o superiore
- Libreria `google-generativeai`
- Una o più API key valide di [Google Gemini](https://aistudio.google.com/apikey)

Download, installazione e configurazione:

1. **Clona la repository**
2. **Installa le dipendenze**:
   ```ps1
   pip install google-generativeai
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
| `--max-cols`                | Numero massimo colonne ammesse                             | Nessuno (opzionale)         | `--max-cols 5`                                                |
| `--encoding`                | Codifica file in lettura/scrittura                         | `utf-8`                     | `--encoding iso-8859-1`                                       |
| `--game-name`               | Contesto specifico per il tono/termini della traduzione    | `un videogioco generico`    | `--game-name "The Witcher 3"`                                |
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

#### Input/Output e Formato CSV

- `--input`: Percorso cartella CSV (default: `input`)
- `--delimiter`: Delimitatore CSV (default: `,`)
- `--translate-col`: Colonna da tradurre (default: `3`)
- `--output-col`: Colonna per output (default: `3`)
- `--max-cols`: Numero massimo colonne ammesse (opzionale)
- `--encoding`: Codifica file (default: `utf-8`)

#### Parametri di Traduzione

- `--game-name`: Contesto gioco (default: `un videogioco generico`)
- `--source-lang`: Lingua originale (default: `inglese`)
- `--target-lang`: Lingua di destinazione (default: `italiano`)
- `--translation-only-output`: Output in formato `.txt` con sole traduzioni
- `--rpm`: Limite richieste/minuto (maggior info [qui](https://ai.google.dev/gemini-api/docs/rate-limits?hl=it))


#### A Capo Automatico (Word Wrapping)

- `--wrap-at`: Numero massimo caratteri per riga
- `--newline-char`: Simbolo per newline (`\n`, `<br>`, ecc.)

#### Utilità e Modalità Interattiva

- `--oneThread`: Disabilita animazione caricamento
- `--enable-file-log`: Abilita logging su file
- `--interactive`: Abilita comandi runtime da tastiera
- `--resume`: Riprende sessioni interrotte
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
- **Errori API Persistenti**: In caso di fallimenti continui, lo script entra in loop infinito senza alcun avviso o nota, per un possibile utilizzo in un server, finche le quote delle API non vengono resettate. Per un uso quotidiano/causale, si consiglia di interrompere lo script con `CTRL + C` e successivamente riprendere con `--resume` per continuare dove lo script ha operato come ultima traduzione.


