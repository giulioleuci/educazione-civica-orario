"""
Genera classes.csv, civics_teachers.csv, availability.csv per calendario-ed-civ-generator.py
a partire da EXP_COURS.csv (EDT) e elenco_classi_docenti_materie.tsv (ALDO).

Uso: python3 script_from_edt_and_aldo/edt_to_csv.py [cartella_output]
     (input letti dalla radice del repo; output di default nella radice del repo,
      che e' dove il generatore li cerca)
     Disponibilita': i docenti CIV sono DISPOS UNICAMENTE nelle ore "a disposizione"
     (MAT_COD DISPOS di EDT, durata espansa); tutte le altre ore sono NO.
"""

import os
import sys
from collections import defaultdict

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import extract_civics_teachers_mapping, format_teacher_name, map_cours_class_to_id

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GIORNI = {'lunedì': 'LUN', 'martedì': 'MAR', 'mercoledì': 'MER',
          'giovedì': 'GIO', 'venerdì': 'VEN', 'sabato': 'SAB'}
PRIMA_ORA = 8  # O.INIZIO '08h00' = 1a ora
# Ore a disposizione INVENTATE (assenti in EDT) per portare il docente a 18h totali (lezioni + DISPOS) su 5 giorni.
# Vanni ha 6h di lezione (MER4 GIO5 VEN1 VEN4 SAB1 SAB5): +12h DISPOS, 5o giorno = LUN.
DISPOS_INVENTATE = {'Vanni': {'LUN': [1, 2, 3], 'MER': [2, 3], 'GIO': [3, 4], 'VEN': [2, 3], 'SAB': [2, 3, 4]}}


def ore_occupate(durata: str, inizio: str) -> list[int]:
    """'2h00' alle '08h00' -> [1, 2]; '3h00' alle '10h00' -> [3, 4, 5]."""
    n = int(durata.split('h')[0])
    ora0 = int(inizio.split('h')[0]) - PRIMA_ORA + 1
    return list(range(ora0, ora0 + n))


def espandi_lezioni(cours: pd.DataFrame, avvisi: list) -> list[tuple]:
    """Una tupla (docente, classe|None, giorno, ora) per OGNI ora di ogni riga di EDT."""
    lezioni = []
    for r in cours.itertuples():
        if pd.isna(r.GIORNO) or pd.isna(r.INIZIO):
            avvisi.append(f"riga NUMERO={r.NUMERO} ({r.DOC_COGN}) senza giorno/ora: ignorata")
            continue
        giorno = GIORNI[r.GIORNO.strip().lower()]
        ore = ore_occupate(r.DURATA, r.INIZIO)
        docenti = [d.strip() for d in r.DOC_COGN.split(',')]
        # DISPOS: docente a disposizione, nessuna classe
        classi = [None] if pd.isna(r.CLASSE) else map_cours_class_to_id(r.CLASSE)
        if len(docenti) != len(classi):
            avvisi.append(f"riga NUMERO={r.NUMERO}: {len(docenti)} docenti ma {len(classi)} classi: ignorata")
            continue
        # co-docenza/accorpamento: i docenti sono in corrispondenza posizionale con le classi
        for d, c in zip(docenti, classi):
            for ora in ore:
                lezioni.append((format_teacher_name(d), c, giorno, ora, r.MAT_COD))
    return lezioni


def main(out_dir: str):
    cours = pd.read_csv(os.path.join(RADICE, 'EXP_COURS.csv'), sep=';', encoding='utf-8-sig', dtype=str).rename(columns={'O.INIZIO': 'INIZIO'})
    elenco = pd.read_csv(os.path.join(RADICE, 'elenco_classi_docenti_materie.tsv'), sep='\t', dtype=str)
    avvisi = []

    civ = extract_civics_teachers_mapping(elenco, cours)
    classi_civ = sorted({c for v in civ.values() for c in v['classes']})  # solo classi con docente CIV
    lezioni = espandi_lezioni(cours, avvisi)
    nore = max(l[3] for l in lezioni)

    # --- classes.csv: docente per classe/giorno/ora (solo ore con classe) ---
    orario = {c: {g: [''] * nore for g in GIORNI.values()} for c in classi_civ}
    for doc, cls, g, ora, _ in lezioni:
        if cls not in orario:
            continue
        cella = orario[cls][g]
        if cella[ora - 1] and cella[ora - 1] != doc:
            avvisi.append(f"conflitto {cls} {g} ora {ora}: {cella[ora - 1]} vs {doc} (tenuto il primo)")
            continue
        cella[ora - 1] = doc
    pd.DataFrame(
        [[c] + [';'.join(orario[c][g]) for g in GIORNI.values()] for c in classi_civ],
        columns=['CLASSE'] + [f'DOC {g}' for g in GIORNI.values()],
    ).to_csv(os.path.join(out_dir, 'classes.csv'), index=False)

    # --- civics_teachers.csv ---
    pd.DataFrame(
        [[d, ';'.join(sorted(v['classes']))] for d, v in sorted(civ.items())],
        columns=['DOCENTE', 'CLASSI'],
    ).to_csv(os.path.join(out_dir, 'civics_teachers.csv'), index=False)

    # --- availability.csv ---
    occupato, a_disp = defaultdict(set), defaultdict(set)
    for doc, cls, g, ora, _ in lezioni:
        if doc in civ:
            if cls is None:
                a_disp[doc].add((g, ora))
                continue
            if (g, ora) in occupato[doc]:
                avvisi.append(f"{doc} ha due classi contemporanee {g} ora {ora}")
            occupato[doc].add((g, ora))
    for d, giorni in DISPOS_INVENTATE.items():
        a_disp[d] |= {(g, o) for g, ore in giorni.items() for o in ore}
    libero = lambda d, k: k in a_disp[d] and k not in occupato[d]
    pd.DataFrame(
        [[d] + [';'.join('DISPOS' if libero(d, (g, o)) else 'NO' for o in range(1, nore + 1))
                for g in GIORNI.values()] for d in sorted(civ)],
        columns=['DOCENTE'] + list(GIORNI.values()),
    ).to_csv(os.path.join(out_dir, 'availability.csv'), index=False)

    for d in sorted(civ):
        ore_dispos = {k for k in a_disp[d] if k not in occupato[d]}
        giorni = {g for g, _ in ore_dispos | occupato[d]}
        print(f"{d}: {len(ore_dispos)}h DISPOS + {len(occupato[d])}h in classe = {len(ore_dispos) + len(occupato[d])}h su {len(giorni)} giorni")
    # classi senza nessuna ora coperta: col generatore sarebbero infattibili (loop infinito)
    for c in classi_civ:
        docs = [d for d, v in civ.items() if c in v['classes']]
        coperte = sum(1 for g in GIORNI.values() for o, doc in enumerate(orario[c][g], 1)
                      if doc and any(doc == d or libero(d, (g, o)) for d in docs))
        if coperte == 0:
            avvisi.append(f"INFATTIBILE: {c} ({'/'.join(docs)}) non ha nessuna ora coperta da docenti CIV")
    print(f"classi con CIV: {len(classi_civ)}/{len(elenco)} | docenti CIV: {sorted(civ)} | ore/giorno: {nore}")
    print(f"righe EDT: {len(cours)} -> ore-lezione espanse: {len(lezioni)}")
    for a in avvisi:
        print("AVVISO:", a)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else RADICE)
