import json
from pathlib import Path


RADICE_PROGETTO = Path(__file__).resolve().parent.parent


def carica_configurazioni():
    with (RADICE_PROGETTO / "config_generazione.json").open(encoding="utf-8") as f:
        generazione = json.load(f)
    with (RADICE_PROGETTO / "config_scuola.json").open(encoding="utf-8") as f:
        scuola = json.load(f)
    if (not isinstance(generazione, dict) or not isinstance(scuola, dict)
            or not isinstance(scuola.get("cartelle"), dict)):
        raise ValueError("Configurazione non valida: attesi oggetti JSON per generazione e cartelle scuola.")
    cartelle = scuola["cartelle"]
    if any(not isinstance(cartelle.get(nome), str) or not cartelle[nome].strip()
           for nome in ("file_scuola", "calendario_generato")):
        raise ValueError("Configurazione non valida: i nomi delle cartelle devono essere stringhe non vuote.")
    return generazione, cartelle
