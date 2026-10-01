# -------------------------------------------------------------------------
# Questo script utilizza un algoritmo genetico per generare un calendario di sostituzioni
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
# **Organizzazione dell'Output:**
#  Oltre ai file finali, ad ogni generazione dell'algoritmo genetico verrà creata una cartella
#  denominata "generation_X" (dove X è il numero della generazione), contenente:
#   - calendar.csv: il calendario di quella generazione
#   - teachersLost.csv: le statistiche per quella generazione
#   - orario_classi.xlsx e orario_docenti.xlsx: i file Excel con la pianificazione per classi e docenti
#
# In questo modo potremo monitorare il progresso dell'algoritmo e verificare come le soluzioni
# si evolvono nel tempo.
#
# -------------------------------------------------------------------------


import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import os
import random
import multiprocessing
import logging
import re
import time
from dataclasses import dataclass
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
    num_generazioni: int = 200
    early_stopping_n: int = 20
    popolazione_size: int = 200
    probabilita_mutazione: float = 0.2
    probabilita_crossover: float = 0.8
    elitismo_rate: float = 0.01
    num_cores: int = 4
    allow_teacher_replace_self: bool = True
    save_interval: int = 50
    log_ogni_n_generazioni: int = 25


class CalendarioGenerator:
    # Classe principale che gestisce l'esecuzione dell'algoritmo genetico
    # Probabilità per slot di spostare l'ora su un'altra settimana (unica mutazione che cambia la fitness):
    # parte da ~2 spostamenti per figlio e aumenta con la stagnazione fino al massimo
    base_probabilita_spostamento_slot = 0.002
    max_probabilita_spostamento_slot = 0.02
    probabilita_spostamento_slot = base_probabilita_spostamento_slot

    def __init__(self, config: CalendarioConfig):
        # Inizializzazione dei parametri
        self.config = config
        self.num_varianti = config.num_varianti
        self.data_inizio_str = config.data_inizio_str
        self.data_fine_str = config.data_fine_str
        self.ore_tot_civics = config.ore_tot_civics
        # Sanitize cartella_output to prevent path traversal
        self.cartella_output = _sanitize_output_path(config.cartella_output)
        self.num_generazioni = config.num_generazioni
        self.early_stopping_n = config.early_stopping_n
        self.popolazione_size = config.popolazione_size
        self.probabilita_mutazione = config.probabilita_mutazione
        self.probabilita_crossover = config.probabilita_crossover
        self.elitismo_rate = config.elitismo_rate
        self.num_cores = config.num_cores
        self.allow_teacher_replace_self = config.allow_teacher_replace_self
        self.save_interval = config.save_interval
        self.log_ogni_n_generazioni = config.log_ogni_n_generazioni

        # Backup degli hyperparams di base
        self.base_probabilita_mutazione = config.probabilita_mutazione
        self.base_probabilita_crossover = config.probabilita_crossover
        self.base_elitismo_rate = config.elitismo_rate

        self.hyperparams = {
            'probabilita_mutazione': self.probabilita_mutazione,
            'probabilita_crossover': self.probabilita_crossover,
            'elitismo_rate': self.elitismo_rate
        }

        # Stampa parametri di inizializzazione
        print("Parametri iniziali:")
        print(f"num_varianti = {self.num_varianti}")
        print(f"data_inizio_str = {self.data_inizio_str}")
        print(f"data_fine_str = {self.data_fine_str}")
        print(f"ore_tot_civics = {self.ore_tot_civics}")
        print(f"cartella_output = {self.cartella_output}")
        print(f"num_generazioni = {self.num_generazioni}")
        print(f"early_stopping_n = {self.early_stopping_n}")
        print(f"popolazione_size = {self.popolazione_size}")
        print(f"probabilita_mutazione = {self.probabilita_mutazione}")
        print(f"probabilita_crossover = {self.probabilita_crossover}")
        print(f"elitismo_rate = {self.elitismo_rate}")
        print(f"num_cores = {self.num_cores}")
        print(f"allow_teacher_replace_self = {self.allow_teacher_replace_self}")
        print(f"save_interval = {self.save_interval}")
        print(f"log_ogni_n_generazioni = {self.log_ogni_n_generazioni}")

        # Caricamento dati e inizializzazione variabili
        self.load_data()
        self.initialize_variables()

    def calcola_probabilita_mutazione(self, generazioni_senza_miglioramento):
        # Aumenta gradualmente la probabilità di mutazione se non c'è miglioramento
        base_prob = self.base_probabilita_mutazione
        return min(0.5, base_prob * (1 + generazioni_senza_miglioramento / 10))

    def calcola_probabilita_spostamento_slot(self, generazioni_senza_miglioramento):
        # Aumenta gradualmente la probabilità di spostare gli slot se non c'è miglioramento
        return min(self.max_probabilita_spostamento_slot,
                   self.base_probabilita_spostamento_slot * (1 + generazioni_senza_miglioramento / 10))

    def calcola_elitismo_rate(self, generazioni_senza_miglioramento):
        # Aumenta gradualmente il tasso di elitismo se non c'è miglioramento
        base_rate = self.base_elitismo_rate
        return min(0.1, base_rate * (1 + generazioni_senza_miglioramento / 10))

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
                f"l'esito si vede dalla popolazione iniziale.")

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

    def genera_calendario(self):
        # Funzione principale che esegue l'algoritmo genetico, genera popolazione,
        # esegue crossover, mutazione, selezione e infine salva i risultati

        inizio_esecuzione = time.time()
        logging.info("Inizializzazione della popolazione...")
        self.initialize_population()

        if len(self.population) == 0:
            logging.error("Impossibile generare una popolazione iniziale valida.")
            return

        migliore_fitness = float('inf')
        migliore_individuo = None
        generazioni_senza_miglioramento = 0
        generazioni_eseguite = 0
        motivo_arresto = "limite di generazioni raggiunto"
        fitness_riga_precedente = None  # fitness all'ultima riga di avanzamento
        fitness_ultimo_evento = None    # fitness all'ultimo miglioramento significativo loggato
        soglia_miglioramento = 0.01     # logga un evento solo se la fitness scende di almeno l'1%

        logging.info("Esecuzione dell'algoritmo genetico...")
        for generazione in range(self.num_generazioni):
            generazioni_eseguite = generazione + 1

            # Aggiorna probabilità di mutazione ed elitismo in base alla mancata miglioria
            self.probabilita_mutazione = self.calcola_probabilita_mutazione(generazioni_senza_miglioramento)
            self.hyperparams['probabilita_mutazione'] = self.probabilita_mutazione
            self.probabilita_spostamento_slot = self.calcola_probabilita_spostamento_slot(generazioni_senza_miglioramento)

            self.evaluate_population()
            self.population.sort(key=lambda x: x['fitness'])

            num_elite = max(1, int(self.calcola_elitismo_rate(generazioni_senza_miglioramento) * self.popolazione_size))
            elite = self.population[:num_elite]

            # Controllo miglioramento
            if self.population[0]['fitness'] < migliore_fitness:
                migliore_fitness = self.population[0]['fitness']
                migliore_individuo = self.population[0]['individuo']
                generazioni_senza_miglioramento = 0
                if fitness_ultimo_evento is None:
                    logging.info(f"Generazione {generazioni_eseguite}: fitness iniziale {migliore_fitness:.1f}")
                    fitness_ultimo_evento = migliore_fitness
                elif migliore_fitness <= fitness_ultimo_evento * (1 - soglia_miglioramento):
                    logging.info(f"Generazione {generazioni_eseguite}: miglioramento significativo, fitness "
                                 f"{fitness_ultimo_evento:.1f} -> {migliore_fitness:.1f}")
                    fitness_ultimo_evento = migliore_fitness
            else:
                generazioni_senza_miglioramento += 1

            # Avanzamento periodico
            if self.log_ogni_n_generazioni > 0 and generazioni_eseguite % self.log_ogni_n_generazioni == 0:
                trascorso = time.time() - inizio_esecuzione
                rimanente = trascorso / generazioni_eseguite * (self.num_generazioni - generazioni_eseguite)
                variazione = "" if fitness_riga_precedente is None else f" ({migliore_fitness - fitness_riga_precedente:+.1f})"
                logging.info(f"Gen {generazioni_eseguite}/{self.num_generazioni} | miglior fitness {migliore_fitness:.1f}{variazione} | "
                             f"senza miglioramento {generazioni_senza_miglioramento}/{self.early_stopping_n} | "
                             f"trascorso {_formatta_durata(trascorso)} | rimanente al massimo ~{_formatta_durata(rimanente)}")
                fitness_riga_precedente = migliore_fitness

            # Early stopping se nessun miglioramento
            if generazioni_senza_miglioramento >= self.early_stopping_n:
                logging.info("Early stopping attivato.")
                motivo_arresto = f"early stopping ({self.early_stopping_n} generazioni senza miglioramento)"
                break

            # Ricombinazione e mutazione per generare la nuova popolazione
            self.select_and_generate_new_population(elite)

            # -------------------------------------------
            # Salvataggio dei risultati della generazione corrente
            # -------------------------------------------
            if self.save_interval > 0 and (generazione + 1) % self.save_interval == 0:
                generation_dir = os.path.join(self.cartella_output, f"generation_{generazione+1}")
                os.makedirs(generation_dir, exist_ok=True)

                best_individual = self.population[0]['individuo']
                best_calendario = self.create_calendario(best_individual)

                # Salva calendar.csv
                calendario_df = pd.DataFrame(best_calendario)
                calendario_df = _sanitize_for_excel(calendario_df)
                calendario_df.to_csv(os.path.join(generation_dir, 'calendar.csv'), index=False)

                # Calcola e salva teachersLost.csv per questa generazione
                statistiche_classi = self.calcola_statistiche(best_calendario)
                statistiche_df = pd.DataFrame(statistiche_classi)
                statistiche_df = _sanitize_for_excel(statistiche_df)
                statistiche_df.to_csv(os.path.join(generation_dir, 'teachersLost.csv'), index=False)

                # Genera i file Excel anche per la generazione intermedia
                genera_file_excel(best_calendario, self.classi_df, self.docenti_civics_df, generation_dir)

        logging.info("Migliore individuo trovato con fitness: {}".format(migliore_fitness))

        # -------------------------
        # Salvataggio finale
        # -------------------------
        calendario = self.create_calendario(migliore_individuo)

        if not os.path.exists(self.cartella_output):
            os.makedirs(self.cartella_output)

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
        logging.info(f"Generazioni eseguite: {generazioni_eseguite}/{self.num_generazioni} - motivo arresto: {motivo_arresto}")
        logging.info(f"Fitness finale: {migliore_fitness:.1f} - tempo totale: {_formatta_durata(time.time() - inizio_esecuzione)}")
        self._log_controllo_coerenza(migliore_individuo)

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

    def initialize_population(self):
        # Generazione della popolazione iniziale con approcci diversi (greedy, batch, random)
        self.population = []
        tentativi = 0
        max_tentativi = self.popolazione_size * 100

        num_greedy = int(0.3 * self.popolazione_size)
        num_batch = int(0.3 * self.popolazione_size)
        num_random = self.popolazione_size - num_greedy - num_batch

        with multiprocessing.Pool(processes=self.num_cores, initializer=init_worker, initargs=(self,)) as pool:
            # Generazione con approccio greedy
            logging.info("Generazione popolazione iniziale con approccio greedy...")
            tentativi = 0  # tentativi separati per fase: una strategia che fallisce non deve bloccare le altre
            max_tentativi = self.num_cores  # strategia deterministica: ripetere i tentativi darebbe sempre lo stesso risultato
            while len(self.population) < num_greedy and tentativi < max_tentativi:
                batch_size = min(num_greedy - len(self.population), self.num_cores)
                results = pool.map(genera_individuo_greedy_helper, [None] * batch_size)
                for individuo in results:
                    if individuo is not None:
                        self.population.append({'individuo': individuo})
                tentativi += batch_size
            esiti = [("greedy", len(self.population), tentativi)]

            # Generazione con approccio per fasce (batch)
            logging.info("Generazione popolazione iniziale con approccio per fasce...")
            tentativi = 0  # tentativi separati per fase: una strategia che fallisce non deve bloccare le altre
            max_tentativi = self.num_cores  # strategia deterministica: ripetere i tentativi darebbe sempre lo stesso risultato
            validi_prima = len(self.population)
            while len(self.population) < num_greedy + num_batch and tentativi < max_tentativi:
                batch_size = min(num_batch - (len(self.population) - num_greedy), self.num_cores)
                results = pool.map(genera_individuo_batch_helper, [None] * batch_size)
                for individuo in results:
                    if individuo is not None:
                        self.population.append({'individuo': individuo})
                tentativi += batch_size
            esiti.append(("batch", len(self.population) - validi_prima, tentativi))

            # Generazione con approccio random
            logging.info("Generazione popolazione iniziale con approccio casuale...")
            tentativi = 0
            max_tentativi = self.popolazione_size * 100
            validi_prima = len(self.population)
            while len(self.population) < self.popolazione_size and tentativi < max_tentativi:
                batch_size = min(self.popolazione_size - len(self.population), self.num_cores)
                results = pool.map(genera_individuo_random_helper, [None] * batch_size)
                for individuo in results:
                    if individuo is not None:
                        self.population.append({'individuo': individuo})
                tentativi += batch_size
            esiti.append(("random", len(self.population) - validi_prima, tentativi))

        logging.info("Popolazione iniziale (individui validi/tentativi): "
                     + ", ".join(f"{nome} {validi}/{tent}" for nome, validi, tent in esiti))

    def evaluate_population(self):
        # Calcolo della fitness per ogni individuo della popolazione in parallelo
        with multiprocessing.Pool(processes=self.num_cores, initializer=init_worker, initargs=(self,)) as pool:
            fitness_results = pool.map(calcola_fitness_helper, [ind['individuo'] for ind in self.population])
        for i, fit in enumerate(fitness_results):
            self.population[i]['fitness'] = fit

    def select_and_generate_new_population(self, elite):
        # Selezione e generazione nuova popolazione
        selected = self.selezione([ind['individuo'] for ind in self.population], [ind['fitness'] for ind in self.population])
        new_population = elite.copy()
        while len(new_population) < self.popolazione_size:
            genitore1 = random.choice(selected)
            genitore2 = random.choice(selected)
            if random.random() < self.probabilita_crossover:
                figlio = self.crossover(genitore1, genitore2)
            else:
                figlio = genitore1.copy()

            figlio = self.mutazione(figlio)

            if self.verifica_vincoli(figlio):
                new_population.append({'individuo': figlio})

        self.population = new_population

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

    def genera_individuo_random(self, _):
        return self.genera_individuo_base(strategy='random')

    def genera_individuo_greedy(self, _):
        return self.genera_individuo_base(strategy='greedy')

    def genera_individuo_batch(self, _):
        return self.genera_individuo_base(strategy='batch')

    def genera_individuo_base(self, strategy='random'):
        # Genera un individuo con la strategia indicata (greedy, batch, random)
        individuo = {}
        ore_per_classe = defaultdict(int)
        occupati = set()  # (data, ora, docente): un docente può stare in una sola classe alla volta
        ore_settimanali_classe = defaultdict(lambda: defaultdict(int))

        if strategy == 'greedy':
            slot_copia = sorted(self.slot_disponibili, key=lambda x: x['DATA'])
        elif strategy == 'batch':
            slot_copia = sorted(self.slot_disponibili, key=lambda x: (x['CLASSE'], x['DATA']))
        else:
            slot_copia = self.slot_disponibili.copy()
            random.shuffle(slot_copia)

        # Assegna docenti civics in base alla strategia
        for slot in slot_copia:
            nome_classe = slot['CLASSE']
            data = slot['DATA']
            settimana = slot['SETTIMANA']

            # Controlla limite di ore totali e settimanali
            if ore_per_classe[nome_classe] >= self.ore_tot_civics:
                continue
            if ore_settimanali_classe[nome_classe][settimana] >= 1:
                continue

            nome_giorno = slot['GIORNO']
            ora = slot['ORA']
            slot_key = slot['KEY']
            docente_sostituito = slot['DOCENTE_SOSTITUITO']

            # Trova docenti civics possibili
            docenti_possibili = []
            for docente_civics in self.docenti_per_classe[nome_classe]:
                disponibile = False
                if (docente_civics in self.docenti_civics_organico[nome_classe]) and (docente_civics == docente_sostituito):
                    # Se il docente civics insegna anche la materia e coincide con il docente sostituito
                    disponibile = True
                else:
                    # Controlla disponibilità sul giorno e ora
                    if len(self.disponibilita_civics[docente_civics][nome_giorno]) >= ora and \
                        self.disponibilita_civics[docente_civics][nome_giorno][ora - 1]:
                        disponibile = True

                    # Controllo se il docente non insegna due ore nello stesso giorno alla stessa ora
                    if disponibile and (data, ora, docente_civics) not in occupati:
                        docenti_possibili.append(docente_civics)

            if docenti_possibili:
                if strategy == 'greedy':
                    docente_assegnato = docenti_possibili[0]
                else:
                    docente_assegnato = random.choice(docenti_possibili)
                individuo[slot_key] = docente_assegnato
                ore_per_classe[nome_classe] += 1
                ore_settimanali_classe[nome_classe][settimana] += 1
                occupati.add((data, ora, docente_assegnato))

        if self.verifica_vincoli(individuo):
            return individuo
        else:
            return None

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

    def _calcola_penalita_classe(self, classe, ore_perse_docente):
        variance_total = 0
        max_percentage_penalty = 0
        penalties_total = 0

        medium_intensity_penalty = 5
        high_intensity_penalty = 10
        low_intensity_penalty = 1

        # Penalità per docenti civics
        medium_intensity_penalty_civics_teacher = 10
        high_intensity_penalty_civics_teacher = 20
        low_intensity_penalty_civics_teacher = 0.5

        # Utilizza il lookup pre-calcolato invece della scansione O(N)
        ore_totali_docente = self.ore_totali_docente_per_classe[classe]
        P = self.P_per_classe.get(classe, 0)
        docenti_organico = self.docenti_civics_organico[classe]

        percentuali = []
        for docente in ore_totali_docente:
            ore_totali = ore_totali_docente[docente]
            ore_perse = ore_perse_docente.get(docente, 0)
            percentuale_perse = (ore_perse / ore_totali) * 100 if ore_totali > 0 else 0
            percentuali.append(percentuale_perse)

            is_organico = docente in docenti_organico

            # Penalità in base alla percentuale di ore perse
            if percentuale_perse > 2 * P:
                if is_organico:
                    penalties_total += high_intensity_penalty_civics_teacher
                else:
                    penalties_total += high_intensity_penalty
            elif percentuale_perse > P:
                if is_organico:
                    penalties_total += medium_intensity_penalty_civics_teacher
                else:
                    penalties_total += medium_intensity_penalty
            elif percentuale_perse < 0.3 * P:
                if is_organico:
                    penalties_total += low_intensity_penalty_civics_teacher
                else:
                    penalties_total += low_intensity_penalty

            # Penalità per percentuali molto alte
            if is_organico:
                if percentuale_perse > 5:
                    max_percentage_penalty += (percentuale_perse - 5) * 10

        if percentuali:
            n = len(percentuali)
            mean = sum(percentuali) / n
            variance = sum((x - mean) ** 2 for x in percentuali) / n
            variance_total += variance

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

    def selezione(self, popolazione, fitness):
        # Selezione con ranking
        popolazione_fitness = list(zip(popolazione, fitness))
        popolazione_fitness.sort(key=lambda x: x[1])
        ranks = range(len(popolazione), 0, -1)
        total_rank = sum(ranks)
        selection_probs = [rank / total_rank for rank in ranks]
        popolazione_sorted = [ind for ind, fit in popolazione_fitness]
        selected = random.choices(popolazione_sorted, weights=selection_probs, k=len(popolazione))
        return selected

    def crossover(self, genitore1, genitore2):
        # Crossover: unisce parti di genitore1 e genitore2
        figlio = {}
        blocks = self.identify_blocks(genitore1, genitore2)
        for block in blocks:
            if random.random() < 0.5:
                figlio.update(block['genitore1'])
            else:
                figlio.update(block['genitore2'])
        return figlio

    def identify_blocks(self, genitore1, genitore2):
        # Identifica blocchi di chiavi da scambiare
        keys = list(genitore1.keys())
        random.shuffle(keys)
        blocks = []
        block_size = max(1, len(keys) // 10)
        for i in range(0, len(keys), block_size):
            block_keys = keys[i:i+block_size]
            block_gen1 = {k: genitore1[k] for k in block_keys}
            block_gen2 = {k: genitore2.get(k, genitore1[k]) for k in block_keys}
            blocks.append({'genitore1': block_gen1, 'genitore2': block_gen2})
        return blocks

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

    def mutazione(self, individuo):
        # Mutazione: cambia il docente assegnato e, con bassa probabilità, sposta lo slot di una classe
        # su un'altra settimana libera. Se il docente è occupato con un'altra classe, prova a spostare
        # anche quella (scambio). Mantiene il vincolo "un docente in una sola classe alla volta".
        occupati = {}  # (data, ora, docente) -> chiave dello slot che lo occupa
        settimane_classe = defaultdict(set)
        for key, docente_civics in individuo.items():
            slot_info = self.slots_by_key[key]
            occupati[(slot_info['DATA'], slot_info['ORA'], docente_civics)] = key
            settimane_classe[slot_info['CLASSE']].add(slot_info['SETTIMANA'])

        def slot_candidato(slot_vecchio):
            # Slot casuale della stessa classe, non usato, in una settimana libera (o nella stessa dello slot)
            nuovo = random.choice(self.slots_by_class[slot_vecchio['CLASSE']])
            if nuovo['KEY'] in individuo:
                return None
            if nuovo['SETTIMANA'] != slot_vecchio['SETTIMANA'] and nuovo['SETTIMANA'] in settimane_classe[slot_vecchio['CLASSE']]:
                return None
            return nuovo

        def docenti_liberi(nuovo):
            return [d for d in self._docenti_disponibili(nuovo) if (nuovo['DATA'], nuovo['ORA'], d) not in occupati]

        def sposta(vecchia_key, nuovo, docente_nuovo):
            vecchio = self.slots_by_key[vecchia_key]
            occupati.pop((vecchio['DATA'], vecchio['ORA'], individuo.pop(vecchia_key)), None)
            individuo[nuovo['KEY']] = docente_nuovo
            occupati[(nuovo['DATA'], nuovo['ORA'], docente_nuovo)] = nuovo['KEY']
            settimane_classe[vecchio['CLASSE']].discard(vecchio['SETTIMANA'])
            settimane_classe[vecchio['CLASSE']].add(nuovo['SETTIMANA'])

        def prova_scambio(key, nuovo):
            # Libera lo slot "nuovo" spostando la classe che occupa uno dei docenti disponibili
            occupanti = [(d, occupati[(nuovo['DATA'], nuovo['ORA'], d)]) for d in self._docenti_disponibili(nuovo)]
            if not occupanti:
                return False
            docente, key_b = random.choice(occupanti)
            slot_b = self.slots_by_key[key_b]
            for _ in range(10):
                nuovo_b = slot_candidato(slot_b)
                if nuovo_b is not None and docente in docenti_liberi(nuovo_b):
                    sposta(key_b, nuovo_b, docente)
                    sposta(key, nuovo, docente)
                    return True
            return False

        for key in list(individuo.keys()):
            if key not in individuo:  # già spostato da uno scambio
                continue
            slot_info = self.slots_by_key[key]
            data = slot_info['DATA']
            ora = slot_info['ORA']

            if random.random() < self.probabilita_mutazione:
                docenti_possibili = [d for d in self._docenti_disponibili(slot_info)
                                     if (data, ora, d) not in occupati or d == individuo[key]]
                if docenti_possibili:
                    occupati.pop((data, ora, individuo[key]), None)
                    individuo[key] = random.choice(docenti_possibili)
                    occupati[(data, ora, individuo[key])] = key

            if random.random() < self.probabilita_spostamento_slot:
                for _ in range(10):
                    nuovo = slot_candidato(slot_info)
                    if nuovo is None:
                        continue
                    liberi = docenti_liberi(nuovo)
                    if liberi:
                        sposta(key, nuovo, random.choice(liberi))
                        break
                    if prova_scambio(key, nuovo):
                        break
        return individuo


_worker_instance = None

def init_worker(instance):
    global _worker_instance
    _worker_instance = instance

def genera_individuo_greedy_helper(args):
    return _worker_instance.genera_individuo_greedy(args)

def genera_individuo_batch_helper(args):
    return _worker_instance.genera_individuo_batch(args)

def genera_individuo_random_helper(args):
    return _worker_instance.genera_individuo_random(args)

def calcola_fitness_helper(individuo):
    return _worker_instance.calcola_fitness(individuo)


if __name__ == "__main__":
    config = CalendarioConfig(
        num_varianti=1,
        data_inizio_str='01/10/2026',
        data_fine_str='10/06/2027',
        ore_tot_civics=31,
        cartella_output="CALENDARIO_GENERATO",
        num_generazioni=9000,
        early_stopping_n=300,
        popolazione_size=500,
        probabilita_mutazione=0.05,  # solo docenti: non cambia la fitness, costa tempo
        probabilita_crossover=0.8,
        elitismo_rate=0.005,
        num_cores=15,
        save_interval=500,
        log_ogni_n_generazioni=25,
        allow_teacher_replace_self=True
    )
    import multiprocessing
    multiprocessing.set_start_method("fork")  # Python 3.14: default forkserver non funziona col Pool
    generator = CalendarioGenerator(config)
    generator.genera_calendario()

