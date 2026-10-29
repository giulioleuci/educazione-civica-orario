import itertools
import sys
from datetime import datetime, timedelta
from collections import defaultdict

import pytest
from conftest import real_modules
import generator_mod
from generator_mod import CalendarioConfig, CalendarioGenerator


@pytest.fixture(autouse=True)
def numpy_pandas_reali(monkeypatch):
    # conftest sostituisce numpy/pandas con mock, ma ortools ha bisogno di quelli reali
    for nome, modulo in real_modules.items():
        monkeypatch.setitem(sys.modules, nome, modulo)


class Gen(CalendarioGenerator):
    def __init__(self, classi, docenti_classi, slot_per_classe, assegnazioni_fisse=None):
        # slot_per_classe: {classe: [(settimana, ora, docente_sostituito), ...]}
        self.classi_list = classi
        self.docenti_civics_classi = docenti_classi
        self.allow_teacher_replace_self = True
        self.num_cores = 1
        self.tempo_max_secondi = 20
        self.gap_relativo = 0.005
        self.assegnazioni_fisse = [] if assegnazioni_fisse is None else assegnazioni_fisse
        self.giorni_settimana = ['LUN']
        self.docenti_civics_organico = defaultdict(set)
        self.disponibilita_civics = {d: {'LUN': [True] * 4} for d in docenti_classi}
        base = datetime(2026, 10, 5)  # lunedì
        self.slot_disponibili = [
            {'CLASSE': c, 'DATA': base + timedelta(weeks=w), 'GIORNO': 'LUN', 'ORA': ora,
             'DOCENTE_SOSTITUITO': doc, 'KEY': f"{c}_{w}_{ora}", 'SETTIMANA': w}
            for c, slots in slot_per_classe.items() for w, ora, doc in slots]
        self._precalcola_lookups()


def _brute_force(gen, docente):
    # Ottimo esaustivo per un solo docente civics: tutte le scelte valide, fitness con calcola_fitness
    per_classe = []
    for c in gen.classi_list:
        scelte = [s for s in itertools.combinations(gen.slots_by_class[c], gen.ore_per_classe[c])
                  if len({x['SETTIMANA'] for x in s}) == len(s)]
        per_classe.append(scelte)
    migliore = float('inf')
    for combo in itertools.product(*per_classe):
        slots = [s for scelta in combo for s in scelta]
        if len({(s['DATA'], s['ORA']) for s in slots}) != len(slots):
            continue
        individuo = {s['KEY']: docente for s in slots}
        if gen._ripetizioni_consecutive(individuo):
            continue
        migliore = min(migliore, gen.calcola_fitness(individuo))
    return migliore


def test_soluzione_ottima_e_valida():
    # B a un'ora diversa da A nelle settimane con un solo slot, altrimenti il docente C sarebbe in conflitto
    slot = {'A': [(1, 1, 'X'), (2, 1, 'Y'), (3, 1, 'X'), (3, 2, 'Z'), (4, 1, 'Y')],
            'B': [(1, 2, 'X'), (2, 2, 'Y'), (3, 1, 'X'), (3, 2, 'Z'), (4, 2, 'Y')]}
    gen = Gen(['A', 'B'], {'C': ['A', 'B']}, slot)
    individuo = gen.risolvi()
    assert gen.verifica_vincoli(individuo)
    assert gen.calcola_fitness(individuo) == pytest.approx(_brute_force(gen, 'C'), abs=0.05)


def test_componenti_una_per_docente():
    slot = {c: [(1, 1, 'X'), (2, 1, 'Y')] for c in ('A', 'B', 'C')}
    gen = Gen(['A', 'B', 'C'], {'D1': ['A', 'B'], 'D2': ['C']}, slot)
    assert sorted(map(sorted, gen._componenti())) == [['A', 'B'], ['C']]


def test_settimana_corta_ora_a_rotazione():
    # un solo docente e un solo slot a settimana per due classi: l'ora va a turno, mai a entrambe
    gen = Gen(['A', 'B'], {'C': ['A', 'B']}, {c: [(w, 1, 'X') for w in (1, 2, 3, 4)] for c in 'AB'})
    assert gen.ore_per_classe == {'A': 2, 'B': 2}
    individuo = gen.risolvi()
    assert gen.verifica_vincoli(individuo) and len(individuo) == 4


def test_tempo_risparmiato_passa_ai_modelli_successivi(monkeypatch):
    gen = Gen(['A', 'B', 'C'], {'D1': ['A'], 'D2': ['B'], 'D3': ['C']}, {c: [(1, 1, 'X')] for c in 'ABC'})
    gen.tempo_max_secondi = 100
    orologio = [0]
    monkeypatch.setattr(generator_mod.time, 'monotonic', lambda: orologio[0])
    limiti = []

    def finto(classi, tempo):
        limiti.append(tempo)
        orologio[0] += 10 if classi == ['A'] else tempo  # il primo modello dimostra l'ottimo subito
        return {}

    gen._risolvi_componente = finto
    gen.risolvi()
    assert limiti == [100, 145, 145]


def test_docente_organico_copre_anche_lezioni_altrui():
    # C insegna in A (slot 'C') ed è disponibile anche per le ore degli altri: le perdite si distribuiscono
    slot = {'A': [(1, 1, 'C'), (2, 1, 'X'), (3, 1, 'Y'), (4, 1, 'Z')]}
    gen = Gen(['A'], {'C': ['A']}, slot)
    gen.docenti_civics_organico['A'] = {'C'}
    individuo = gen.risolvi()
    assert gen.verifica_vincoli(individuo)
    assert {gen.slots_by_key[k]['DOCENTE_SOSTITUITO'] for k in individuo} != {'C'}
    gen.allow_teacher_replace_self = False
    gen._precalcola_lookups()  # la settimana 1 (solo lezione di C) resta senza ora
    assert gen.ore_per_classe['A'] == 3
    assert all(gen.slots_by_key[k]['DOCENTE_SOSTITUITO'] != 'C' for k in gen.risolvi())


def test_penalita_eccesso_senza_soglie_piatte():
    # 15 settimane: P = 75%, X ha 15 ore (quota ideale 11,25); oltre la quota la penalità deve crescere sempre
    slot = {'A': [(w, 1, 'X') for w in range(15)] + [(w, 2, 'Y') for w in range(5)]}
    gen = Gen(['A'], {'C': ['A']}, slot)
    pen = [sum(gen._penalita_docente('A', 'X', l)[:2]) for l in range(12, 16)]
    assert all(b > a for a, b in zip(pen, pen[1:]))


def test_minimo_classe_uguale_all_ottimo_con_una_classe(monkeypatch):
    monkeypatch.setattr(generator_mod, 'PENALITA_RIPETIZIONE', {})  # il limite inferiore non le conosce
    slot = {'A': [(1, 1, 'X'), (2, 1, 'Y'), (3, 1, 'X'), (3, 2, 'Z'), (4, 1, 'Y')]}
    gen = Gen(['A'], {'C': ['A']}, slot)
    assert gen._minimo_classe('A') == pytest.approx(_brute_force(gen, 'C'), abs=0.05)


FISSA = {'docente_civics': 'C', 'classe': 'A', 'data': '05/10/2026', 'ora': 1}


def test_assegnazione_fissa_da_config_riserva_docente_e_ora():
    config = CalendarioConfig(assegnazioni_fisse=[dict(FISSA, docente_sostituito='X')])
    gen = Gen(['A', 'B'], {'C': ['A', 'B'], 'D': ['A', 'B']},
              {c: [(0, 1, 'X'), (0, 2, 'Y')] for c in 'AB'}, config.assegnazioni_fisse)
    individuo = gen.risolvi()
    assert individuo['A_0_1'] == 'C'
    assert len(individuo) == 2
    assert individuo.get('B_0_1') != 'C'
    assert gen.verifica_vincoli(individuo)


def test_assegnazione_fissa_prioritaria_nella_settimana_corta():
    gen = Gen(['A', 'B'], {'C': ['A', 'B']}, {c: [(0, 1, 'X')] for c in 'AB'},
              [dict(FISSA, classe='B')])
    assert gen.ore_per_classe == {'A': 0, 'B': 1}
    assert gen.risolvi() == {'B_0_1': 'C'}


def test_assegnazione_fissa_riduce_le_celle_utilizzabili_dalle_altre_classi():
    gen = Gen(['A', 'B'], {'C': ['A', 'B']},
              {'A': [(0, 1, 'X'), (0, 2, 'Y')], 'B': [(0, 1, 'X')]}, [FISSA])
    assert gen.ore_per_classe == {'A': 1, 'B': 0}
    assert gen.risolvi() == {'A_0_1': 'C'}


@pytest.mark.parametrize('individuo', [{}, {'A_0_2': 'C'}, {'A_0_1': 'D'}])
def test_verifica_vincoli_rifiuta_assegnazione_fissa_assente_o_diversa(individuo):
    gen = Gen(['A'], {'C': ['A'], 'D': ['A']},
              {'A': [(0, 1, 'X'), (0, 2, 'Y')]}, [FISSA])
    assert not gen.verifica_vincoli(individuo)


@pytest.mark.parametrize('assegnazioni', [
    {},
    [None],
    [{'classe': 'A'}],
    [dict(FISSA, classe='INESISTENTE')],
    [dict(FISSA, classe=[])],
    [dict(FISSA, docente_civics='INESISTENTE')],
    [dict(FISSA, docente_civics='D')],
    [dict(FISSA, docente_civics=[])],
    [dict(FISSA, data='31/02/2026')],
    [dict(FISSA, data=20261005)],
    [dict(FISSA, data='05/10/2025')],
    [dict(FISSA, data='06/10/2026')],
    [dict(FISSA, ora=0)],
    [dict(FISSA, ora=3)],
    [dict(FISSA, ora='1')],
    [dict(FISSA, ora=True)],
    [dict(FISSA, docente_sostituito='INESISTENTE')],
    [dict(FISSA, docente_sostituito=None)],
    [dict(FISSA, campo_errato='X')],
])
def test_assegnazioni_fisse_non_valide_terminano_con_errore(assegnazioni, caplog):
    with pytest.raises(SystemExit) as errore:
        Gen(['A', 'B'], {'C': ['A'], 'D': ['B']},
            {'A': [(0, 1, 'X'), (0, 2, 'Y')], 'B': [(0, 1, 'X')]}, assegnazioni)
    assert errore.value.code == 1
    assert 'assegnazion' in caplog.text.lower()


@pytest.mark.parametrize('seconda', [
    dict(FISSA, classe='B'),
    dict(FISSA, ora=2),
    dict(FISSA, docente_civics='D'),
])
def test_assegnazioni_fisse_in_conflitto_terminano_con_errore(seconda, caplog):
    with pytest.raises(SystemExit):
        Gen(['A', 'B'], {'C': ['A', 'B'], 'D': ['A']},
            {c: [(0, 1, 'X'), (0, 2, 'Y')] for c in 'AB'}, [FISSA, seconda])
    assert 'assegnazion' in caplog.text.lower()


def test_assegnazioni_fisse_identiche_non_raddoppiano_le_ore():
    gen = Gen(['A'], {'C': ['A']}, {'A': [(0, 1, 'X')]}, [FISSA, FISSA.copy()])
    assert gen.risolvi() == {'A_0_1': 'C'}


@pytest.mark.parametrize('docente_sostituito', ['X', 'C'])
def test_assegnazione_fissa_rispetta_disponibilita_e_sostituzione_propria(docente_sostituito):
    gen = Gen(['A'], {'C': ['A']}, {'A': [(0, 1, docente_sostituito)]})
    gen.disponibilita_civics['C']['LUN'][0] = False
    gen.allow_teacher_replace_self = False
    gen.assegnazioni_fisse = [FISSA]
    with pytest.raises(SystemExit):
        gen._precalcola_lookups()


def _sostituzioni(gen, individuo):
    # {docente sostituito: [settimane]} della classe A
    out = defaultdict(list)
    for k in individuo:
        out[gen.slots_by_key[k]['DOCENTE_SOSTITUITO']].append(gen.slots_by_key[k]['SETTIMANA'])
    return {d: sorted(w) for d, w in out.items()}


def test_stesso_docente_mai_sostituito_in_settimane_consecutive():
    # X e Y alternati: l'unica soluzione valida è X Y X Y (o Y X Y X)
    gen = Gen(['A'], {'C': ['A']}, {'A': [(w, o, d) for w in range(4) for o, d in ((1, 'X'), (2, 'Y'))]})
    individuo = gen.risolvi()
    assert gen.verifica_vincoli(individuo)
    for settimane in _sostituzioni(gen, individuo).values():
        assert all(b - a > 1 for a, b in zip(settimane, settimane[1:]))


def test_senza_alternative_il_vincolo_duro_rende_il_modello_impossibile(caplog):
    gen = Gen(['A'], {'C': ['A']}, {'A': [(w, 1, 'X') for w in range(3)]})
    with pytest.raises(SystemExit) as errore:
        gen.risolvi()
    assert errore.value.code == 1


def test_verifica_vincoli_rifiuta_sostituzioni_consecutive():
    gen = Gen(['A'], {'C': ['A']}, {'A': [(w, 1, 'X') for w in range(2)] + [(w, 2, 'Y') for w in range(2)]})
    assert not gen.verifica_vincoli({'A_0_1': 'C', 'A_1_1': 'C'})
    assert gen.verifica_vincoli({'A_0_1': 'C', 'A_1_2': 'C'})


@pytest.mark.parametrize('settimane, attesa', [((0, 1), None), ((0, 2), 5), ((0, 3), 2), ((0, 4), 0)])
def test_penalita_ripetizioni_graduata_con_la_distanza(settimane, attesa):
    gen = Gen(['A'], {'C': ['A']}, {'A': [(w, 1, 'X') for w in range(5)]})
    individuo = {f'A_{w}_1': 'C' for w in settimane}
    if attesa is None:
        assert gen._ripetizioni_consecutive(individuo)
    else:
        assert not gen._ripetizioni_consecutive(individuo)
        assert gen._penalita_ripetizioni(individuo) == attesa


def test_il_costo_soft_allontana_le_sostituzioni_dello_stesso_docente():
    # 5 settimane e 3 docenti: X e Y sono sostituiti due volte (Z una). Senza ripetizioni a distanza 2 la penalità
    # minima è 4: X e Y a distanza 3 (settimane 0-3 e 1-4)
    gen = Gen(['A'], {'C': ['A']}, {'A': [(w, o, d) for w in range(5) for o, d in enumerate('XYZ', 1)]})
    gen.gap_relativo = 1e-6  # la penalità è sotto la tolleranza di default (0,5% della fitness)
    individuo = gen.risolvi()
    assert gen.verifica_vincoli(individuo)
    assert gen._penalita_ripetizioni(individuo) == 4


def test_settimane_in_ordine_cronologico_anche_a_cavallo_d_anno():
    # i numeri ISO ripartono da 1 a gennaio: la distanza va misurata sull'ordine delle date, non sul numero
    gen = Gen(['A'], {'C': ['A']}, {'A': [(w, 1, 'X') for w in range(3)]})
    gen.slots_by_key['A_0_1']['SETTIMANA'], gen.slots_by_key['A_1_1']['SETTIMANA'] = 52, 1
    gen.slots_by_key['A_1_1']['DATA'] = gen.slots_by_key['A_0_1']['DATA'] + timedelta(weeks=1)
    gen.slots_by_key['A_2_1']['SETTIMANA'] = 2
    gen.slots_by_key['A_2_1']['DATA'] = gen.slots_by_key['A_0_1']['DATA'] + timedelta(weeks=2)
    gen._precalcola_lookups()
    assert gen._ripetizioni_consecutive({'A_0_1': 'C', 'A_1_1': 'C'})
    assert gen._penalita_ripetizioni({'A_0_1': 'C', 'A_2_1': 'C'}) == 5
