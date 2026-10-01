"""
Modulo di utilità per la conversione dei dati da EDT (EXP_COURS.csv)
e ALDO (elenco_classi_docenti_materie.tsv).
"""

import os
import re
import pandas as pd


def clean_str(s: str) -> str:
    """Rimuove caratteri non alfabetici e converte in minuscolo per il matching."""
    if not isinstance(s, str):
        return ""
    return re.sub(r'[^a-zA-Z]', '', s).lower()


def format_teacher_name(name: str) -> str:
    """
    Formatta il cognome del docente in Title Case mantenendo apostrofi e spazi.
    Esempi:
    - 'FOMMEI' -> 'Fommei'
    - 'DELLA MONICA' -> 'Della Monica'
    - 'D\'ELIA' -> 'D\'Elia'
    - 'LA MANTIA' -> 'La Mantia'
    """
    if not isinstance(name, str) or not name.strip():
        return ""
    
    parts = name.split()
    formatted_parts = []
    for part in parts:
        if "'" in part:
            subparts = part.split("'")
            formatted_parts.append("'".join(p.capitalize() for p in subparts))
        else:
            formatted_parts.append(part.capitalize())
    return " ".join(formatted_parts)


def map_cours_class_to_id(c_str: str) -> list[str]:
    """
    Mappa i codici classe di EDT (EXP_COURS.csv) agli ID classe di ALDO (elenco_classi_docenti_materie.tsv).
    Esempi:
    - 'LC 1A' -> ['1ALC']
    - 'A1 LS' -> ['1ALS']
    - 'C1 LS' -> ['1C']
    - 'A1 LS, B1 LS, C1 LS' -> ['1ALS', '1BLS', '1C']
    """
    if not isinstance(c_str, str) or not c_str.strip():
        return []
    
    result = []
    for raw in c_str.split(','):
        c = raw.strip()
        if not c:
            continue
        if c.startswith('LC '):
            parts = c.split(' ')
            if len(parts) >= 2 and len(parts[1]) >= 2:
                anno = parts[1][0]
                sez = parts[1][1]
                result.append(f"{anno}{sez}LC")
            else:
                result.append(c)
        elif ' LS' in c:
            parts = c.replace(' LS', '').strip()
            if len(parts) >= 2:
                sez = parts[0]
                anno = parts[1]
                if sez in ['A', 'B']:
                    result.append(f"{anno}{sez}LS")
                else:
                    result.append(f"{anno}{sez}")
            else:
                result.append(c)
        else:
            result.append(c)
    return result


def extract_civics_teachers_mapping(df_elenco: pd.DataFrame, df_cours: pd.DataFrame) -> dict:
    """
    Estrae il mapping dai docenti CIV (email in elenco_classi) ai loro nomi formattati
    e alle classi loro assegnate.
    Ritorna un dizionario:
    {
        'Fommei': {'raw_name': 'FOMMEI', 'classes': ['3ALC', '3BLC', ...]},
        ...
    }
    """
    cours_docenti = df_cours[['DOC_COGN', 'DOC_NOME']].dropna().drop_duplicates()
    cours_docenti['clean_cogn'] = cours_docenti['DOC_COGN'].apply(clean_str)

    civ_assignments = {}

    for _, row in df_elenco.iterrows():
        cls_id = str(row['ID']).strip()
        civ_email = row.get('CIV')
        if pd.isna(civ_email) or not str(civ_email).strip():
            continue

        prefix = str(civ_email).split('@')[0]
        cogn = prefix.split('.')[0] if '.' in prefix else prefix
        clean_c = clean_str(cogn)
        
        m = cours_docenti[cours_docenti['clean_cogn'] == clean_c]
        if not m.empty:
            raw_cogn = m.iloc[0]['DOC_COGN']
        else:
            raw_cogn = cogn.upper()

        fmt_cogn = format_teacher_name(raw_cogn)
        if fmt_cogn not in civ_assignments:
            civ_assignments[fmt_cogn] = {
                'raw_name': raw_cogn,
                'classes': []
            }
        civ_assignments[fmt_cogn]['classes'].append(cls_id)

    return civ_assignments
