# AGENTS.md

Single-file Python app: `calendario-ed-civ-generator.py` is the whole program (genetic-algorithm
scheduler for civics substitution hours). No package, no CLI, no config file, no CI, no
requirements.txt/lint/typecheck setup. Comments, log messages and docs are in Italian — keep new
comments/logs in Italian too.

## Commands

- Install deps (nothing is vendored): `pip install pandas numpy openpyxl`
  (`numpy` is imported but unused by the script; only `pandas` + `openpyxl` really matter.)
- Tests: `python3 -m pytest tests -q` → 67 tests, <1s. pytest is **not** installed in this
  environment (`pip install pytest` first). Works from the repo root; no pytest config exists.
- One file / one test: `python3 -m pytest tests/test_selezione.py -q`, add `-k <name>` / `-x`.
- `python3 run_test.py` runs **only** `tests/test_security.py`, not the whole suite.
- Ad-hoc perf scripts: `python3 benchmark.py`, `python3 test_perf.py` (creates and deletes
  `./test_output`), `python3 measure_date_parsing.py`.

## Running the generator

- Parameters live in the `if __name__ == "__main__":` block at the bottom of
  `calendario-ed-civ-generator.py:1048` — there are no CLI flags, so changing a run means editing
  that block.
- The 4 input CSVs (`classes.csv`, `civics_teachers.csv`, `availability.csv`, `closures.csv`) are
  read with bare relative paths from the **current working directory** (`load_data`), so copy
  `examples/*.csv` into the repo root to smoke-test. Missing file → log error + `SystemExit(1)`.
  `examples/*.csv` only has 2 classes / 2 teachers: usable to verify the pipeline runs, not that
  results are meaningful.
- `ore_tot_civics` must be ≤ the number of school weeks: `verifica_vincoli` hard-requires
  *exactly* `ore_tot_civics` hours per class and max 1 hour/class/week. Individuals that violate it
  are discarded, and `select_and_generate_new_population` loops until the population is refilled →
  an infeasible config hangs instead of erroring.
- Outputs (`calendar.csv`, `teachersLost.csv`, `orario_classi.xlsx`, `orario_docenti.xlsx`, plus
  `generation_<n>/` every `save_interval` generations) go to `cartella_output`, forced to a
  basename by `_sanitize_output_path`.

## Verified environment gotcha: Python 3.14 + multiprocessing

On this machine `python3` is 3.14, where the default `multiprocessing` start method is
`forkserver`. Every `multiprocessing.Pool(..., initargs=(self,))` then pickles the generator
instance and dies with:
`PicklingError: Can't pickle local object <function ..._precalcola_lookups.<locals>.<lambda>>`
(from the `defaultdict(lambda: ...)` at `calendario-ed-civ-generator.py:535`; the module-level
`init_worker`/`*_helper` functions also need an importable module name).

- Fix when running: `multiprocessing.set_start_method("fork")` before building the generator
  (verified: full run then completes and writes all outputs), or use Python ≤ 3.13 where `fork` is
  the Linux default.
- Do not drive the generator by importing it through `SourceFileLoader`/`importlib` (what
  `benchmark.py` and `test_perf.py` do) — the worker helpers are unpicklable in that setup.
- The test suite never builds a Pool, so it is unaffected.

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
- Known inconsistencies (don't "fix" silently, they may be relied on):
  - `allow_teacher_replace_self` is honoured only in `mutazione()`; `genera_individuo_base()`
    always allows a civics teacher to cover their own lesson.
  - `CalendarioConfig.num_varianti` is stored and printed but never used.
  - README says a subfolder is written for every generation; the code only writes
    `generation_<n>` every `save_interval` generations (default 50).