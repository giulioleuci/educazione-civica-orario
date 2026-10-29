# CLAUDE.md

Python app: generator modules live in `src/generatore/`, EDT/ALDO conversion in
`src/importazione_edt_aldo/`, and shared configuration loading in `src/configurazione.py`.
There is no CI, no
requirements.txt/lint/typecheck setup. Comments, log messages and docs are in Italian — keep new
comments/logs in Italian too.

## Commands

- Install deps (nothing is vendored): `pip install pandas numpy openpyxl ortools`
  (`numpy` is only used inside `_minimo_classe`, imported locally there; `pandas` + `openpyxl` do the rest.)
- Tests: `python3 -m pytest tests -q` → ~100 tests, ~3s. pytest is **not** installed in this
  environment (`pip install pytest` first). Works from the repo root; no pytest config exists.
- One file / one test: `python3 -m pytest tests/test_cpsat.py -q`, add `-k <name>` / `-x`.
- `python3 run_test.py` runs **only** `tests/test_security.py`, not the whole suite.
- Ad-hoc perf scripts: `python3 benchmark.py`, `python3 test_perf.py` (creates and deletes
  `./test_output`), `python3 measure_date_parsing.py`.

## Running the generator

- Generation parameters live in `config_generazione.json`; folder names live in
  `config_scuola.json`. Run the generator with `python3 -m src.generatore.main`.
- The 4 input CSVs (`classes.csv`, `civics_teachers.csv`, `availability.csv`, `closures.csv`) are
  read from the `file_scuola` folder in `config_scuola.json` (default `FILE_SCUOLA`). Copy
  `examples/*.csv` into that folder to smoke-test. Missing file → log error + `SystemExit(1)`.
  `examples/*.csv` only has 2 classes / 2 teachers: usable to verify the pipeline runs, not that
  results are meaningful.
- No total-hours parameter: target is 1 civics hour per class per school week. In short weeks (closures) the
  civics teachers cannot cover all classes, so `_assegna_settimane` (called by `_precalcola_lookups`) computes per
  week a maximum matching classes → (date, hour, teacher) cells and drops the hour from classes with fewer lost weeks so far;
  result = `settimane_classe` / `ore_per_classe`, and the model requires exactly 1 hour in those weeks, 0 elsewhere.
- `SETTIMANA` negli slot = chiave `settimana_di` (da `_init_date_scolastiche`): settimane parziali consecutive senza giorni
  della settimana in comune (es. mezza settimana prima + mezza dopo le vacanze) sono una sola settimana (1 ora in totale).
- Generation parameters are loaded from `config_generazione.json`; school folder names come from
  `config_scuola.json`.
- Outputs (`calendar.csv`, `teachersLost.csv`, `orario_classi.xlsx`, `orario_docenti.xlsx`) go to the
  `calendario_generato` folder in `config_scuola.json` (default `CALENDARIO_GENERATO`), forced to a
  basename by `_sanitize_output_path`.

## Solver

- No `multiprocessing` any more: `risolvi()` solves one CP-SAT model per group of classes sharing civics
  teachers (`_componenti()`, normally one per teacher); `num_cores` = solver workers,
  `tempo_max_secondi` × n. models = total time budget; time left by a model that proves optimality is split among the remaining ones (best feasible solution is used, not necessarily optimal).
- Objective = fitness × `SCALA_OBIETTIVO`; penalties come from `_penalita_docente` (shared with
  `calcola_fitness`), variance is rounded to 0.1% points (`DECIMI`) → ~0.1 fitness difference vs
  `calcola_fitness` is expected.
- Fairness: `_penalita_docente` penalises hours lost above the proportional share (`ore_totali * P / 100`)
  quadratically (`PESO_ECCESSO`), no flat tiers (flat tiers made the teacher with most hours lose ~2× P).
  Teachers with no candidate slot (lessons never in a civics DISPOS cell) lose 0 by data, so the others
  inevitably lose > P: ratio 1.1–1.6 is the floor, not a bug.
- Ripetizioni: lo stesso `DOCENTE_SOSTITUITO` nella stessa classe non può esserlo in settimane consecutive (vincolo duro,
  in `_risolvi_componente` e `verifica_vincoli`); a distanza 2 e 3 settimane c'è una penalità (`PENALITA_RIPETIZIONE`, in
  `calcola_fitness` e nel modello come booleane `z`, fuori dalla fetta di costo usata dal limite inferiore). Le distanze usano
  `indice_settimana` (ordine cronologico, il numero ISO riparte a gennaio) sulle settimane del calendario, non sulle sole
  settimane con ora. Classe con un solo docente sostituibile (o assegnazioni fisse che violano il vincolo) → infeasible.
- `_minimo_classe` = exact per-class minimum ignoring conflicts (DP), added as a lower-bound constraint per
  class. Without it CP-SAT's bound stays far below the optimum (e.g. 85 vs 278) and the gap never closes. It must
  use the same cost as the model (`_penalita_docente` tables + free-mean variance), else the bound is invalid.
- `_risolvi_componente` stops at `gap_relativo` (default 0.1%); if the gap stays above it, up to `TENTATIVI_MAX`
  attempts with a different seed and the best solution as hint. In practice only tight instances need the
  restarts (demand ≈ usable cells of the civics teacher); on the real data the first attempt proves the gap in ~20 s.
- No solution (infeasible or timeout without incumbent) → log error + `SystemExit(1)`.
- The old `fork`/forkserver pickling problem on Python 3.14 is gone.

## Test harness conventions (`tests/conftest.py`)

- `conftest.py` imports `src.generatore.calendario` and registers it as `generator_mod`; tests use
  `from generator_mod import ...`.
- `conftest.py` replaces `pandas`, `numpy`, `openpyxl` in `sys.modules` for the whole session, so
  tests never touch real pandas. A new third-party import in a module needs a stub there, and
  real-pandas behaviour is only covered by the ad-hoc perf scripts.
- Tests subclass `CalendarioGenerator` and override `__init__` with `pass` to bypass
  `load_data` / `initialize_variables`, setting the attributes they need by hand.

## Invariants worth preserving

- Security helpers at the top of the script (`_sanitize_output_path`, `_sanitize_for_logging`,
  `_sanitize_sheet_name`, `_sanitize_for_excel`) plus `tests/test_security.py` and
  `tests/test_load_data_security.py`: keep sanitization when touching output paths, log messages,
  Excel sheet names, or cells written to CSV/Excel.
- Dates are `%d/%m/%Y` everywhere (input CSVs, `calendar.csv`, `closures.csv`).
  `genera_file_excel` converts `DATA` strings → `datetime`, so the `genera_orario_*` functions must
  receive datetimes (as `test_perf.py` does) — they call `_get_week_range` on it.
- Fitness is minimised (lower is better) and sums deviation × 10, variance × 5, penalties, and the quadratic excess term.
- `allow_teacher_replace_self` is honoured by `_docenti_disponibili` (used by the model): it only controls
  whether a civics teacher may cover their own lesson; lessons of other teachers always follow
  `availability.csv`, also for civics teachers who teach in the class.
- `CalendarioConfig.num_varianti` is stored and printed but never used (don't "fix" silently).
- Tests: `conftest.py` mocks numpy/pandas but ortools needs the real ones → `test_cpsat.py` swaps them
  back in via `real_modules`.
