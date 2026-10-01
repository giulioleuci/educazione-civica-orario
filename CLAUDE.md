# CLAUDE.md

Single-file Python app: `calendario-ed-civ-generator.py` is the whole program (OR-Tools CP-SAT
scheduler for civics substitution hours). No package, no CLI, no config file, no CI, no
requirements.txt/lint/typecheck setup. Comments, log messages and docs are in Italian — keep new
comments/logs in Italian too.

## Commands

- Install deps (nothing is vendored): `pip install pandas numpy openpyxl ortools`
  (`numpy` is imported but unused by the script; only `pandas` + `openpyxl` really matter.)
- Tests: `python3 -m pytest tests -q` → 53 tests, <1s. pytest is **not** installed in this
  environment (`pip install pytest` first). Works from the repo root; no pytest config exists.
- One file / one test: `python3 -m pytest tests/test_cpsat.py -q`, add `-k <name>` / `-x`.
- `python3 run_test.py` runs **only** `tests/test_security.py`, not the whole suite.
- Ad-hoc perf scripts: `python3 benchmark.py`, `python3 test_perf.py` (creates and deletes
  `./test_output`), `python3 measure_date_parsing.py`.

## Running the generator

- Parameters live in the `if __name__ == "__main__":` block at the bottom of
  `calendario-ed-civ-generator.py` (end of file) — there are no CLI flags, so changing a run means editing
  that block.
- The 4 input CSVs (`classes.csv`, `civics_teachers.csv`, `availability.csv`, `closures.csv`) are
  read with bare relative paths from the **current working directory** (`load_data`), so copy
  `examples/*.csv` into the repo root to smoke-test. Missing file → log error + `SystemExit(1)`.
  `examples/*.csv` only has 2 classes / 2 teachers: usable to verify the pipeline runs, not that
  results are meaningful.
- `ore_tot_civics` must be ≤ the number of school weeks: the model hard-requires
  *exactly* `ore_tot_civics` hours per class and max 1 hour/class/week; an infeasible config makes
  CP-SAT report INFEASIBLE and the script exits with an error.
- Outputs (`calendar.csv`, `teachersLost.csv`, `orario_classi.xlsx`, `orario_docenti.xlsx`) go to `cartella_output`, forced to a
  basename by `_sanitize_output_path`.

## Solver

- No `multiprocessing` any more: `risolvi()` solves one CP-SAT model per group of classes sharing civics
  teachers (`_componenti()`, normally one per teacher); `num_cores` = solver workers,
  `tempo_max_secondi` × n. models = total time budget; time left by a model that proves optimality is split among the remaining ones (best feasible solution is used, not necessarily optimal).
- Objective = fitness × `SCALA_OBIETTIVO`; penalties come from `_penalita_docente` (shared with
  `calcola_fitness`), variance is rounded to 0.1% points (`DECIMI`) → ~0.1 fitness difference vs
  `calcola_fitness` is expected.
- No solution (infeasible or timeout without incumbent) → log error + `SystemExit(1)`.
- The old `fork`/forkserver pickling problem on Python 3.14 is gone.

## Test harness conventions (`tests/conftest.py`)

- The script filename contains hyphens, so it cannot be imported by name. `conftest.py` loads it via
  `importlib` and registers it as `generator_mod`; all test files do `from generator_mod import ...`.
  Never import `calendario-ed-civ-generator.py` directly in a test.
- `conftest.py` replaces `pandas`, `numpy`, `openpyxl` in `sys.modules` for the whole session, so
  tests never touch real pandas. A new third-party import in the script needs a stub there, and
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
- Fitness is minimised (lower is better) and sums deviation × 10, variance × 5, and penalties.
- `allow_teacher_replace_self` is honoured by `_docenti_disponibili` (used by the model): a teacher who
  teaches in the class may only cover their own lesson, others follow `availability.csv`.
- `CalendarioConfig.num_varianti` is stored and printed but never used (don't "fix" silently).
- Tests: `conftest.py` mocks numpy/pandas but ortools needs the real ones → `test_cpsat.py` swaps them
  back in via `real_modules`.
