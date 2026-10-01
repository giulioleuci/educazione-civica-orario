# Generatore Sostituzioni per un Calendario di Educazione Civica

Un modello OR-Tools CP-SAT per generare calendari ottimali di educazione civica per le scuole. Questo progetto (e questo README) è stato sviluppato con l'assistenza di strumenti di AI generativa (specialmente GPT-o1 Preview e Claude 5.5 Sonnet).

## Panoramica

Questo script genera un calendario di sostituzioni per l'educazione civica, con l'obiettivo di:
- Distribuire equamente le ore di insegnamento tra docenti e classi
- Garantire che ogni classe raggiunga le ore richieste di educazione civica
- Rispettare la disponibilità dei docenti e le chiusure della scuola
- Mantenere massimo un'ora di civica a settimana per classe

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

Posizionare questi file CSV nella cartella dello script:

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

1. Configurare i parametri nello script:
   ```python
   generator = CalendarioGenerator(
       data_inizio_str='15/10/2024',
       data_fine_str='10/06/2025',
       ore_tot_civics=30,
       cartella_output="CALENDARIO_GENERATO",
       tempo_max_secondi=120,
       num_cores=4
   )
   ```

2. Eseguire lo script:
   ```bash
   python3 calendario-ed-civ-generator.py
   ```

## Output

Lo script genera nella cartella di output specificata:
- `calendar.csv`: Calendario completo con date, classi e docenti
- `teachersLost.csv`: Statistiche sulle ore "perse" per docente
- `orario_classi.xlsx`: Sintesi settimanale per classe
- `orario_docenti.xlsx`: Vista settimanale per docente

## Dettagli Implementativi

Il calendario viene generato con OR-Tools CP-SAT:
1. Le classi che non condividono docenti civics formano gruppi indipendenti (di norma uno per docente): un modello per gruppo
2. Vincoli duri: `ore_tot_civics` ore per classe, al massimo 1 ora a settimana per classe, un docente in una sola classe alla volta
3. L'obiettivo riproduce `calcola_fitness` (penalità a gradini come tabelle sulle ore perse, varianza come termine quadratico intero)
4. Se non esiste una soluzione ammissibile entro il tempo limite lo script termina con errore

## Ottimizzazione Prestazioni

Parametri regolabili:
- `num_cores`: Numero di thread del solver
- `tempo_max_secondi`: Tempo medio per ogni modello: il budget totale è questo valore × numero di modelli e il tempo non usato da un modello che dimostra l'ottimo passa ai successivi (si usa la migliore soluzione trovata)

## Licenza

GNU GPL - Vedere il file LICENSE per i dettagli
