from datetime import datetime

from generator_mod import CalendarioGenerator


class _Righe:
    def iterrows(self):
        return enumerate([{'INIZIO': '24/12/2026', 'FINE': '06/01/2027'}])


def test_mezze_settimane_vacanze_unite():
    g = object.__new__(CalendarioGenerator)
    g.data_inizio, g.data_fine = datetime(2026, 12, 14), datetime(2027, 1, 22)
    g.chiusure_df = _Righe()
    g._init_date_scolastiche()
    k = g.settimana_di
    # lun-mer 21-23/12 + gio-sab 7-9/1 (giorni disgiunti) = una settimana; le altre restano separate
    assert k[datetime(2026, 12, 21)] == k[datetime(2027, 1, 7)]
    assert k[datetime(2026, 12, 14)] != k[datetime(2026, 12, 21)]
    assert k[datetime(2027, 1, 11)] != k[datetime(2027, 1, 7)]
