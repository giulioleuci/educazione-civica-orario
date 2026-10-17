import os
import re
import pandas as pd


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

