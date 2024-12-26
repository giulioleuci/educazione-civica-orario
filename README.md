# Generatore Sostituzioni per un Calendario di Educazione Civica

Un algoritmo genetico per generare calendari ottimali di educazione civica per le scuole. Questo progetto (e questo README) è stato sviluppato con l'assistenza di strumenti di AI generativa (specialmente GPT-o1 Preview).

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
pip install pandas numpy openpyxl
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
       num_generazioni=400,
       popolazione_size=500
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

Inoltre, ogni generazione crea una sottocartella con risultati intermedi.

## Dettagli Implementativi

Il calendario viene generato utilizzando un algoritmo genetico che:
1. Crea una popolazione iniziale usando approcci greedy, batch e random
2. Evolve le soluzioni attraverso crossover e mutazione
3. Valuta il fitness basandosi su metriche di qualità del calendario
4. Implementa early stopping quando non vengono trovati miglioramenti

## Ottimizzazione Prestazioni

Parametri regolabili per l'ottimizzazione:
- `num_cores`: Numero di core CPU da utilizzare
- `popolazione_size`: Dimensione della popolazione per generazione
- `probabilita_mutazione`: Probabilità di mutazione
- `num_generazioni`: Numero massimo di generazioni da eseguire

## Licenza

GNU GPL - Vedere il file LICENSE per i dettagli
