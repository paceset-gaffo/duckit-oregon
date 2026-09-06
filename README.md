# duckit-oregon

Source data and analysis for Oregon waterfowl hunting.

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build_database.py
.venv/bin/jupyter lab
```

## Data

- [ODFW Sauvie Island waterfowl source archive](data/raw/odfw/sauvie-island/README.md):
  Raw harvest, blind, and reservation documents for the 2021-22 through
  2025-26 seasons.
- [Sauvie Island hunt-day weather](data/processed/sauvie-island/README.md):
  Opening-time and daily historical weather for every archived hunt date.
- [DuckDB analytical database](data/processed/README.md): Parsed unit harvest,
  weather, and source metadata with weekly and seasonal analytical views.
- [Football schedules](data/processed/sports/README.md): Archived and
  normalized Oregon, Oregon State, and Seahawks schedules for 2021-2025.

## Analysis

- [Weekly unit harvest trends](notebooks/01_weekly_unit_harvest.ipynb):
  Five-season comparison of unit harvest efficiency, including the Racetrack
  hypothesis.
- [Football schedules and hunting](notebooks/02_sports_schedule_comparison.ipynb):
  Oregon, Oregon State, and Seahawks game dates compared with reservation
  demand, hunter turnout, and harvest.