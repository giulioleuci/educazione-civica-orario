from src.configurazione import carica_configurazioni
from .calendario import CalendarioConfig, CalendarioGenerator


def main():
    parametri, cartelle = carica_configurazioni()
    parametri["cartella_input"] = cartelle["file_scuola"]
    parametri["cartella_output"] = cartelle["calendario_generato"]
    CalendarioGenerator(CalendarioConfig(**parametri)).genera_calendario()


if __name__ == "__main__":
    main()
