# -------------------------------------------------------------------------
# Questo script utilizza OR-Tools CP-SAT per generare un calendario di sostituzioni
# di docenti di educazione civica, in modo da distribuire in maniera più omogenea
# le ore perse tra i docenti e le classi.
#
# **Obiettivi:**
# L'obiettivo è quello di creare un calendario di sostituzioni che, partendo dai docenti
# di educazione civica disponibili, copra le ore di lezione previste affinché ogni classe
# abbia un'ora di educazione civica a settimana fino a fine anno (le settimane ridotte dalle chiusure,
# senza lezioni, non la hanno), distribuendo
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
import time
from dataclasses import dataclass, field
from ortools.sat.python import cp_model

from .output import (
    _COLORE_BORDO, _COLORE_SCURO, _NOMI_GIORNI, _get_excel_styles,
    _get_week_range, _scrivi_titolo_foglio, genera_file_excel,
    genera_orario_classi, genera_orario_docenti,
)
from .sicurezza import (
    _sanitize_for_excel, _sanitize_for_logging, _sanitize_output_path,
    _sanitize_sheet_name,
)


# Configura il logger per informazioni sull'esecuzione
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Scala dell'obiettivo intero CP-SAT (fitness * SCALA_OBIETTIVO) e risoluzione delle percentuali (decimi di punto)
SCALA_OBIETTIVO = 100_000
DECIMI = 10
# Peso della penalità quadratica sulle ore perse oltre la quota proporzionale (ore_totali * P / 100): niente soglie piatte
PESO_ECCESSO = 5
# Riavvii (seed diverso, soluzione migliore come hint) se il gap rispetto al limite inferiore resta sopra gap_relativo
TENTATIVI_MAX = 3


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
    cartella_output: str = "CALENDARIO_GENERATO"
    cartella_input: str = "FILE_SCUOLA"
    tempo_max_secondi: float = 900  # budget per gruppo di classi, normalmente uno per docente di civica; residuo redistribuito
    num_cores: int = 4
    allow_teacher_replace_self: bool = True
    gap_relativo: float = 0.001  # 0,1% per gruppo di classi: distanza relativa tra soluzione e limite inferiore
    assegnazioni_fisse: list = field(default_factory=list)


class CalendarioGenerator:
    # Classe principale che gestisce caricamento dati, risoluzione CP-SAT e salvataggio dei risultati

    def __init__(self, config: CalendarioConfig):
        # Inizializzazione dei parametri
        self.config = config
        self.num_varianti = config.num_varianti
        self.data_inizio_str = config.data_inizio_str
        self.data_fine_str = config.data_fine_str
        # Sanitize cartella_output to prevent path traversal
        self.cartella_output = _sanitize_output_path(config.cartella_output)
        self.cartella_input = _sanitize_output_path(config.cartella_input, default="FILE_SCUOLA")
        self.tempo_max_secondi = config.tempo_max_secondi
        self.num_cores = config.num_cores
        self.allow_teacher_replace_self = config.allow_teacher_replace_self
        self.gap_relativo = config.gap_relativo
        self.assegnazioni_fisse = config.assegnazioni_fisse

        # Stampa parametri di inizializzazione
        print("Parametri iniziali:")
        print(f"num_varianti = {self.num_varianti}")
        print(f"data_inizio_str = {self.data_inizio_str}")
        print(f"data_fine_str = {self.data_fine_str}")
        print(f"cartella_output = {self.cartella_output}")
        print(f"tempo_max_secondi = {self.tempo_max_secondi} (budget per gruppo di classi / docente di civica, residuo redistribuito)")
        print(f"num_cores = {self.num_cores}")
        print(f"allow_teacher_replace_self = {self.allow_teacher_replace_self}")
        print(f"gap_relativo = {self.gap_relativo} ({self.gap_relativo * 100:g}% per gruppo di classi)")
        print(f"assegnazioni_fisse = {_sanitize_for_logging(self.assegnazioni_fisse)}")

        # Caricamento dati e inizializzazione variabili
        self.load_data()
        self.initialize_variables()

    def load_data(self):
        # Caricamento dati da file CSV
        logging.info("Caricamento dei file CSV...")
        try:
            self.classi_df = pd.read_csv(os.path.join(self.cartella_input, 'classes.csv'))
            self.docenti_civics_df = pd.read_csv(os.path.join(self.cartella_input, 'civics_teachers.csv'))
            self.disponibilita_df = pd.read_csv(os.path.join(self.cartella_input, 'availability.csv'))
            self.chiusure_df = pd.read_csv(os.path.join(self.cartella_input, 'closures.csv'))
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
        settimane_utili = len(set(self.settimana_di.values()))
        n_classi = len(self.classi_list)
        docenti = list(self.docenti_civics_classi.keys())
        logging.info(
            f"Struttura dati: {n_classi} classi, {len(docenti)} docenti civics ({', '.join(docenti)}), "
            f"{len(self.slot_disponibili)} slot disponibili, {settimane_utili} settimane utili dopo le chiusure "
            f"({len(self.date_scolastiche)} giorni scolastici), 1 ora a settimana per classe "
            f"({sum(self.ore_per_classe.values())} ore totali, da {min(self.ore_per_classe.values(), default=0)} "
            f"a {max(self.ore_per_classe.values(), default=0)} per classe)")
        # Settimane con lezioni in cui la classe non ha l'ora (docenti civica insufficienti, tipicamente settimane corte)
        senza_ora = {c: len({s['SETTIMANA'] for s in self.slots_by_class[c]}) - self.ore_per_classe[c]
                     for c in self.classi_list}
        if any(senza_ora.values()):
            logging.warning("Settimane con lezioni ma senza ora di educazione civica (docenti civica insufficienti): "
                            + ", ".join(f"{_sanitize_for_logging(c)} {n}" for c, n in senza_ora.items() if n))

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

        # Settimane parziali consecutive (es. prima e dopo le vacanze) senza giorni della settimana in comune
        # contano come una sola settimana: chiave = numero ISO della prima
        giorni = defaultdict(set)
        for d in self.date_scolastiche:
            giorni[d.isocalendar()[:2]].add(d.weekday())
        chiavi, chiave, usati = {}, None, set()
        for anno_sett in sorted(giorni):
            if chiave is None or giorni[anno_sett] & usati:
                chiave, usati = anno_sett[1], set()
            usati |= giorni[anno_sett]
            chiavi[anno_sett] = chiave
        self.settimana_di = {d: chiavi[d.isocalendar()[:2]] for d in self.date_scolastiche}

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
                lista_docenti = (row[colonna_doc] if isinstance(row[colonna_doc], str) else '').split(';')
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
                lista_docenti = (row[colonna_doc] if isinstance(row[colonna_doc], str) else '').split(';')
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
                                'SETTIMANA': self.settimana_di[data]
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

        self._valida_assegnazioni_fisse()
        self._assegna_settimane()
        self.ore_per_classe = {c: len(w) for c, w in self.settimane_classe.items()}

        # Pre-calcola P per ogni classe per ottimizzare le prestazioni in _calcola_penalita_classe
        self.P_per_classe = {}
        for classe in self.classi_list:
            ore_totali_docente = self.ore_totali_docente_per_classe[classe]
            total_teaching_hours = sum(ore_totali_docente.values())
            self.P_per_classe[classe] = (self.ore_per_classe[classe] / total_teaching_hours) * 100 if total_teaching_hours > 0 else 0

    def _valida_assegnazioni_fisse(self):
        self.assegnazioni_fisse_per_slot = {}
        per_settimana, occupate = {}, {}
        richiesti = {'classe', 'data', 'ora', 'docente_civics'}
        try:
            assegnazioni = getattr(self, 'assegnazioni_fisse', [])
            if not isinstance(assegnazioni, list):
                raise ValueError("assegnazioni_fisse deve essere una lista.")
            for a in assegnazioni:
                if (not isinstance(a, dict) or not richiesti <= a.keys()
                        or a.keys() - richiesti - {'docente_sostituito'}):
                    raise ValueError("Ogni assegnazione richiede classe, data, ora, docente_civics; "
                                     "è ammesso anche docente_sostituito.")
                for campo in a.keys() - {'ora'}:
                    if not isinstance(a[campo], str) or not a[campo].strip():
                        raise ValueError(f"Il campo {campo} deve essere una stringa non vuota.")
                classe, docente, ora = a['classe'], a['docente_civics'], a['ora']
                if type(ora) is not int or ora < 1:
                    raise ValueError("ora deve essere un intero positivo (1 = prima ora).")
                data = datetime.strptime(a['data'], '%d/%m/%Y')
                if classe not in self.classi_list:
                    raise ValueError(f"Classe inesistente: {classe}.")
                if docente not in self.docenti_per_classe[classe]:
                    raise ValueError(f"Docente {docente} non assegnato alla classe {classe}.")
                slot = next((s for s in self.slots_by_class[classe]
                             if s['DATA'] == data and s['ORA'] == ora), None)
                if slot is None:
                    raise ValueError(f"Nessuna lezione per {classe} il {a['data']} alla {ora}ª ora: "
                                     "data fuori periodo, chiusura o ora senza lezione.")
                if 'docente_sostituito' in a and a['docente_sostituito'] != slot['DOCENTE_SOSTITUITO']:
                    raise ValueError(f"docente_sostituito diverso dall'orario di {classe} "
                                     f"il {a['data']} alla {ora}ª ora.")
                if docente not in self._docenti_disponibili(slot):
                    raise ValueError(f"Docente {docente} non disponibile per {classe} "
                                     f"il {a['data']} alla {ora}ª ora.")
                settimana = (classe, slot['SETTIMANA'])
                scelta = (slot['KEY'], docente)
                if settimana in per_settimana and per_settimana[settimana] != scelta:
                    raise ValueError(f"Più assegnazioni fisse per {classe} nella stessa settimana.")
                cella = (data, ora, docente)
                if cella in occupate and occupate[cella] != classe:
                    raise ValueError(f"Docente {docente} assegnato a due classi "
                                     f"il {a['data']} alla {ora}ª ora.")
                per_settimana[settimana] = scelta
                occupate[cella] = classe
                self.assegnazioni_fisse_per_slot[slot['KEY']] = docente
        except ValueError as e:
            logging.error(f"Errore assegnazioni fisse: {_sanitize_for_logging(e)}")
            raise SystemExit(1)

    def _assegna_settimane(self):
        # Un'ora a settimana per classe. Nelle settimane corte (chiusure) i docenti civica non riescono a coprire tutte
        # le classi: per ogni settimana si cerca il massimo insieme di classi coperibile insieme (accoppiamento classi -
        # celle data/ora/docente, le settimane sono indipendenti) e l'ora manca alle classi con meno settimane già perse
        celle = defaultdict(lambda: defaultdict(set))  # settimana -> classe -> celle (data, ora, docente) possibili
        for c in self.classi_list:
            for s in self.slots_by_class[c]:
                for d in self._docenti_disponibili(s):
                    celle[s['SETTIMANA']][c].add((s['DATA'], s['ORA'], d))

        # Le classi con un'assegnazione fissa partecipano solo con la cella riservata e hanno precedenza.
        fissate = defaultdict(set)
        for key, docente in self.assegnazioni_fisse_per_slot.items():
            s = self.slots_by_key[key]
            celle[s['SETTIMANA']][s['CLASSE']] = {(s['DATA'], s['ORA'], docente)}
            fissate[s['SETTIMANA']].add(s['CLASSE'])

        def coperibili(classi, adj):
            occupata = {}

            def assegna(c, viste):
                for cella in adj[c]:
                    if cella not in viste:
                        viste.add(cella)
                        if cella not in occupata or assegna(occupata[cella], viste):
                            occupata[cella] = c
                            return True
                return False
            return all(assegna(c, set()) for c in classi)

        perse = defaultdict(int)
        self.settimane_classe = {c: set() for c in self.classi_list}
        for settimana, adj in sorted(celle.items()):
            scelte = sorted(fissate[settimana])
            for c in scelte:
                self.settimane_classe[c].add(settimana)
            for c in sorted(adj.keys() - fissate[settimana], key=lambda c: (-perse[c], c)):
                if coperibili(scelte + [c], adj):
                    scelte.append(c)
                    self.settimane_classe[c].add(settimana)
                else:
                    perse[c] += 1

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

    def _minimo_classe(self, classe):
        # Minimo esatto della fitness di una classe ignorando i conflitti con le altre (programmazione dinamica su
        # ore perse totali e somma delle percentuali): limite inferiore valido per il modello CP-SAT
        import numpy as np  # locale: ortools richiede il numpy reale
        con_candidati = defaultdict(set)
        for s in self.slots_by_class[classe]:
            if s['SETTIMANA'] in self.settimane_classe[classe] and self._docenti_disponibili(s):
                con_candidati[s['DOCENTE_SOSTITUITO']].add(s['SETTIMANA'])
        R = self.ore_per_classe[classe]
        tabelle = []
        for docente, ore_totali in self.ore_totali_docente_per_classe[classe].items():
            massimo = min(ore_totali, len(con_candidati[docente]), R)
            tab = [self._penalita_docente(classe, docente, l) for l in range(massimo + 1)]
            tabelle.append([(p + mp, round(pct * DECIMI)) for p, mp, pct in tab])
        n = len(tabelle)
        a = 5 / (n * DECIMI * DECIMI)  # varianza = min su mu di Σ(pc - mu)² / n = Σpc²/n - (Σpc)²/n²
        smax = sum(max(pc for _, pc in tab) for tab in tabelle)
        F = np.full((R + 1, smax + 1), np.inf)  # F[ore perse, somma percentuali] = costo minimo dei docenti visti
        F[0, 0] = 0
        for tab in tabelle:
            G = np.full_like(F, np.inf)
            for l, (costo, pc) in enumerate(tab[:R + 1]):
                np.minimum(G[l:, pc:], F[:R + 1 - l, :smax + 1 - pc] + costo + a * pc * pc, out=G[l:, pc:])
            F = G
        return float((F[R] - a * np.arange(smax + 1) ** 2 / n).min())

    def _risolvi_componente(self, classi, tempo_max_secondi):
        # Modello CP-SAT: x[slot, docente] = il docente civics copre lo slot. Obiettivo = fitness * SCALA_OBIETTIVO
        # (penalità per docente come tabelle sulle ore perse, varianza come somma di quadrati interi sulle percentuali
        # in decimi di punto rispetto a una media libera)
        inizio = time.time()
        m = cp_model.CpModel()
        x = {}
        occupati = defaultdict(list)  # (data, ora, docente) -> variabili: un docente in una sola classe alla volta
        costo = []
        for classe in classi:
            inizio_classe = len(costo)
            sel = {}  # chiave slot -> 1 se lo slot è usato da un docente civics
            for s in self.slots_by_class[classe]:
                vs = []
                for d in self._docenti_disponibili(s) if s['SETTIMANA'] in self.settimane_classe[classe] else []:
                    v = x[s['KEY'], d] = m.NewBoolVar(f"x_{s['KEY']}_{d}")
                    if self.assegnazioni_fisse_per_slot.get(s['KEY']) == d:
                        m.Add(v == 1)
                    occupati[s['DATA'], s['ORA'], d].append(v)
                    vs.append(v)
                sel[s['KEY']] = sum(vs)
            m.Add(sum(sel.values()) == self.ore_per_classe[classe])
            per_settimana = defaultdict(list)
            for s in self.slots_by_class[classe]:
                per_settimana[s['SETTIMANA']].append(sel[s['KEY']])
            for settimana, expr in per_settimana.items():
                m.Add(sum(expr) == (settimana in self.settimane_classe[classe]))

            percentuali = []  # (percentuale in decimi come espressione, massimo)
            for docente, ore_totali in self.ore_totali_docente_per_classe[classe].items():
                max_perse = min(ore_totali, self.ore_per_classe[classe])
                tab = [self._penalita_docente(classe, docente, l) for l in range(max_perse + 1)]
                y = [m.NewBoolVar("") for _ in tab]  # y[l] = il docente perde esattamente l ore
                m.AddExactlyOne(y)
                m.Add(sum(l * v for l, v in enumerate(y)) == sum(sel[s['KEY']] for s in self.slots_by_class[classe]
                                                                  if s['DOCENTE_SOSTITUITO'] == docente))
                costo.append(sum(round((p + mp) * SCALA_OBIETTIVO) * v for (p, mp, _), v in zip(tab, y)))
                percentuali.append((sum(round(pct * DECIMI) * v for (_, _, pct), v in zip(tab, y)),
                                    max(round(pct * DECIMI) for _, _, pct in tab)))

            # n * varianza * DECIMI² = min su mu di Σ(pc - mu)²
            n = len(percentuali)
            massimo = max(mx for _, mx in percentuali)
            mu = m.NewIntVar(0, massimo, "")
            quadrati = []
            for pc, _ in percentuali:
                scarto = m.NewIntVar(-massimo, massimo, "")
                m.Add(scarto == pc - mu)
                q = m.NewIntVar(0, massimo * massimo, "")
                m.AddMultiplicationEquality(q, [scarto, scarto])
                quadrati.append(q)
            costo.append(round(5 * SCALA_OBIETTIVO / (n * DECIMI * DECIMI)) * sum(quadrati))
            # Limite inferiore della classe (0,2% di tolleranza per gli arrotondamenti dei coefficienti): senza di esso
            # il bound di CP-SAT resta molto sotto l'ottimo e il gap non si chiude mai
            minimo = self._minimo_classe(classe)
            if minimo != float('inf'):  # inf = classe senza abbastanza ore candidate: lo dichiara infeasible CP-SAT
                m.Add(sum(costo[inizio_classe:]) >= int(minimo * SCALA_OBIETTIVO * 0.998))

        for vs in occupati.values():
            m.AddAtMostOne(vs)
        m.Minimize(sum(costo))

        # Tentativi con seed diversi e la soluzione migliore come hint, finché il gap resta sopra gap_relativo
        migliore, obiettivo, limite, stato_migliore = None, float('inf'), 0, None
        fine = time.monotonic() + tempo_max_secondi
        for tentativo in range(TENTATIVI_MAX):
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = (fine - time.monotonic()) / (TENTATIVI_MAX - tentativo)
            solver.parameters.num_workers = self.num_cores
            solver.parameters.random_seed = tentativo
            solver.parameters.relative_gap_limit = self.gap_relativo
            stato = solver.Solve(m)
            if stato not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                continue
            limite = max(limite, solver.BestObjectiveBound())
            if solver.ObjectiveValue() < obiettivo:
                obiettivo, stato_migliore = solver.ObjectiveValue(), solver.StatusName(stato)
                migliore = {key: d for (key, d), v in x.items() if solver.Value(v)}
                m.ClearHints()
                for chiave, v in x.items():
                    m.AddHint(v, solver.Value(v))
            if stato == cp_model.OPTIMAL or obiettivo - limite <= self.gap_relativo * max(1, abs(obiettivo)):
                break
        nome = ', '.join(_sanitize_for_logging(c) for c in classi)
        if migliore is None:
            logging.error(f"Nessuna soluzione per le classi {nome}: "
                          f"vincoli incompatibili o tempo_max_secondi troppo basso.")
            raise SystemExit(1)
        logging.info(f"Classi {nome}: {stato_migliore}, fitness {obiettivo / SCALA_OBIETTIVO:.1f} "
                     f"(limite inferiore {limite / SCALA_OBIETTIVO:.1f}, tentativi {tentativo + 1}) "
                     f"in {_formatta_durata(time.time() - inizio)}")
        return migliore

    def genera_calendario(self):
        # Risolve il problema con CP-SAT e salva i risultati
        inizio_esecuzione = time.time()
        tempo_totale_max = self.tempo_max_secondi * len(self._componenti())
        fine_max = datetime.now() + timedelta(seconds=tempo_totale_max)
        logging.info(f"Tempo massimo di risoluzione: {_formatta_durata(tempo_totale_max)} - "
                     f"ora di fine stimata (al tempo massimo): {fine_max.strftime('%d/%m/%Y %H:%M:%S')}")
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
        classi_errate = [c for c in self.classi_list if ore_per_classe[c] != self.ore_per_classe[c]]
        esito = "OK" if not (classi_errate or settimane_doppie or doppi_impegni) else "ERRORE"
        logging.info(f"Controllo coerenza: {esito} - classi con ore != settimane utili: {len(classi_errate)}, "
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

        if any(individuo.get(key) != docente
               for key, docente in getattr(self, 'assegnazioni_fisse_per_slot', {}).items()):
            return False

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

        # Ogni classe deve avere esattamente un'ora in ogni settimana utile
        if not all(ore_per_classe[nome_classe] == self.ore_per_classe[nome_classe]
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
        # Penalità per eccesso/difetto di ore perse e penalità sulle percentuali alte per un docente sostituito in una classe.
        # Ritorna (penalità eccesso/difetto, penalità percentuale alta, percentuale di ore perse)
        low_intensity_penalty = 1

        # Penalità per docenti civics
        low_intensity_penalty_civics_teacher = 0.5

        P = self.P_per_classe.get(classe, 0)
        ore_totali = self.ore_totali_docente_per_classe[classe][docente]
        percentuale_perse = (ore_perse / ore_totali) * 100 if ore_totali > 0 else 0
        is_organico = docente in self.docenti_civics_organico[classe]

        penalita = 0
        if percentuale_perse < 0.3 * P:
            penalita = low_intensity_penalty_civics_teacher if is_organico else low_intensity_penalty
        # Eccesso rispetto alla quota proporzionale (ore_totali * P / 100): penalità quadratica, così l'eccesso
        # inevitabile si ripartisce tra i docenti in proporzione alle loro ore invece di cadere su uno solo
        ideale = ore_totali * P / 100
        if ore_perse > ideale:
            penalita += PESO_ECCESSO * (2 if is_organico else 1) * (ore_perse - ideale) ** 2 / ideale

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
            if docente_civics == slot['DOCENTE_SOSTITUITO']:
                # Lezione propria: il docente la copre solo se consentito (non conta availability.csv)
                disponibile = self.allow_teacher_replace_self
            else:
                # Lezione di un altro docente: vale la disponibilità oraria, anche per i docenti della classe
                disponibilita = self.disponibilita_civics[docente_civics][nome_giorno]
                disponibile = len(disponibilita) >= ora and disponibilita[ora - 1]

            if disponibile:
                docenti_possibili.append(docente_civics)
        return docenti_possibili
