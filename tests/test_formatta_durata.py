from generator_mod import _formatta_durata


def test_formatta_durata():
    assert _formatta_durata(9) == "9s"
    assert _formatta_durata(309) == "5m 09s"
    assert _formatta_durata(3909.7) == "1h 05m 09s"
