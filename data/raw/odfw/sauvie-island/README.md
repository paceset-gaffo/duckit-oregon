# ODFW Sauvie Island waterfowl source archive

Raw public documents downloaded from the Oregon Department of Fish and
Wildlife (ODFW) on September 6, 2026. The archive covers the five completed
waterfowl seasons from 2021-22 through 2025-26.

## Contents

- `YYYY-YY/harvest/daily/`: One ODFW daily harvest PDF per published hunt
  date. Reports include hunters and harvest by area, unit, and numbered blind.
- `YYYY-YY/harvest/season-summary-by-unit-and-blind.pdf`: ODFW's compiled
  blind-level season summary where one was published (2023-24 through
  2025-26).
- `YYYY-YY/reservations/`: Hunt periods A-G, showing first-choice application
  counts by date and requested hunt unit.
- `references/`: Blind/unit maps, reservation capacity, the multi-season daily
  unit report, and ODFW's 50-year harvest comparison.
- `manifest.csv`: Source URL, local path, byte size, and SHA-256 checksum for
  every PDF.

There are 256 daily harvest reports:

| Season | Reports |
| --- | ---: |
| 2021-22 | 51 |
| 2022-23 | 52 |
| 2023-24 | 51 |
| 2024-25 | 51 |
| 2025-26 | 51 |

There are also 35 reservation reports (seven periods for each of five
seasons), three season summaries, and eight reference documents.

## Interpretation note

Reservation applicants select a hunt unit, not a numbered blind. Several
units—Hunt, Johnson, Mudhen, Oak Island, and Racetrack—contain designated
blinds. Successful applicants receive a check-in sequence number and choose an
available blind on the hunt date. The public application reports can therefore
be correlated with demand for blind-bearing units, while the harvest reports
show which numbered blinds were used and their results. They do not provide a
direct application-to-numbered-blind assignment.

## Primary sources

- [Sauvie Island harvest statistics][harvest]
- [Sauvie Island reservation summaries][reservations]
- [Eastside unit and blind-selection guide][eastside]
- [Westside unit and lottery guide][westside]
- [Wildlife area reservation hunt rules and calendar][hunt-rules]
- [Controlled hunt drawing procedure][draw-rules]

The 2021-22 and 2022-23 harvest landing pages have been removed, but their
individual daily PDFs remain available from ODFW's legacy file host and are
preserved here.

## Reproduction

From the repository root:

```sh
python3 scripts/download_odfw_sauvie_data.py
```

The downloader uses only the Python standard library. It discovers linked
current-season and reservation documents, checks the legacy ODFW archive for
historical daily reports, validates PDF responses, and regenerates
`manifest.csv`.

[harvest]: https://myodfw.com/2025-26-sauvie-island-wildlife-area-game-bird-harvest-statistics
[reservations]: https://myodfw.com/sauvie-island-wildlife-area-game-bird-reservation-summaries
[eastside]: https://myodfw.com/articles/hunting-sauvie-islands-east-side-unit
[westside]: https://myodfw.com/articles/hunting-sauvie-islands-west-side-unit
[hunt-rules]: https://www.eregulations.com/oregon/hunting/game-bird/wildlife-area-reservation-hunts
[draw-rules]: https://www.eregulations.com/oregon/hunting/game-bird/reservation-permit-application
