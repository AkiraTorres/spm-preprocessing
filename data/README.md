# Data

The raw Moodle CSVs are **not versioned** (they contain student data). Place each
course's files under `data/raw/{COURSE}/`:

```
data/raw/{COURSE}/
├── event_mapping.csv                       (required)
├── see_course{COURSE}_logs_filtered.csv    (required)
├── see_course{COURSE}_quiz_list.csv        (required — defines the activity dates)
└── see_course{COURSE}_quiz_grades.csv      (optional — enables grade metrics and --use-split)
```

Example: `data/raw/2060/see_course2060_logs_filtered.csv`.

These four files are the **only input** to the pipeline; everything under
`outputs/` is generated from them. The column layout of each file is documented in
the [Database](../README.md#database) section of the main README.

> Other Moodle exports (e.g. `resource_list`, `timeline`, `user_list`) may coexist
> here, but are **not used** by the pipeline core.
