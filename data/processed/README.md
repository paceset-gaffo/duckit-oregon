# DuckDB analytical database

`duckit_oregon.duckdb` is the reproducible analytical database for the
project. Build it from the archived source files with:

```sh
python3 scripts/build_database.py
```

## Tables

- `harvest_daily_unit`: 5,376 unit-date records covering 21 units, 256 hunt
  dates, and five seasons.
- `hunt_day_weather`: Opening-time and daily weather for all 256 hunt dates.
- `odfw_source_manifest`: Metadata, source URLs, and checksums for all 302 ODFW
  documents.
- `reservation_first_choice_application`: First-choice applicant counts and
  reservations available for every choice and date in the 35 reservation
  reports. Oak Island blind choices 1-6 remain separate.
- `football_game`: Oregon, Oregon State, and Seattle Seahawks regular- and
  postseason games for the 2021 through 2025 football seasons.
- `sports_source_manifest`: Source URLs and checksums for the 30 archived ESPN
  schedule responses.
- `weather_raw_response`: The five original Open-Meteo API responses as JSON.
- `database_metadata`: Build and methodology metadata.

## Views

- `weekly_unit_harvest`: Hunter-weighted unit results by season week.
- `season_unit_harvest`: Hunter-weighted unit results by season.
- `all_seasons_unit_harvest`: Hunter-weighted unit results across five
  seasons.
- `harvest_with_weather`: Unit harvest records joined to hunt-day weather.
- `reservation_report_sources`: The 35 archived first-choice application
  reports.
- `reservation_first_choice_demand`: Application rows with applicants per
  available reservation.
- `sports_on_hunt_date`: Football games whose Pacific date matches a hunt date.
- `hunt_day_sports_comparison`: One record per hunt date with application
  demand, harvest totals, efficiency, and team game-day flags.

The unit extraction uses ODFW's compiled duck table for 2021-22 through
2024-25 and the first-page unit summary in each 2025-26 daily report. The
compiled source explicitly identifies its values as duck harvest and avoids
ambiguity in older daily reports that labeled the same field `BIRDS`.

`ducks_per_hunter` is always recalculated from summed ducks and hunters.
Averages across dates, weeks, or seasons should therefore use
`SUM(ducks) / SUM(hunters)`, not an unweighted average of daily rates.
