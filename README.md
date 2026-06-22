# SPM Torres — Sequential Pattern Mining over Moodle logs

A research library that mines **frequent event sequences** from student activity
traces (Moodle LMS logs) and computes metrics (support, grades, time spans,
Jaccard diversity) across different **simplification scenarios**.

The core idea: each student produces a sequence of events within an activity
(e.g. `assignment_vis → assignment_try → assignment_sub`). The pipeline catalogs
and simplifies these sequences in 24 different ways, mines the frequent patterns
(PrefixSpan), and computes metrics that allow comparing the scenarios.

Two courses were studied in the master's research (**2060** and **2065**), but the
code is generic — it works for any course/activity as long as the input CSVs
follow the format described in [Database](#database).

The project is an installable **library** (`spm`), usable in two ways:

1. **Importing functions** in Python — operating on your own data in memory
   (`simplify` → `mine` → `metrics`).
2. **Through the CLI** `spm` (subcommands `simplify` / `mine` / `metrics` / `pipeline`).

---

## Table of contents

- [Installation](#installation)
- [Project structure](#project-structure)
- [Database](#database)
- [Library usage (Python)](#library-usage-python)
- [CLI usage (`spm`)](#cli-usage-spm)
- [Generated outputs](#generated-outputs)
- [The 24 scenarios](#the-24-scenarios)
- [Configuration and legacy scripts](#configuration-and-legacy-scripts)

---

## Installation

Requires **Python ≥ 3.10**. A virtual environment is recommended:

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -e .            # installs the library + the `spm` command
```

Optional extras:

```bash
pip install -e ".[viz]"     # matplotlib/seaborn — only for the legacy plotting scripts
pip install -e ".[gsp]"     # gsppy — GSP algorithm (spm.mining.gsp_mining)
pip install -e ".[dev]"     # black, pytest
```

Core runtime dependencies: **`pandas`**, **`numpy`**, **`prefixspan`**.
Everything else is optional.

> **Note (external NTFS drive):** create the `.venv` with `python -m venv` (real
> symlinks). Copies of a `.venv` made by file managers on filesystems without
> symlink support may break the binaries ("exec format error").

---

## Project structure

```
.
├── src/spm/              # the library
│   ├── __init__.py       # public API (simplify, mine, metrics, run_*)
│   ├── simplification.py # CORE: transforms + simplify()  (preprocessing)
│   ├── mining.py         # CORE: mine()  (PrefixSpan)
│   ├── metrics.py        # CORE: metrics()  (Jaccard, supports, grades)
│   ├── io.py             # JSON/CSV reading/writing and consolidated reports
│   ├── pipeline.py       # file-based orchestrators: run_simplification/mining/metrics + run_pipeline
│   ├── cli.py            # `spm` command (argparse, subcommands)
│   ├── sceneries.py      # SINGLE SOURCE: the 24-scenario matrix (SCENERY_DEFINITIONS)
│   ├── config.py         # legacy: knobs used only by scripts/mining.py and viz/*
│   └── paths.py          # directory layout (data/raw, outputs/)
├── scripts/              # legacy scripts (NOT part of the library)
│   ├── mining.py, order.py, scenario_metrics.py, support_percentage.py
│   └── viz/              # plots (analysis, plot_patterns, comparison_boxplots)
├── configs/              # per-experiment parameters (course_2060.yaml, course_2065.yaml)
├── data/raw/{course}/    # raw Moodle CSVs (NOT versioned — see data/README.md)
├── outputs/              # everything generated (gitignored)
│   ├── sceneries/{course}/{activity}/
│   ├── mining_results/{course}/{activity}/
│   ├── results/{course}/{activity}/{json,csv}/
│   └── figures/
├── notebooks/            # exploration (.ipynb, gitignored)
├── docs/                 # CODE_ORGANIZATION, JACCARD_METRICS, OPTIMIZATIONS (gitignored)
├── pyproject.toml        # packaging + the `spm` entry point
└── requirements.txt
```

---

## Database

The raw Moodle CSVs are **not versioned** (they contain student data). Place each
course's files under `data/raw/{COURSE}/`, named as follows:

```
data/raw/{COURSE}/
├── event_mapping.csv                       (required)
├── see_course{COURSE}_logs_filtered.csv    (required)
├── see_course{COURSE}_quiz_list.csv        (required — defines the activity dates)
└── see_course{COURSE}_quiz_grades.csv      (optional — enables grade metrics)
```

Example: `data/raw/2060/see_course2060_logs_filtered.csv`. These files are the
**only input** to the pipeline; everything under `outputs/` is generated from them.

### 1. `event_mapping.csv` — event vocabulary

Maps each Moodle log triple `(component, action, target)` to an **event class**
used in the sequences.

| Column      | Type   | Description                                                       |
|-------------|--------|-------------------------------------------------------------------|
| `component` | string | Moodle component (`core`, `mod_quiz`, `mod_forum`, …)             |
| `action`    | string | Action verb (`viewed`, `started`, `submitted`, `created`, …)     |
| `target`    | string | Action object (`course`, `attempt`, `course_module`, …)          |
| `class`     | string | **Event class** assigned to the triple (see vocabulary below)    |

Event classes in use (the suffix is added by the simplification techniques):

`course_vis`, `resource_vis`, `assignment_vis`, `assignment_try`,
`assignment_sub`, `forum_vis`, `forum_participation`, `forum_followup`,
`message_sent`, `message_read`.

> The `assignment_vis` → `assignment_try` → `assignment_sub` events (view, attempt,
> submit the activity) are the focus of *coalescing* and of the sequence
> extraction (the pipeline trims back from the last submission).

### 2. `see_course{COURSE}_logs_filtered.csv` — event log

One row per recorded event. This is the main input table.

| Column          | Type  | Used?  | Description                                                     |
|-----------------|-------|:------:|-----------------------------------------------------------------|
| `id`            | int   |   •    | Log line identifier (used as the index)                         |
| `userid`        | int   |   ✔    | Student identifier                                              |
| `t`             | int   |   ✔    | Unix timestamp of the event                                     |
| `component`     | str   |   ✔    | Component — matched against `event_mapping`                     |
| `action`        | str   |   ✔    | Action — matched against `event_mapping`                        |
| `target`        | str   |   ✔    | Target — matched against `event_mapping`                        |
| `assignment_id` | int   |   ✔    | ID of the activity the event refers to (empty for general events) |
| `objectid`, `objecttable`, `courseid`, `relateduserid`, `extra_info`, `crud` | — | | Extra Moodle fields (unused by the core) |

An activity is sliced out by filtering on the time window
(`t_open ≤ t ≤ t_close`) **and** on `assignment_id` (`core`/`mod_page` events are
kept as navigation context).

### 3. `see_course{COURSE}_quiz_list.csv` — activity catalog

Defines each activity and, most importantly, **its dates** (from which the
pipeline derives the time window — you don't type dates).

| Column       | Type  | Description                                                       |
|--------------|-------|-------------------------------------------------------------------|
| `id`         | int   | The activity's **`assignment_id`** (this is what goes in `--assignment-id`) |
| `course_id`  | int   | Course                                                           |
| `name`       | str   | Name (e.g. `Atividade 2`)                                        |
| `t_open`     | int   | Open time (Unix) → becomes `initial_date`                        |
| `t_close`    | int   | Close time (Unix) → becomes `final_date`                         |
| `hidden`     | int   | Hidden flag                                                      |
| `max_grade`  | float | Maximum grade                                                   |
| `grade_pass` | float | Passing grade                                                   |

### 4. `see_course{COURSE}_quiz_grades.csv` — per-student grades (optional)

Enables the grade metrics (`grade_avg`, `grade_median`, …) and `--use-split`
(splitting patterns by high/low performance). Without this file the pipeline still
runs, but with no grade information.

| Column          | Type  | Description                                                |
|-----------------|-------|------------------------------------------------------------|
| `course_id`     | int   | Course                                                     |
| `id`            | int   | `assignment_id` (matches `quiz_list.id`)                   |
| `timeopen`      | int   | Open time (Unix)                                           |
| `timeclose`     | int   | Close time (Unix)                                          |
| `max_grade`     | float | Activity's maximum grade                                   |
| `student_grade` | float | Grade obtained by the student                              |
| `userid`        | int   | Student (matches `logs_filtered.userid`)                  |

### Activity ↔ `assignment_id`

The CLI and the orchestrators derive the `assignment_id` from
`(course, activity)` using the `spm.pipeline.ASSIGNMENT_IDS` map:

```python
ASSIGNMENT_IDS = {
    2060: [12841, 12842, 12843, 12844],   # activity 1..4
    2065: [12874, 12875, 12876],          # activity 1..3
}
```

For another course (or to override), pass `--assignment-id` on the CLI or the
`assignment_id=` argument to the functions.

---

## Library usage (Python)

The **core** API works in memory: you pass your own `DataFrame`s and get the
results back, chaining the steps.

```python
import pandas as pd
from spm import simplify, mine, metrics, SCENERY_DEFINITIONS
from spm.simplification import get_dates

# 1. Load the data (yours, from wherever)
base    = "data/raw/2060"
logs    = pd.read_csv(f"{base}/see_course2060_logs_filtered.csv", index_col="id")
mapping = pd.read_csv(f"{base}/event_mapping.csv")
grades  = pd.read_csv(f"{base}/see_course2060_quiz_grades.csv")
quiz    = pd.read_csv(f"{base}/see_course2060_quiz_list.csv")

# 2. Derive the activity's time window from the quiz CSV
assignment_id = 12842
initial_date, final_date = get_dates(quiz, assignment_id)

# 3. Simplify → mine → compute metrics, for one scenario
scenario = SCENERY_DEFINITIONS[1]                       # scenario "1-first"
seqs = simplify(logs, mapping, scenario,                # -> list of per-user sequences
                assignment_id=assignment_id,
                initial_date=initial_date, final_date=final_date,
                grades_df=grades)
patterns       = mine(seqs, minsup=0.08)                # -> dict of frequent patterns
final, general = metrics(patterns, seqs,                # -> (per-pattern detail, summary)
                         scenery=scenario["path"], minsup=0.08)
```

### Core functions

| Function   | Signature (abridged)                                                                  | Returns |
|------------|---------------------------------------------------------------------------------------|---------|
| `simplify` | `(logs_df, mapping_df, scenario, *, assignment_id, initial_date, final_date, grades_df=None, split_grade=False)` | list of per-user sequences (or `(high, low)` if `split_grade`) |
| `mine`     | `(sequences, minsup=0.08)`                                                            | dict of frequent patterns |
| `metrics`  | `(mining_results, sequences, *, scenery="0", minsup=0.08)`                            | `(final_result, general_info)` |

### Orchestrators (file-based)

To reproduce the experiment reading from `data/raw/` and writing to `outputs/`:

```python
from spm import run_pipeline   # or run_simplification / run_mining / run_metrics

run_pipeline(course=2060, activity=2, total_sequences=11974)
```

`run_pipeline(course, activity, assignment_id=None, *, minsup=0.08,
total_sequences=11974.0, use_split=False)` runs the three steps in sequence for
**all 24 scenarios**.

---

## CLI usage (`spm`)

The `spm` command assumes the **repository root** as the working directory
(input/output paths are relative to it). The `assignment_id` is derived from
`(course, activity)`; override it with `--assignment-id`.

```bash
# Full pipeline (the 3 steps, all scenarios)
spm pipeline --course 2060 --activity 2 --total-sequences 11974

# Or step by step:
spm simplify --course 2060 --activity 2 --assignment-id 12842
spm mine     --course 2060 --activity 2 --minsup 0.08
spm metrics  --course 2060 --activity 2 --minsup 0.08 --total-sequences 11974
```

Main flags (see `spm <subcommand> --help`):

| Flag                       | Steps         | Default                 | Meaning |
|----------------------------|---------------|-------------------------|---------|
| `-co`, `--course`          | all           | —                       | Course number |
| `-act`, `--activity`       | all           | —                       | Activity number |
| `-id`, `--assignment-id`   | pipeline/simplify | derived             | Override the assignment_id |
| `-ms`, `--minsup`          | pipeline/mine/metrics | `0.08`          | PrefixSpan minimum support (fraction) |
| `-ts`, `--total-sequences` | pipeline/metrics | `11974`              | Reference total for the support percentage |
| `--use-split` / `--split-grade` | —        | off                     | Generate/use `_high`/`_low` variants by grade |
| `--logs`/`--grades`/`--quiz`/`--mapping` | simplify | derived from `data/raw/{course}/` | Input CSV paths |
| `--sceneries-dir`/`--mining-dir`/`--out-dir` | per step | `outputs/...` | Input/output roots |

> **`--total-sequences`** is the population size used as 100% when converting the
> sequence support to a percentage (`s_support_percentage`). Use the total number
> of student sequences considered in the experiment (11974 for course 2060).

---

## Generated outputs

Everything goes under `outputs/` (gitignored), per course/activity:

```
outputs/
├── sceneries/{course}/{activity}/{scenery}.json          # preprocessed sequences
├── mining_results/{course}/{activity}/{scenery}_mining.json  # frequent patterns
└── results/{course}/{activity}/
    ├── json/{scenery}.json     # detailed per-pattern metrics
    ├── csv/{scenery}.csv       # same, as CSV (one row per pattern)
    ├── general_info.csv        # 1 row per scenario (experiment summary)
    ├── total.csv               # all patterns of all scenarios
    └── top_k.csv               # top-K most frequent patterns per scenario
```

With `--use-split`, scenarios get `_high`/`_low` suffixes and the simplification
step writes into `sceneries/{course}/{activity}/split_grade/`.

### `general_info.csv` (per-scenario summary)

Columns (separator `;`): `scenery`, `minsup`, `max_grade`, `total_sequences`
(number of patterns), `time_span_in_days`, `longest_pattern_length`,
`shortest_pattern_length`, `average_pattern_length`, `longest_sequence_length`,
`shortest_sequence_length`, `average_sequence_length`, `jaccard_diversity`,
`avg_jaccard_distance`, `elapsed_time`, `i_support`, `s_support`,
`s_support_percentage`, `s_support_std_percentage`.

### Per-scenario CSV (one row per pattern)

Columns: `sequence_size`, `sequence` (events joined by `>`), `total`,
`total_time_span`, `avg_time_span`, `i_support`, `s_support`, `ids` (number of
sequences containing the pattern), `grade_avg`, `grade_avg_deviation`,
`grade_median`, `grade_mode`, `max_grade`, `jaccard_distance`.

---

## The 24 scenarios

Each scenario is a fixed combination of the simplification techniques applied to
the sequences. The matrix is the **experiment definition** and lives in
`src/spm/sceneries.py` (`SCENERY_DEFINITIONS`, index = scenario number):

| Flag                   | Technique |
|------------------------|-----------|
| `multilevel`           | Splits each event into a `_START`/`_END` phase relative to the midpoint of the period |
| `spell`                | Compresses long runs into `_SOME` (3–5) / `_MANY` (>5) |
| `coalescing_repeating` | Removes consecutive identical events |
| `coalescing_hidden`    | Removes implicit transitions (e.g. `vis`→`try`, `try`→`sub`) |
| `tf` (temporal folding)| Splits the sequence into sessions by gaps > 1h |

Scenario `0-zero` is the baseline (no technique). The others combine the flags
above — see the full table in the file.

---

## Configuration and legacy scripts

- The **24-scenario matrix** is a fixed experiment definition in
  `src/spm/sceneries.py`. Edit it only to change the scenarios themselves.
- The `(course, activity) → assignment_id` map lives in `spm.pipeline.ASSIGNMENT_IDS`.
- `src/spm/config.py` remains only as a **legacy** shim for the scripts outside the
  library (`scripts/mining.py`, `scripts/viz/*`), which still import it. The YAMLs
  in `configs/` document each run's parameters.
- The files under `scripts/` (plots and utilities) are **not part of the library**
  and may depend on the `viz`/`gsp` extras.
