# -------------------------------------------------------------------------
# Questo script utilizza OR-Tools CP-SAT per generare un calendario di sostituzioni
# di docenti di educazione civica, in modo da distribuire in maniera più omogenea
# le ore perse tra i docenti e le classi.
#
# **Obiettivi:**
# L'obiettivo è quello di creare un calendario di sostituzioni che, partendo dai docenti
# di educazione civica disponibili, copra le ore di lezione previste affinché ogni classe
# raggiunga le ore totali di educazione civica richieste (ore_tot_civics), distribuendo
# in modo equilibrato le ore perse per docente e minimizzando le deviazioni di vario tipo.
#
# **File di Input:**
#  - classes.csv: contiene l'elenco delle classi e gli orari settimanali dei docenti.
#  - civics_teachers.csv: elenco dei docenti di educazione civica e le classi a loro assegnate.
#  - availability.csv: disponibilità oraria dei docenti di educazione civica (DISPOS o meno).
#  - closures.csv: elenca i periodi di chiusura della scuola.
#
# **File di Output (generati nella cartella di output impostata in cartella_output):**
#  - calendar.csv: calendario risultante con data, giorno, ora, docente civics e docente sostituito.
#  - teachersLost.csv: statistiche per classe e docente, con percentuale di ore perse.
#  - orario_classi.xlsx: un file Excel per ogni classe, con una vista settimanale delle sostituzioni.
#  - orario_docenti.xlsx: un file Excel per ogni docente di educazione civica, con una vista settimanale.
#
# **Metodo:**
#  Le classi che non condividono docenti civics sono indipendenti (di norma un modello per docente):
#  ogni gruppo è un modello CP-SAT con vincoli duri (ore totali, max 1 ora a settimana per classe,
#  un docente in una sola classe alla volta) e la stessa fitness di calcola_fitness come obiettivo.
#
# -------------------------------------------------------------------------


import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import os
import logging
import re
import time
from dataclasses import dataclass
from ortools.sat.python import cp_model
from openpyxl.styles import PatternFill, Border, Side, Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.pagebreak import Break
from openpyxl.worksheet.properties import PageSetupProperties

# Configura il logger per informazioni sull'esecuzione
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _sanitize_output_path(path, default="CALENDARIO_GENERATO"):
    """Sanitizza il percorso di output per prevenire Path Traversal."""
    if not path:
        return default

    path = os.path.normpath(path)
    if os.path.isabs(path) or path.startswith(".."):
        path = os.path.basename(path)

    if not path or path in (".", ".."):
        return default
    return path

def _sanitize_for_logging(value):
    """Sanitizza le stringhe per prevenire Log Injection (CRLF)."""
    return str(value).replace('\n', '\\n').replace('\r', '\\r')

def _sanitize_sheet_name(name, default="Sheet"):
    """
    Sanitizza il nome del foglio Excel:
    - Rimuove caratteri non validi: \\ / * ? : [ ]
    - Trunca a 31 caratteri (limite massimo di Excel)
    """
    if not isinstance(name, str):
        name = str(name)
    # Rimuovi i caratteri non consentiti nei nomi dei fogli Excel
    safe_name = re.sub(r'[\\/*?:\[\]]', '', name).strip()
    # Trunca a 31 caratteri
    safe_name = safe_name[:31]
    return safe_name if safe_name else default

def _sanitize_for_excel(df):
    """
    Sanitizza le stringhe nel DataFrame per prevenire Excel formula injection.
    Aggiunge un apice singolo all'inizio di ogni cella che inizia con '=', '+', '-', o '@'.
    """
    if df.empty:
        return df

    def sanitize_val(val):
        if isinstance(val, str) and val.lstrip() and val.lstrip()[0] in ('=', '+', '-', '@'):
            return f"'{val}"
        return val

    # In pandas >= 2.1.0, applymap è deprecato in favore di map.
    # Usiamo map se disponibile, altrimenti applymap.
    try:
        return df.map(sanitize_val)
    except AttributeError:
        return df.applymap(sanitize_val)

def _get_excel_styles():
    """Restituisce gli stili predefiniti per i fogli Excel."""
    return {
        'header_fill': PatternFill(start_color='B8CCE4', end_color='B8CCE4', fill_type='solid'),
        'week_fill': PatternFill(start_color='E6E6FA', end_color='E6E6FA', fill_type='solid'),
        'thin_border': Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        ),
        'centered_alignment': Alignment(horizontal='center', vertical='center'),
        'bold_font': Font(bold=True)
    }

def _get_week_range(date):
    """Funzione per calcolare il range settimanale (lun-sab)"""
    start = date - timedelta(days=date.weekday())  # Lunedì
    end = start + timedelta(days=5)  # Sabato
    return f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"

_COLORE_SCURO = '1F3864'
_COLORE_BORDO = 'BFBFBF'
_NOMI_GIORNI = {'LUN': 'Lunedì', 'MAR': 'Martedì', 'MER': 'Mercoledì', 'GIO': 'Giovedì', 'VEN': 'Venerdì', 'SAB': 'Sabato'}

def _scrivi_titolo_foglio(ws, titolo, sottotitolo, n_colonne):
    """Scrive titolo (riga 1) e sottotitolo (riga 2) uniti su tutte le colonne del foglio"""
    for riga, testo, font, altezza in ((1, titolo, Font(bold=True, size=16, color=_COLORE_SCURO), 28),
                                       (2, sottotitolo, Font(italic=True, size=10, color='595959'), 18)):
        ws.merge_cells(start_row=riga, start_column=1, end_row=riga, end_column=n_colonne)
        ws.cell(row=riga, column=1, value=testo)
        ws.cell(row=riga, column=1).font = font
        ws.cell(row=riga, column=1).alignment = Alignment(horizontal='left', vertical='center')
        ws.row_dimensions[riga].height = altezza

def genera_orario_classi(calendario, classi_df, cartella_output):
    """Genera il file orario_classi.xlsx: un foglio per ogni classe, con le sostituzioni settimanali"""

    # Stili del foglio classe (tavolozza blu scuro / grigio, bordi sottili chiari, righe alternate)
    colore_scuro = _COLORE_SCURO
    colore_bordo = _COLORE_BORDO
    header_fill = PatternFill(start_color=colore_scuro, end_color=colore_scuro, fill_type='solid')
    banda_fill = PatternFill(start_color='EEF3FA', end_color='EEF3FA', fill_type='solid')
    lato = Side(style='thin', color=colore_bordo)
    bordo = Border(left=lato, right=lato, top=lato, bottom=lato)
    bordo_nuovo_mese = Border(left=lato, right=lato, bottom=lato, top=Side(style='medium', color=colore_scuro))
    centrato = Alignment(horizontal='center', vertical='center')
    a_sinistra = Alignment(horizontal='left', vertical='center', indent=1)
    font_header = Font(bold=True, color='FFFFFF')

    colonne = ['N.', 'Settimana', 'Data', 'Giorno', 'Ora', 'Docente di civica', 'Docente sostituito']
    colonne_a_sinistra = {6, 7}  # nomi dei docenti
    riga_header = 4

    writer_classi = pd.ExcelWriter(os.path.join(cartella_output, 'orario_classi.xlsx'), engine='openpyxl')

    # Pre-raggruppamento delle voci per classe per ottimizzare la ricerca
    calendario_per_classe = defaultdict(list)
    for entry in calendario:
        calendario_per_classe[entry['CLASSE']].append(entry)

    # Per ogni classe, estraiamo le entries corrispondenti e creiamo un foglio
    for nome_classe in classi_df['CLASSE']:
        class_entries = sorted(calendario_per_classe.get(nome_classe, []), key=lambda x: x['DATA'])

        class_data = []
        for numero, entry in enumerate(class_entries, start=1):
            class_data.append({
                'N.': numero,
                'Settimana': _get_week_range(entry['DATA']),
                'Data': entry['DATA'].date(),
                'Giorno': _NOMI_GIORNI.get(entry['GIORNO'], entry['GIORNO']),
                'Ora': entry['ORA'],
                'Docente di civica': entry['DOCENTE_CIVICS'],
                'Docente sostituito': entry['DOCENTE_SOSTITUITO']
            })

        if class_data:
            df = pd.DataFrame(class_data, columns=colonne)
            df = _sanitize_for_excel(df)
            safe_sheet_name = _sanitize_sheet_name(nome_classe, default="Classe")
            df.to_excel(writer_classi, sheet_name=safe_sheet_name, index=False, startrow=riga_header - 1)

            ws = writer_classi.sheets[safe_sheet_name]
            ultima_riga = riga_header + len(class_data)
            n_colonne = len(colonne)

            # Titolo e sottotitolo (docente/i, numero di ore, periodo coperto)
            docenti = sorted({e['DOCENTE_CIVICS'] for e in class_entries})
            _scrivi_titolo_foglio(
                ws, f"Educazione civica – Classe {nome_classe}",
                f"Docente di civica: {', '.join(docenti)}  ·  {len(class_entries)} ore  ·  "
                f"dal {class_entries[0]['DATA'].strftime('%d/%m/%Y')} al {class_entries[-1]['DATA'].strftime('%d/%m/%Y')}",
                n_colonne)
            ws.row_dimensions[riga_header].height = 24

            # Intestazione della tabella
            for col in range(1, n_colonne + 1):
                cell = ws.cell(row=riga_header, column=col)
                cell.fill = header_fill
                cell.font = font_header
                cell.border = bordo
                cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

            # Righe dati: righe alternate, data in formato italiano, bordo marcato al cambio di mese
            mese_precedente = None
            for indice, entry in enumerate(class_entries):
                riga = riga_header + 1 + indice
                nuovo_mese = mese_precedente is not None and entry['DATA'].month != mese_precedente
                mese_precedente = entry['DATA'].month
                for col in range(1, n_colonne + 1):
                    cell = ws.cell(row=riga, column=col)
                    cell.border = bordo_nuovo_mese if nuovo_mese else bordo
                    cell.alignment = a_sinistra if col in colonne_a_sinistra else centrato
                    if indice % 2 == 1:
                        cell.fill = banda_fill
                ws.cell(row=riga, column=3).number_format = 'DD/MM/YYYY'

            # Larghezza colonne in base al contenuto della tabella (titolo escluso)
            for col in range(1, n_colonne + 1):
                lunghezza = max(len(str(ws.cell(row=riga, column=col).value or ''))
                                for riga in range(riga_header, ultima_riga + 1))
                ws.column_dimensions[get_column_letter(col)].width = max(lunghezza + 4, 8)

            # Vista e stampa: intestazione fissa, filtri, niente griglia, A4 in larghezza con intestazione ripetuta
            ws.freeze_panes = ws.cell(row=riga_header + 1, column=1)
            ws.auto_filter.ref = f"A{riga_header}:{get_column_letter(n_colonne)}{ultima_riga}"
            ws.sheet_view.showGridLines = False
            ws.sheet_properties.tabColor = colore_scuro
            ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
            ws.page_setup.orientation = 'portrait'
            ws.page_setup.paperSize = ws.PAPERSIZE_A4
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 0
            ws.print_options.horizontalCentered = True
            ws.print_title_rows = f"{riga_header}:{riga_header}"
            ws.oddFooter.center.text = "Pagina &P di &N"

    writer_classi.close()

def genera_orario_docenti(calendario, docenti_civics_df, cartella_output):
    """Genera il file orario_docenti.xlsx: un foglio per ogni docente, con una griglia ore x giorni per ogni settimana"""

    colore_scuro = _COLORE_SCURO
    lato = Side(style='thin', color=_COLORE_BORDO)
    bordo = Border(left=lato, right=lato, top=lato, bottom=lato)
    settimana_fill = PatternFill(start_color=colore_scuro, end_color=colore_scuro, fill_type='solid')
    giorni_fill = PatternFill(start_color='D9E2F3', end_color='D9E2F3', fill_type='solid')
    ora_fill = PatternFill(start_color='EEF3FA', end_color='EEF3FA', fill_type='solid')
    lezione_fill = PatternFill(start_color='FFF2CC', end_color='FFF2CC', fill_type='solid')
    centrato_a_capo = Alignment(horizontal='center', vertical='center', wrap_text=True)

    writer_docenti = pd.ExcelWriter(os.path.join(cartella_output, 'orario_docenti.xlsx'), engine='openpyxl')

    giorni_tutti = ['LUN', 'MAR', 'MER', 'GIO', 'VEN', 'SAB']
    riga_iniziale = 4
    settimane_per_pagina = 3

    # Pre-raggruppamento delle voci per docente per ottimizzare la ricerca
    calendario_per_docente = defaultdict(list)
    for entry in calendario:
        calendario_per_docente[entry['DOCENTE_CIVICS']].append(entry)

    # Per ogni docente di civics creiamo un foglio con una griglia (ore x giorni) per ogni settimana
    for nome_docente in docenti_civics_df['DOCENTE']:
        docente_entries = calendario_per_docente.get(nome_docente, [])
        if not docente_entries:
            continue

        # Lezioni raggruppate per settimana (identificata dal lunedì, così l'ordine è cronologico)
        lezioni_per_settimana = defaultdict(dict)
        for entry in docente_entries:
            lunedi = entry['DATA'] - timedelta(days=entry['DATA'].weekday())
            lezioni_per_settimana[lunedi][(entry['GIORNO'], entry['ORA'])] = \
                f"{entry['CLASSE']}\n({entry['DOCENTE_SOSTITUITO']})"

        # Il sabato compare solo se il docente ha almeno una lezione quel giorno; le ore sono almeno 6
        giorni = [g for g in giorni_tutti if g != 'SAB' or any(e['GIORNO'] == 'SAB' for e in docente_entries)]
        n_ore = max(6, max(e['ORA'] for e in docente_entries))
        n_colonne = len(giorni) + 1

        # Costruzione delle righe: per ogni settimana titolo, intestazione dei giorni, ore e riga vuota
        righe = []
        tipi = []
        for numero, lunedi in enumerate(sorted(lezioni_per_settimana), start=1):
            righe.append([f"Settimana {numero}  ·  {_get_week_range(lunedi)}"] + [''] * len(giorni))
            tipi.append('settimana')
            righe.append(['Ora'] + [f"{_NOMI_GIORNI[g]}\n{(lunedi + timedelta(days=giorni_tutti.index(g))).strftime('%d/%m')}"
                                    for g in giorni])
            tipi.append('giorni')
            for ora in range(1, n_ore + 1):
                righe.append([ora] + [lezioni_per_settimana[lunedi].get((g, ora), '') for g in giorni])
                tipi.append('ora')
            righe.append([''] * n_colonne)
            tipi.append('vuota')

        df = pd.DataFrame(righe)
        df = _sanitize_for_excel(df)
        safe_sheet_name = _sanitize_sheet_name(nome_docente, default="Docente")
        df.to_excel(writer_docenti, sheet_name=safe_sheet_name, index=False, header=False, startrow=riga_iniziale - 1)

        ws = writer_docenti.sheets[safe_sheet_name]

        _scrivi_titolo_foglio(
            ws, f"Educazione civica – Docente {nome_docente}",
            f"{len(docente_entries)} ore  ·  {len({e['CLASSE'] for e in docente_entries})} classi  ·  "
            f"{len(lezioni_per_settimana)} settimane  ·  dal {min(e['DATA'] for e in docente_entries).strftime('%d/%m/%Y')} "
            f"al {max(e['DATA'] for e in docente_entries).strftime('%d/%m/%Y')}",
            n_colonne)

        # Formattazione per tipo di riga
        ws.column_dimensions['A'].width = 9
        for col in range(2, n_colonne + 1):
            ws.column_dimensions[get_column_letter(col)].width = 22
        for indice, tipo in enumerate(tipi):
            riga = riga_iniziale + indice
            if tipo == 'settimana':
                ws.merge_cells(start_row=riga, start_column=1, end_row=riga, end_column=n_colonne)
                cella = ws.cell(row=riga, column=1)
                cella.fill = settimana_fill
                cella.font = Font(bold=True, color='FFFFFF')
                cella.alignment = Alignment(horizontal='left', vertical='center', indent=1)
                ws.row_dimensions[riga].height = 22
            elif tipo == 'giorni':
                for col in range(1, n_colonne + 1):
                    cella = ws.cell(row=riga, column=col)
                    cella.fill = giorni_fill
                    cella.font = Font(bold=True)
                    cella.border = bordo
                    cella.alignment = centrato_a_capo
                ws.row_dimensions[riga].height = 32
            elif tipo == 'ora':
                for col in range(1, n_colonne + 1):
                    cella = ws.cell(row=riga, column=col)
                    cella.border = bordo
                    cella.alignment = centrato_a_capo
                    if col == 1:
                        cella.fill = ora_fill
                        cella.font = Font(bold=True)
                    elif cella.value:
                        cella.fill = lezione_fill
                ws.row_dimensions[riga].height = 32
            else:
                ws.row_dimensions[riga].height = 10

        # Vista e stampa: A4 in larghezza, 3 settimane per pagina (interruzione dopo la riga vuota)
        righe_per_settimana = n_ore + 3
        for numero_settimana in range(settimane_per_pagina, len(lezioni_per_settimana), settimane_per_pagina):
            ws.row_breaks.append(Break(id=riga_iniziale + numero_settimana * righe_per_settimana - 1))
        ws.sheet_view.showGridLines = False
        ws.sheet_properties.tabColor = colore_scuro
        ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
        ws.page_setup.orientation = 'portrait'
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.print_options.horizontalCentered = True
        ws.oddFooter.center.text = "Pagina &P di &N"

    writer_docenti.close()

def genera_file_excel(calendario, classi_df, docenti_civics_df, cartella_output):
    # Sanitize cartella_output to prevent path traversal
    cartella_output = _sanitize_output_path(cartella_output)

    # Questa funzione genera due file Excel:
    # 1. orario_classi.xlsx: un foglio per ogni classe, con le sostituzioni settimanali
    # 2. orario_docenti.xlsx: un foglio per ogni docente, con le ore settimanali su righe

    # Converte le date in datetime, se stringhe (ottimizzato con cache)
    date_cache = {}
    for entry in calendario:
        if isinstance(entry['DATA'], str):
            date_str = entry['DATA']
            if date_str not in date_cache:
                date_cache[date_str] = datetime.strptime(date_str, '%d/%m/%Y')
            entry['DATA'] = date_cache[date_str]

    genera_orario_classi(calendario, classi_df, cartella_output)
    genera_orario_docenti(calendario, docenti_civics_df, cartella_output)


# Scala dell'obiettivo intero CP-SAT (fitness * SCALA_OBIETTIVO) e risoluzione delle percentuali (decimi di punto)
SCALA_OBIETTIVO = 100_000
DECIMI = 10


def _formatta_durata(secondi):
    # Formatta una durata in secondi come "1h 05m 09s" / "5m 09s" / "9s"
    secondi = int(secondi)
    ore, resto = divmod(secondi, 3600)
    minuti, sec = divmod(resto, 60)
    if ore:
        return f"{ore}h {minuti:02d}m {sec:02d}s"
    if minuti:
        return f"{minuti}m {sec:02d}s"
    return f"{sec}s"


@dataclass
class CalendarioConfig:
    num_varianti: int = 1
    data_inizio_str: str = '02/12/2024'
    data_fine_str: str = '10/06/2025'
    ore_tot_civics: int = 27
    cartella_output: str = "CALENDARIO_GENERATO"
    tempo_max_secondi: float = 120  # tempo medio per modello CP-SAT (budget totale = tempo * n. modelli)
    num_cores: int = 4
    allow_teacher_replace_self: bool = True


class CalendarioGenerator:
    # Classe principale che gestisce caricamento dati, risoluzione CP-SAT e salvataggio dei risultati

    def __init__(self, config: CalendarioConfig):
        # Inizializzazione dei parametri
        self.config = config
        self.num_varianti = config.num_varianti
        self.data_inizio_str = config.data_inizio_str
        self.data_fine_str = config.data_fine_str
        self.ore_tot_civics = config.ore_tot_civics
        # Sanitize cartella_output to prevent path traversal
        self.cartella_output = _sanitize_output_path(config.cartella_output)
        self.tempo_max_secondi = config.tempo_max_secondi
        self.num_cores = config.num_cores
        self.allow_teacher_replace_self = config.allow_teacher_replace_self

        # Stampa parametri di inizializzazione
        print("Parametri iniziali:")
        print(f"num_varianti = {self.num_varianti}")
        print(f"data_inizio_str = {self.data_inizio_str}")
        print(f"data_fine_str = {self.data_fine_str}")
        print(f"ore_tot_civics = {self.ore_tot_civics}")
        print(f"cartella_output = {self.cartella_output}")
        print(f"tempo_max_secondi = {self.tempo_max_secondi}")
        print(f"num_cores = {self.num_cores}")
        print(f"allow_teacher_replace_self = {self.allow_teacher_replace_self}")

        # Caricamento dati e inizializzazione variabili
        self.load_data()
        self.initialize_variables()

    def load_data(self):
        # Caricamento dati da file CSV
        logging.info("Caricamento dei file CSV...")
        try:
            self.classi_df = pd.read_csv('classes.csv')
            self.docenti_civics_df = pd.read_csv('civics_teachers.csv')
            self.disponibilita_df = pd.read_csv('availability.csv')
            self.chiusure_df = pd.read_csv('closures.csv')
            # Inizializza la lista delle classi dal DataFrame
            self.classi_list = list(self.classi_df['CLASSE'])
        except FileNotFoundError as e:
            logging.error(f"Errore: File non trovato - {_sanitize_for_logging(e.filename)}")
            raise SystemExit(1)
        except pd.errors.EmptyDataError as e:
            logging.error(f"Errore: Il file CSV è vuoto - {_sanitize_for_logging(e)}")
            raise SystemExit(1)
        except pd.errors.ParserError as e:
            logging.error(f"Errore: Errore nel parsing del file CSV - {_sanitize_for_logging(e)}")
            raise SystemExit(1)
        except Exception as e:
            logging.error(f"Errore imprevisto durante il caricamento dei dati: {_sanitize_for_logging(e)}")
            raise SystemExit(1)

    def initialize_variables(self):
        logging.info("Inizializzazione delle variabili...")
        try:
            self.data_inizio = datetime.strptime(self.data_inizio_str, '%d/%m/%Y')
            self.data_fine = datetime.strptime(self.data_fine_str, '%d/%m/%Y')
        except ValueError as e:
            logging.error(f"Errore: Formato data non valido per data_inizio o data_fine - {_sanitize_for_logging(e)}")
            raise SystemExit(1)
        self.giorni_settimana = ['LUN', 'MAR', 'MER', 'GIO', 'VEN', 'SAB']
        self.mappa_giorni = {0: 'LUN', 1: 'MAR', 2: 'MER', 3: 'GIO', 4: 'VEN', 5: 'SAB', 6: 'DOM'}

        self._init_date_scolastiche()
        self._parse_orari_classi()
        self._parse_disponibilita_docenti()
        self._parse_assegnazioni_docenti()
        self._identifica_docenti_civics_organico()
        self._genera_slot_disponibili()
        self._precalcola_lookups()

        self._log_struttura_dati_e_fattibilita()

    def _log_struttura_dati_e_fattibilita(self):
        # Riepilogo della struttura dati e controllo di fattibilità (condizione necessaria, non sufficiente)
        settimane_utili = len({d.isocalendar()[1] for d in self.date_scolastiche})
        n_classi = len(self.classi_list)
        docenti = list(self.docenti_civics_classi.keys())
        logging.info(
            f"Struttura dati: {n_classi} classi, {len(docenti)} docenti civics ({', '.join(docenti)}), "
            f"{len(self.slot_disponibili)} slot disponibili, {settimane_utili} settimane utili dopo le chiusure "
            f"({len(self.date_scolastiche)} giorni scolastici), {self.ore_tot_civics} ore richieste per classe "
            f"({self.ore_tot_civics * n_classi} totali)")

        settimane_per_classe = {c: len({s['SETTIMANA'] for s in self.slots_by_class[c]}) for c in self.classi_list}
        classi_critiche = [c for c, n in settimane_per_classe.items() if n < self.ore_tot_civics]
        if classi_critiche:
            logging.error(
                f"Fattibilità: NON OK. {self.ore_tot_civics} ore richieste ma almeno 1 ora a settimana per classe "
                f"copre al massimo {min(settimane_per_classe.values())} settimane (classi critiche: "
                f"{_sanitize_for_logging(', '.join(classi_critiche))}). Riduci ore_tot_civics o le chiusure.")
            raise SystemExit(1)
        if settimane_per_classe:
            minimo = min(settimane_per_classe.values())
            logging.info(
                f"Fattibilità: OK sul numero di settimane (minimo {minimo} settimane con slot per classe, "
                f"margine {minimo - self.ore_tot_civics}). Non verifica i conflitti tra docenti: "
                f"l'esito si vede dal solver CP-SAT.")

    def _init_date_scolastiche(self):
        # Creazione della lista di date scolastiche escludendo i giorni di chiusura
        logging.info("Creazione della lista delle date scolastiche escludendo le chiusure...")
        chiusure = set()
        for _, row in self.chiusure_df.iterrows():
            try:
                inizio = datetime.strptime(row['INIZIO'], '%d/%m/%Y')
                fine = datetime.strptime(row['FINE'], '%d/%m/%Y')
                diff_days = (fine - inizio).days
                if diff_days < 0:
                    logging.warning(f"Ignorata chiusura con data fine precedente a data inizio: INIZIO={_sanitize_for_logging(row.get('INIZIO'))}, FINE={_sanitize_for_logging(row.get('FINE'))}")
                    continue
                if diff_days > 366:
                    logging.warning(f"Ignorata chiusura con intervallo troppo lungo (> 366 giorni): INIZIO={_sanitize_for_logging(row.get('INIZIO'))}, FINE={_sanitize_for_logging(row.get('FINE'))}")
                    continue
                chiusure.update([inizio + timedelta(days=i) for i in range(diff_days + 1)])
            except ValueError as e:
                logging.warning(f"Ignorata chiusura con date non valide: INIZIO={_sanitize_for_logging(row.get('INIZIO'))}, FINE={_sanitize_for_logging(row.get('FINE'))} - {_sanitize_for_logging(e)}")
                continue

        self.date_scolastiche = []
        data_corrente = self.data_inizio
        while data_corrente <= self.data_fine:
            if data_corrente not in chiusure and data_corrente.weekday() < 6:
                self.date_scolastiche.append(data_corrente)
            data_corrente += timedelta(days=1)

        logging.info(f"Numero totale di giorni scolastici: {len(self.date_scolastiche)}")

    def _parse_orari_classi(self):
        # Parsing orari delle classi
        logging.info("Parsing degli orari delle classi...")
        self.orari_classi = {}
        for _, row in self.classi_df.iterrows():
            nome_classe = row['CLASSE']
            self.orari_classi[nome_classe] = {}
            for giorno in self.giorni_settimana:
                colonna_doc = f'DOC {giorno}'
                lista_docenti = row[colonna_doc].split(';')
                self.orari_classi[nome_classe][giorno] = lista_docenti

    def _parse_disponibilita_docenti(self):
        # Parsing disponibilità docenti civics
        logging.info("Parsing della disponibilità dei docenti di educazione civica...")
        self.disponibilita_civics = {}
        for _, row in self.disponibilita_df.iterrows():
            nome_docente = row['DOCENTE']
            self.disponibilita_civics[nome_docente] = {}
            for giorno in self.giorni_settimana:
                disponibilita_stringa = row[giorno]
                disponibilita_lista = disponibilita_stringa.split(';')
                disponibilita_bool = [x == 'DISPOS' for x in disponibilita_lista]
                self.disponibilita_civics[nome_docente][giorno] = disponibilita_bool

    def _parse_assegnazioni_docenti(self):
        # Parsing assegnazioni docenti civics
        logging.info("Parsing delle assegnazioni dei docenti di educazione civica...")
        self.docenti_civics_classi = {}
        for _, row in self.docenti_civics_df.iterrows():
            nome_docente = row['DOCENTE']
            lista_classi = row['CLASSI'].split(';')
            self.docenti_civics_classi[nome_docente] = lista_classi

    def _identifica_docenti_civics_organico(self):
        # Identificazione docenti di civics anche in altre materie
        logging.info("Identificazione dei docenti di civics che insegnano altre materie nelle classi...")
        self.docenti_civics_organico = defaultdict(set)
        for _, row in self.classi_df.iterrows():
            nome_classe = row['CLASSE']
            for giorno in self.giorni_settimana:
                colonna_doc = f'DOC {giorno}'
                lista_docenti = row[colonna_doc].split(';')
                for docente in lista_docenti:
                    if docente in self.docenti_civics_classi:
                        self.docenti_civics_organico[nome_classe].add(docente)

    def _genera_slot_disponibili(self):
        # Generazione degli slot disponibili (classe, data, giorno, ora, docente_sostituito)
        logging.info("Generazione degli slot disponibili...")
        self.slot_disponibili = []
        for nome_classe in self.classi_list:
            for data in self.date_scolastiche:
                nome_giorno = self.mappa_giorni[data.weekday()]
                if nome_giorno in self.giorni_settimana:
                    orario_classe = self.orari_classi[nome_classe][nome_giorno]
                    for ora_idx, docente_in_classe in enumerate(orario_classe):
                        if docente_in_classe != '':
                            slot = {
                                'CLASSE': nome_classe,
                                'DATA': data,
                                'GIORNO': nome_giorno,
                                'ORA': ora_idx + 1,
                                'DOCENTE_SOSTITUITO': docente_in_classe,
                                'KEY': f"{nome_classe}_{data.strftime('%Y%m%d')}_{ora_idx + 1}",
                                'SETTIMANA': data.isocalendar()[1]
                            }
                            self.slot_disponibili.append(slot)

    def _precalcola_lookups(self):
        # Pre-calcola lookups per ottimizzare le prestazioni
        self.slots_by_class = defaultdict(list)
        self.slots_by_key = {}
        self.ore_totali_docente_per_classe = defaultdict(lambda: defaultdict(int))
        # self.classi_list is already initialized in load_data
        for slot in self.slot_disponibili:
            self.slots_by_class[slot['CLASSE']].append(slot)
            self.slots_by_key[slot['KEY']] = slot
            self.ore_totali_docente_per_classe[slot['CLASSE']][slot['DOCENTE_SOSTITUITO']] += 1

        # Mappa inversa per trovare i docenti di civics per ogni classe
        self.docenti_per_classe = defaultdict(list)
        for docente_civics, classi in self.docenti_civics_classi.items():
            for nome_classe in classi:
                self.docenti_per_classe[nome_classe].append(docente_civics)

        # Pre-calcola P per ogni classe per ottimizzare le prestazioni in _calcola_penalita_classe
        self.P_per_classe = {}
        for classe in self.classi_list:
            ore_totali_docente = self.ore_totali_docente_per_classe[classe]
            total_teaching_hours = sum(ore_totali_docente.values())
            self.P_per_classe[classe] = (self.ore_tot_civics / total_teaching_hours) * 100 if total_teaching_hours > 0 else 0

    def _componenti(self):
        # Gruppi di classi indipendenti: classi che condividono (anche indirettamente) un docente civics
        padre = {c: c for c in self.classi_list}

        def radice(c):
            while padre[c] != c:
                c = padre[c]
            return c

        for classi in self.docenti_civics_classi.values():
            for c in classi[1:]:
                padre[radice(c)] = radice(classi[0])
        gruppi = defaultdict(list)
        for c in self.classi_list:
            gruppi[radice(c)].append(c)
        return list(gruppi.values())

    def risolvi(self):
        # Risolve un modello CP-SAT per ogni gruppo indipendente di classi e unisce le soluzioni
        # Il tempo è un budget unico (tempo_max_secondi * n. modelli): quello non usato da un modello che
        # dimostra l'ottimo viene ripartito in parti uguali tra i modelli rimasti
        individuo = {}
        componenti = self._componenti()
        residuo = self.tempo_max_secondi * len(componenti)
        for i, classi in enumerate(componenti):
            inizio = time.monotonic()
            individuo.update(self._risolvi_componente(classi, residuo / (len(componenti) - i)))
            residuo -= time.monotonic() - inizio
        return individuo

    def _risolvi_componente(self, classi, tempo_max_secondi):
        # Modello CP-SAT: x[slot, docente] = il docente civics copre lo slot. Obiettivo = fitness * SCALA_OBIETTIVO
        # (penalità a gradini e penalità sulle percentuali alte come tabelle sulle ore perse per docente,
        # varianza come termine quadratico intero sulle percentuali in decimi di punto)
        inizio = time.time()
        m = cp_model.CpModel()
        x = {}
        occupati = defaultdict(list)  # (data, ora, docente) -> variabili: un docente in una sola classe alla volta
        costo = []
        for classe in classi:
            sel = {}  # chiave slot -> 1 se lo slot è usato da un docente civics
            for s in self.slots_by_class[classe]:
                vs = []
                for d in self._docenti_disponibili(s):
                    v = x[s['KEY'], d] = m.NewBoolVar(f"x_{s['KEY']}_{d}")
                    occupati[s['DATA'], s['ORA'], d].append(v)
                    vs.append(v)
                sel[s['KEY']] = sum(vs)
            m.Add(sum(sel.values()) == self.ore_tot_civics)
            per_settimana = defaultdict(list)
            for s in self.slots_by_class[classe]:
                per_settimana[s['SETTIMANA']].append(sel[s['KEY']])
            for expr in per_settimana.values():
                m.Add(sum(expr) <= 1)

            percentuali = []
            for docente, ore_totali in self.ore_totali_docente_per_classe[classe].items():
                max_perse = min(ore_totali, self.ore_tot_civics)
                perse = m.NewIntVar(0, max_perse, f"perse_{classe}_{docente}")
                m.Add(perse == sum(sel[s['KEY']] for s in self.slots_by_class[classe]
                                   if s['DOCENTE_SOSTITUITO'] == docente))
                tab = [self._penalita_docente(classe, docente, l) for l in range(max_perse + 1)]
                costo_l = [round((p + mp) * SCALA_OBIETTIVO) for p, mp, _ in tab]
                pc_l = [round(pct * DECIMI) for _, _, pct in tab]
                c = m.NewIntVar(min(costo_l), max(costo_l), "")
                pc = m.NewIntVar(min(pc_l), max(pc_l), "")
                sq = m.NewIntVar(min(p * p for p in pc_l), max(p * p for p in pc_l), "")
                m.AddElement(perse, costo_l, c)
                m.AddElement(perse, pc_l, pc)
                m.AddElement(perse, [p * p for p in pc_l], sq)
                costo.append(c)
                percentuali.append((pc, sq, max(pc_l)))

            # n² * varianza * DECIMI² = n * Σ pc² - (Σ pc)²
            n = len(percentuali)
            max_somma = sum(p[2] for p in percentuali)
            somma = m.NewIntVar(0, max_somma, "")
            m.Add(somma == sum(p[0] for p in percentuali))
            somma2 = m.NewIntVar(0, max_somma ** 2, "")
            m.AddMultiplicationEquality(somma2, [somma, somma])
            coef = round(5 * SCALA_OBIETTIVO / (n * n * DECIMI * DECIMI))
            varianza = m.NewIntVar(0, n * sum(p[2] ** 2 for p in percentuali), "")  # >= 0: stringe il limite inferiore
            m.Add(varianza == n * sum(p[1] for p in percentuali) - somma2)
            costo.append(coef * varianza)

        for vs in occupati.values():
            m.AddAtMostOne(vs)
        m.Minimize(sum(costo))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = tempo_max_secondi
        solver.parameters.num_workers = self.num_cores
        stato = solver.Solve(m)
        nome = ', '.join(_sanitize_for_logging(c) for c in classi)
        if stato not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            logging.error(f"Nessuna soluzione per le classi {nome} ({solver.StatusName(stato)}): "
                          f"vincoli incompatibili o tempo_max_secondi troppo basso.")
            raise SystemExit(1)
        logging.info(f"Classi {nome}: {solver.StatusName(stato)}, fitness {solver.ObjectiveValue() / SCALA_OBIETTIVO:.1f} "
                     f"(limite inferiore {solver.BestObjectiveBound() / SCALA_OBIETTIVO:.1f}) in {_formatta_durata(time.time() - inizio)}")
        return {key: d for (key, d), v in x.items() if solver.Value(v)}

    def genera_calendario(self):
        # Risolve il problema con CP-SAT e salva i risultati
        inizio_esecuzione = time.time()
        logging.info("Risoluzione con CP-SAT...")
        individuo = self.risolvi()
        if not self.verifica_vincoli(individuo):
            logging.error("La soluzione CP-SAT non rispetta i vincoli.")
            raise SystemExit(1)
        calendario = self.create_calendario(individuo)

        os.makedirs(self.cartella_output, exist_ok=True)

        logging.info("Salvataggio del calendario finale in calendar.csv...")
        calendario_df = pd.DataFrame(calendario)
        calendario_df = _sanitize_for_excel(calendario_df)
        calendario_df.to_csv(os.path.join(self.cartella_output, 'calendar.csv'), index=False)

        logging.info("Salvataggio delle statistiche finali in teachersLost.csv...")
        statistiche_classi = self.calcola_statistiche(calendario)
        statistiche_df = pd.DataFrame(statistiche_classi)
        statistiche_df = _sanitize_for_excel(statistiche_df)
        statistiche_df.to_csv(os.path.join(self.cartella_output, 'teachersLost.csv'), index=False)

        logging.info("Generazione dei file Excel finali...")
        genera_file_excel(calendario, self.classi_df, self.docenti_civics_df, self.cartella_output)
        logging.info("File Excel finali generati con successo!")

        logging.info("===== Riepilogo finale =====")
        logging.info(f"Fitness finale: {self.calcola_fitness(individuo):.1f} - tempo totale: {_formatta_durata(time.time() - inizio_esecuzione)}")
        self._log_controllo_coerenza(individuo)

    def _log_controllo_coerenza(self, individuo):
        # Controllo finale: ore per classe, max 1 ora a settimana per classe, nessun docente in due classi insieme
        ore_per_classe = defaultdict(int)
        settimane_viste = set()
        occupati = set()
        settimane_doppie = doppi_impegni = 0
        for slot_key, docente_civics in individuo.items():
            slot_info = self.slots_by_key[slot_key]
            ore_per_classe[slot_info['CLASSE']] += 1
            chiave_settimana = (slot_info['CLASSE'], slot_info['SETTIMANA'])
            settimane_doppie += chiave_settimana in settimane_viste
            settimane_viste.add(chiave_settimana)
            chiave_occupato = (slot_info['DATA'], slot_info['ORA'], docente_civics)
            doppi_impegni += chiave_occupato in occupati
            occupati.add(chiave_occupato)
        classi_errate = [c for c in self.classi_list if ore_per_classe[c] != self.ore_tot_civics]
        esito = "OK" if not (classi_errate or settimane_doppie or doppi_impegni) else "ERRORE"
        logging.info(f"Controllo coerenza: {esito} - classi con ore != {self.ore_tot_civics}: {len(classi_errate)}, "
                     f"classi con più ore nella stessa settimana: {settimane_doppie}, doppi impegni docenti: {doppi_impegni}")

    def calcola_statistiche(self, calendario):
        # Calcola le statistiche per classe e docente (ore perse, totali e percentuale)
        statistiche_classi = []

        # Raggruppa le voci del calendario per classe per evitare scansioni O(M) nel loop
        entries_by_class = defaultdict(list)
        for entry in calendario:
            entries_by_class[entry['CLASSE']].append(entry)

        for classe in self.classi_list:
            # Utilizza il lookup pre-calcolato invece della scansione O(N)
            ore_perse_docente = defaultdict(int)
            ore_totali_docente = self.ore_totali_docente_per_classe[classe]

            # Calcolo delle ore perse assegnate ad un docente di civics utilizzando il raggruppamento
            for entry in entries_by_class[classe]:
                docente = entry['DOCENTE_SOSTITUITO']
                ore_perse_docente[docente] += 1

            # Calcolo percentuali e costruzione del dict da aggiungere al DataFrame
            for docente in ore_totali_docente:
                ore_perse = ore_perse_docente.get(docente, 0)
                ore_totali = ore_totali_docente[docente]
                percentuale = (ore_perse / ore_totali * 100) if ore_totali > 0 else 0
                statistiche_classi.append({
                    'CLASSE': classe,
                    'DOCENTE': docente,
                    'ORE_PERSE': ore_perse,
                    'ORE_TOTALI': ore_totali,
                    'PERCENTUALE_ORE_PERSE': f'{percentuale:.2f}'
                })
        return statistiche_classi

    def create_calendario(self, individuo):
        # Crea la lista di dizionari rappresentante il calendario dall'individuo
        calendario = []
        for slot_key, docente_civics in individuo.items():
            slot_info = self.slots_by_key[slot_key]
            calendario.append({
                'CLASSE': slot_info['CLASSE'],
                'DATA': slot_info['DATA'].strftime('%d/%m/%Y'),
                'GIORNO': slot_info['GIORNO'],
                'ORA': slot_info['ORA'],
                'DOCENTE_CIVICS': docente_civics,
                'DOCENTE_SOSTITUITO': slot_info['DOCENTE_SOSTITUITO']
            })
        return calendario

    def verifica_vincoli(self, individuo):
        # Verifica se l'individuo rispetta i vincoli (ore tot per classe, max 1 ora a settimana per classe,
        # un docente in una sola classe alla volta)
        ore_per_classe = defaultdict(int)
        ore_settimanali_classe = defaultdict(lambda: defaultdict(int))
        occupati = set()

        for slot_key, docente_civics in individuo.items():
            slot_info = self.slots_by_key[slot_key]
            nome_classe = slot_info['CLASSE']
            data = slot_info['DATA']
            settimana = slot_info['SETTIMANA']
            ore_per_classe[nome_classe] += 1
            ore_settimanali_classe[nome_classe][settimana] += 1

            if ore_settimanali_classe[nome_classe][settimana] > 1:
                return False

            # Un docente non può essere in due classi alla stessa data e ora
            chiave_occupato = (data, slot_info['ORA'], docente_civics)
            if chiave_occupato in occupati:
                return False
            occupati.add(chiave_occupato)

        # Tutte le classi devono avere esattamente ore_tot_civics ore
        if not all(ore_per_classe[nome_classe] == self.ore_tot_civics
                   for nome_classe in self.classi_list):
            return False

        return True

    def _calcola_deviazione_totale(self, ore_settimanali_classe):
        total_deviation = 0
        for classe in self.classi_list:
            ore_per_settimana = ore_settimanali_classe.get(classe, {})
            total_deviation += sum(max(0, ore - 1) for ore in ore_per_settimana.values())
        return total_deviation

    def _penalita_docente(self, classe, docente, ore_perse):
        # Penalità a gradini e penalità sulle percentuali alte per un docente sostituito in una classe.
        # Ritorna (penalità a gradini, penalità percentuale alta, percentuale di ore perse)
        medium_intensity_penalty = 5
        high_intensity_penalty = 10
        low_intensity_penalty = 1

        # Penalità per docenti civics
        medium_intensity_penalty_civics_teacher = 10
        high_intensity_penalty_civics_teacher = 20
        low_intensity_penalty_civics_teacher = 0.5

        P = self.P_per_classe.get(classe, 0)
        ore_totali = self.ore_totali_docente_per_classe[classe][docente]
        percentuale_perse = (ore_perse / ore_totali) * 100 if ore_totali > 0 else 0
        is_organico = docente in self.docenti_civics_organico[classe]

        penalita = 0
        # Penalità in base alla percentuale di ore perse
        if percentuale_perse > 2 * P:
            penalita = high_intensity_penalty_civics_teacher if is_organico else high_intensity_penalty
        elif percentuale_perse > P:
            penalita = medium_intensity_penalty_civics_teacher if is_organico else medium_intensity_penalty
        elif percentuale_perse < 0.3 * P:
            penalita = low_intensity_penalty_civics_teacher if is_organico else low_intensity_penalty

        # Penalità per percentuali molto alte
        penalita_alta = (percentuale_perse - 5) * 10 if is_organico and percentuale_perse > 5 else 0
        return penalita, penalita_alta, percentuale_perse

    def _calcola_penalita_classe(self, classe, ore_perse_docente):
        penalties_total = 0
        max_percentage_penalty = 0
        percentuali = []
        for docente in self.ore_totali_docente_per_classe[classe]:
            p, mp, percentuale = self._penalita_docente(classe, docente, ore_perse_docente.get(docente, 0))
            penalties_total += p
            max_percentage_penalty += mp
            percentuali.append(percentuale)

        variance_total = 0
        if percentuali:
            n = len(percentuali)
            mean = sum(percentuali) / n
            variance_total = sum((x - mean) ** 2 for x in percentuali) / n

        return variance_total, max_percentage_penalty, penalties_total

    def calcola_fitness(self, individuo):
        # Calcola la fitness di un individuo, utilizzando diverse metriche
        # Minore è la fitness, migliore è l'individuo
        ore_settimanali_classe = defaultdict(lambda: defaultdict(int))

        # Pre-calcola le ore perse per ogni classe e docente in un unico passaggio sull'individuo
        # Questo evita scansioni multiple di individuo nel loop delle classi
        ore_perse_per_classe_docente = defaultdict(lambda: defaultdict(int))

        for slot_key in individuo:
            slot_info = self.slots_by_key[slot_key]
            nome_classe = slot_info['CLASSE']
            data = slot_info['DATA']
            settimana = slot_info['SETTIMANA']
            ore_settimanali_classe[nome_classe][settimana] += 1

            docente_sostituito = slot_info['DOCENTE_SOSTITUITO']
            ore_perse_per_classe_docente[nome_classe][docente_sostituito] += 1

        total_deviation = self._calcola_deviazione_totale(ore_settimanali_classe)

        variance_total = 0
        max_percentage_penalty = 0
        penalties_total = 0

        for classe in self.classi_list:
            ore_perse_docente = ore_perse_per_classe_docente[classe]
            v_tot, max_p, p_tot = self._calcola_penalita_classe(classe, ore_perse_docente)
            variance_total += v_tot
            max_percentage_penalty += max_p
            penalties_total += p_tot

        total_fitness = total_deviation * 10 + variance_total * 5 + max_percentage_penalty + penalties_total
        return total_fitness

    def _docenti_disponibili(self, slot):
        # Docenti civics che possono coprire lo slot (disponibilità oraria), senza controllare i conflitti
        nome_classe = slot['CLASSE']
        nome_giorno = slot['GIORNO']
        ora = slot['ORA']
        docenti_possibili = []
        for docente_civics in self.docenti_per_classe[nome_classe]:
            disponibile = False
            if docente_civics in self.docenti_civics_organico[nome_classe]:
                if self.allow_teacher_replace_self and docente_civics == slot['DOCENTE_SOSTITUITO']:
                    disponibile = True
            else:
                if len(self.disponibilita_civics[docente_civics][nome_giorno]) >= ora and \
                   self.disponibilita_civics[docente_civics][nome_giorno][ora - 1]:
                    disponibile = True

            if disponibile:
                docenti_possibili.append(docente_civics)
        return docenti_possibili



if __name__ == "__main__":
    config = CalendarioConfig(
        num_varianti=1,
        data_inizio_str='01/10/2026',
        data_fine_str='10/06/2027',
        ore_tot_civics=31,
        cartella_output="CALENDARIO_GENERATO",
        tempo_max_secondi=120,
        num_cores=15,
        allow_teacher_replace_self=True
    )
    generator = CalendarioGenerator(config)
    generator.genera_calendario()
