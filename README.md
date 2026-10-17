# Generatore Sostituzioni per un Calendario di Educazione Civica

Un modello OR-Tools CP-SAT per generare calendari ottimali di educazione civica per le scuole. Questo progetto (e questo README) è stato sviluppato con l'assistenza di strumenti di AI generativa (specialmente GPT-o1 Preview e Claude 5.5 Sonnet).

## Panoramica

Questo script genera un calendario di sostituzioni per l'educazione civica, con l'obiettivo di:
- Distribuire equamente le ore di insegnamento tra docenti e classi
- Garantire che ogni classe raggiunga le ore richieste di educazione civica
- Rispettare la disponibilità dei docenti e le chiusure della scuola
- Mantenere massimo un'ora di civica a settimana per classe

## Struttura del codice

- `src/generatore/main.py`: caricamento configurazioni e avvio
- `src/generatore/calendario.py`: caricamento dati, vincoli e soluzione CP-SAT
- `src/generatore/output.py`: esportazione CSV ed Excel
- `src/generatore/sicurezza.py`: sanitizzazione di percorsi, log, fogli e celle
- `src/importazione_edt_aldo/`: conversione dei dati EDT/ALDO in CSV
- `src/configurazione.py`: lettura dei file JSON di configurazione

## Requisiti

- Python 3.8+
- pandas
- numpy
- openpyxl

Installazione dipendenze:
```bash
pip install pandas numpy openpyxl ortools
```

## File di Input

I CSV sono letti dalla cartella indicata da `file_scuola` in `config_scuola.json` (default `FILE_SCUOLA`):

1. `classes.csv`: Orari delle classi con assegnazione docenti
   ```
   CLASSE,DOC LUN,DOC MAR,DOC MER,DOC GIO,DOC VEN,DOC SAB
   1SA,Docente1;Docente2...,...
   ```

2. `civics_teachers.csv`: Docenti di educazione civica e loro classi assegnate
   ```
   DOCENTE,CLASSI
   NomeDocente,Classe1;Classe2;Classe3
   ```

3. `availability.csv`: Disponibilità oraria dei docenti di civica (se disponibile è `DISPOS`)
   ```
   DOCENTE,LUN,MAR,MER,GIO,VEN,SAB
   NomeDocente,DISPOS;NO;DISPOS...,... 
   ```

4. `closures.csv`: Date di chiusura della scuola
   ```
   INIZIO,FINE,DESCRIZIONE
   21/12/2024,06/01/2025,Vacanze di Natale
   ```

## Utilizzo

1. Modificare i parametri in `config_generazione.json`. I nomi delle cartelle di input e output
   si impostano in `config_scuola.json` (`FILE_SCUOLA` e `CALENDARIO_GENERATO` per default).

2. Per una prova completa con dati fittizi, copiare gli input di esempio:

   ```bash
   cp examples/generatore/*.csv FILE_SCUOLA/
   ```

3. Eseguire il generatore:
   ```bash
   python3 -m src.generatore.main
   ```

Per convertire gli esempi EDT/ALDO senza copiare file nella radice, eseguire:

```bash
python3 -m src.importazione_edt_aldo.edt_to_csv FILE_SCUOLA --input examples/edt_aldo
cp examples/generatore/closures.csv FILE_SCUOLA/
python3 -m src.generatore.main
```

Gli esempi sono tutti fittizi. I file effettivi della scuola e i risultati della
generazione sono ignorati da Git; la struttura completa è in `examples/README.md`.

### Assegnazioni obbligatorie

Modificare la lista `assegnazioni_fisse` in `config_generazione.json` (vuota per default). Per esempio:

```json
"assegnazioni_fisse": [
  {
    "docente_civics": "FANTASIA",
    "classe": "1ALS",
    "data": "03/09/2030",
    "ora": 1,
    "docente_sostituito": "ESEMPIO"
  }
]
```

Il campo `docente_sostituito` è facoltativo e, se presente, deve corrispondere all'orario della classe.

Usare i nomi esatti dei CSV, date in formato `gg/mm/aaaa` e ore numerate da 1.
Ogni voce fissa il docente di civica nella classe, data e ora indicate: il resto
del calendario viene costruito rispettando queste assegnazioni. Nelle settimane
corte le classi con un'assegnazione fissa hanno precedenza; le altre ore vengono
distribuite con il criterio di rotazione esistente.

Restano validi il limite di un'ora per classe a settimana, le chiusure, le classi
assegnate a ciascun docente, la disponibilità oraria e `allow_teacher_replace_self`.
Voci non valide o in conflitto interrompono la generazione con un errore esplicito;
le voci identiche ripetute contano una sola volta. L'esempio va adattato ai propri
dati e all'intervallo del calendario.

## Output

Lo script genera nella cartella di output specificata:
- `calendar.csv`: Calendario completo con date, classi e docenti
- `teachersLost.csv`: Statistiche sulle ore "perse" per docente
- `orario_classi.xlsx`: Sintesi settimanale per classe
- `orario_docenti.xlsx`: Vista settimanale per docente

## Dettagli Implementativi

Il calendario viene generato con OR-Tools CP-SAT:
1. Le classi che non condividono docenti civics formano gruppi indipendenti (di norma uno per docente): un modello per gruppo
2. Vincoli duri: 1 ora a settimana per classe fino a fine anno (nelle settimane ridotte dalle chiusure i docenti non coprono tutte le classi: `_assegna_settimane` toglie l'ora a rotazione), un docente in una sola classe alla volta
3. L'obiettivo riproduce `calcola_fitness`: penalità sulle ore perse oltre la quota proporzionale (quadratica, senza soglie piatte, così l'eccesso si ripartisce tra i docenti in proporzione alle loro ore) e varianza come somma di quadrati interi
4. Per ogni classe il modello riceve un limite inferiore esatto (`_minimo_classe`): il solver si ferma quando soluzione e limite distano meno di `gap_relativo`, altrimenti riprova con un altro seed (fino a `TENTATIVI_MAX`)
5. Se non esiste una soluzione ammissibile entro il tempo limite lo script termina con errore

## Ottimizzazione Prestazioni

Parametri regolabili:
- `num_cores`: Numero di thread del solver
- `gap_relativo`: Distanza relativa massima tra soluzione e limite inferiore a cui il solver si ferma, per ogni gruppo di classi (default `0.001`, cioè 0,1%). Usare `0` per cercare la dimostrazione dell'ottimo entro il tempo disponibile.
- `tempo_max_secondi`: Budget di risoluzione per gruppo di classi, normalmente uno per ogni docente di civica (default `900` secondi, cioè 15 minuti). Il budget totale è questo valore × numero di gruppi; il tempo risparmiato passa ai successivi, che possono quindi superare i 900 secondi. I tentativi con seed diversi condividono il budget del gruppo; si usa la migliore soluzione trovata.

Entrambi si modificano in `config_generazione.json`.
Con tre docenti di civica che lavorano su gruppi indipendenti il budget totale è di
45 minuti. Se più docenti condividono classi, le loro classi formano un unico gruppo
con un budget comune.

## Licenza

GNU GPL - Vedere il file LICENSE per i dettagli
