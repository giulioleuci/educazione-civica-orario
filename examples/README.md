# Esempi fittizi

Tutti i dati in queste cartelle sono fittizi e minimi. I dati operativi restano
nelle cartelle ignorate `FILE_SCUOLA/` e `CALENDARIO_GENERATO/`.

## Generatore

`generatore/` contiene i quattro CSV di input. Per eseguire l'esempio dalla
radice del progetto:

```bash
cp examples/generatore/*.csv FILE_SCUOLA/
python3 -m src.generatore.main
```

## Conversione EDT/ALDO

`edt_aldo/` contiene sorgenti EDT e ALDO che producono gli stessi tre CSV di
`generatore/` (il file `closures.csv` resta un input del generatore):

```bash
python3 -m src.importazione_edt_aldo.edt_to_csv FILE_SCUOLA --input examples/edt_aldo
cp examples/generatore/closures.csv FILE_SCUOLA/
python3 -m src.generatore.main
```
