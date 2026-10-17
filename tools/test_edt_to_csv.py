"""Check minimo: python3 tools/test_edt_to_csv.py"""
import csv
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.importazione_edt_aldo import edt_to_csv
from src.importazione_edt_aldo.edt_to_csv import ore_occupate

assert ore_occupate('1h00', '08h00') == [1]
assert ore_occupate('2h00', '08h00') == [1, 2]
assert ore_occupate('3h00', '10h00') == [3, 4, 5]
assert ore_occupate('2h00', '14h00') == [7, 8]


def test_disponibilita_solo_da_edt():
    with TemporaryDirectory() as cartella:
        radice = Path(cartella)
        edt_to_csv.pd.DataFrame([
            ['1', 'VANNI', 'BEATRICE', 'DIR', 'G4 LS', 'mercoledì', '08h00', '1h00'],
            ['2', 'VANNI', 'BEATRICE', 'DISPOS', '', 'martedì', '11h00', '2h00'],
            ['3', 'VANNI', 'BEATRICE', 'DIR', 'G4 LS', 'martedì', '12h00', '1h00'],
        ], columns=['NUMERO', 'DOC_COGN', 'DOC_NOME', 'MAT_COD', 'CLASSE',
                    'GIORNO', 'O.INIZIO', 'DURATA']).to_csv(
            radice / 'EXP_COURS.tsv', sep=';', encoding='utf-16', index=False)
        edt_to_csv.pd.DataFrame(
            [['4G', 'vanni.beatrice@pietroaldi.com']], columns=['ID', 'CIV'],
        ).to_csv(radice / 'elenco_classi_docenti_materie.tsv', sep='\t', index=False)
        edt_to_csv.main(cartella, cartella)
        with (radice / 'availability.csv').open(newline='') as f:
            riga, = csv.DictReader(f)
        dispos = {(giorno, ora) for giorno, valore in riga.items() if giorno != 'DOCENTE'
                  for ora, stato in enumerate(valore.split(';'), 1) if stato == 'DISPOS'}
        assert riga['DOCENTE'] == 'Vanni'
        assert dispos == {('MAR', 4)}, f"Disponibilità diverse da EDT: {dispos}"


if __name__ == '__main__':
    test_disponibilita_solo_da_edt()
    print("ok")
