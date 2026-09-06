#!/usr/bin/env python3
"""Build the DuckDB analytical database from archived source documents."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
ODFW_ROOT = ROOT / "data" / "raw" / "odfw" / "sauvie-island"
ODFW_MANIFEST = ODFW_ROOT / "manifest.csv"
WEATHER_ROOT = ROOT / "data" / "raw" / "open-meteo" / "sauvie-island"
WEATHER_CSV = (
    ROOT / "data" / "processed" / "sauvie-island" / "hunt-day-weather.csv"
)
DATABASE = ROOT / "data" / "processed" / "duckit_oregon.duckdb"
COMPILED_HARVEST = (
    ODFW_ROOT
    / "references"
    / "daily-harvest-by-unit-2013-14-to-2024-25.pdf"
)

EASTSIDE_UNITS = [
    "Johnson",
    "Racetrack",
    "Hunt",
    "Mudhen",
    "Aaron",
    "Dead Willow",
    "Footbridge",
    "Malarky",
    "McNary",
    "Pope Lake",
    "Reeder Tract",
    "Rentenaar",
    "Stutzer",
    "Oak Island",
]
WESTSIDE_UNITS = [
    "Mud Lake",
    "Seal",
    "Steelman",
    "Holman Point",
    "Crane",
    "North Crane",
    "Flights End",
]

COMPILED_LABELS = {
    "Johnson": "Johnson",
    "Racetrack": "Racetrack",
    "Hunt": "Hunt",
    "Mudhen": "Mudhen",
    "Aaron": "Aaron",
    "Dead Willow": "Dead Willow",
    "Footbridge": "Footbridge",
    "Malarky": "Malarky",
    "McNary": "McNary",
    "Pope Lake": "Pope",
    "Reeder Tract": "Reeder Tract",
    "Rentenaar": "Rentenaar",
    "Stutzer": "Stutzer",
    "Oak Island": "Oak Island Total",
    "Mud Lake": "Mud Lake",
    "Seal": "Seal",
    "Steelman": "Steelman",
    "Holman Point": "Holman Point",
    "Crane": "Crane",
    "North Crane": "North Crane",
    "Flights End": "Flights End",
}

DAILY_ALIASES = {
    "Deadwillow": "Dead Willow",
    "Dead Willow": "Dead Willow",
    "Pope": "Pope Lake",
    "Pope Lake": "Pope Lake",
    "Reeder": "Reeder Tract",
    "Reeder Tract": "Reeder Tract",
    "Flight's End": "Flights End",
    "Flights End": "Flights End",
}


def read_manifest() -> pd.DataFrame:
    return pd.read_csv(ODFW_MANIFEST)


def archived_hunt_dates(manifest: pd.DataFrame) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    daily = manifest.loc[manifest["category"] == "daily_harvest"]
    for row in daily.itertuples():
        result[row.season].add(Path(row.local_path).stem)
    return result


def integers(value: str) -> list[int]:
    return [int(item.replace(",", "")) for item in value.split()]


def parse_compiled_harvest(
    hunt_dates: dict[str, set[str]]
) -> list[dict[str, object]]:
    reader = PdfReader(COMPILED_HARVEST)
    page_by_season = {
        "2024-25": 0,
        "2023-24": 2,
        "2022-23": 4,
        "2021-22": 6,
    }
    rows: list[dict[str, object]] = []

    for season, first_page in page_by_season.items():
        page_texts = [
            reader.pages[first_page].extract_text() or "",
            reader.pages[first_page + 1].extract_text() or "",
        ]
        header = page_texts[0].split("Season Total", 1)[0]
        dates = [
            datetime.strptime(line.strip(), "%m/%d/%Y").date().isoformat()
            for line in header.splitlines()
            if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", line.strip())
        ]
        combined_text = "\n".join(page_texts)

        for area, units in (
            ("Eastside", EASTSIDE_UNITS),
            ("Westside", WESTSIDE_UNITS),
        ):
            for unit in units:
                label = COMPILED_LABELS[unit]
                metric_values: dict[str, list[int]] = {}
                for metric in ("Hunters", "Ducks"):
                    match = re.search(
                        rf"^{re.escape(label)}(?: Unit)? {metric} (.+)$",
                        combined_text,
                        flags=re.MULTILINE,
                    )
                    if not match:
                        raise ValueError(
                            f"Missing {season} {unit} {metric} row"
                        )
                    values = integers(match.group(1))
                    if len(values) != len(dates) + 1:
                        raise ValueError(
                            f"Unexpected {season} {unit} {metric} length: "
                            f"{len(values)} for {len(dates)} dates"
                        )
                    if sum(values[:-1]) != values[-1]:
                        raise ValueError(
                            f"Season total mismatch for {season} {unit} "
                            f"{metric}"
                        )
                    metric_values[metric] = values[:-1]

                for index, hunt_date in enumerate(dates):
                    if hunt_date not in hunt_dates[season]:
                        continue
                    rows.append(
                        {
                            "season": season,
                            "hunt_date": hunt_date,
                            "area": area,
                            "unit": unit,
                            "hunters": metric_values["Hunters"][index],
                            "ducks": metric_values["Ducks"][index],
                            "source_path": COMPILED_HARVEST.relative_to(
                                ROOT
                            ).as_posix(),
                            "extraction_method": "compiled_unit_summary",
                        }
                    )
    return rows


def parse_current_daily_harvest(
    manifest: pd.DataFrame,
) -> list[dict[str, object]]:
    all_units = EASTSIDE_UNITS + WESTSIDE_UNITS
    names = sorted(set(all_units) | set(DAILY_ALIASES), key=len, reverse=True)
    line_pattern = re.compile(
        r"^(" + "|".join(map(re.escape, names)) + r")\s+(.+?)\s*$"
    )
    rows: list[dict[str, object]] = []
    current = manifest.loc[
        (manifest["category"] == "daily_harvest")
        & (manifest["season"] == "2025-26")
    ]

    for source in current.itertuples():
        source_path = ROOT / source.local_path
        text = PdfReader(source_path).pages[0].extract_text() or ""
        found: dict[str, tuple[int, int]] = {}
        for raw_line in text.splitlines():
            line = " ".join(raw_line.split())
            match = line_pattern.match(line)
            if not match:
                continue
            unit = DAILY_ALIASES.get(match.group(1), match.group(1))
            values = match.group(2).split()
            if len(values) not in (4, 5):
                continue
            try:
                hunters, ducks = int(values[0]), int(values[1])
            except ValueError:
                continue
            found[unit] = (hunters, ducks)

        missing = set(all_units) - set(found)
        if missing:
            raise ValueError(f"{source_path} is missing units: {missing}")
        for unit in all_units:
            hunters, ducks = found[unit]
            rows.append(
                {
                    "season": source.season,
                    "hunt_date": Path(source.local_path).stem,
                    "area": (
                        "Eastside" if unit in EASTSIDE_UNITS else "Westside"
                    ),
                    "unit": unit,
                    "hunters": hunters,
                    "ducks": ducks,
                    "source_path": source.local_path,
                    "extraction_method": "daily_summary_first_page",
                }
            )
    return rows


def harvest_frame(manifest: pd.DataFrame) -> pd.DataFrame:
    hunt_dates = archived_hunt_dates(manifest)
    rows = parse_compiled_harvest(hunt_dates)
    rows.extend(parse_current_daily_harvest(manifest))
    frame = pd.DataFrame(rows)
    frame["hunt_date"] = pd.to_datetime(frame["hunt_date"])
    first_dates = frame.groupby("season")["hunt_date"].transform("min")
    frame["season_day"] = (frame["hunt_date"] - first_dates).dt.days + 1
    frame["season_week"] = ((frame["season_day"] - 1) // 7) + 1
    frame["ducks_per_hunter"] = (
        frame["ducks"] / frame["hunters"].replace(0, pd.NA)
    ).astype("Float64")
    frame = frame[
        [
            "season",
            "hunt_date",
            "season_day",
            "season_week",
            "area",
            "unit",
            "hunters",
            "ducks",
            "ducks_per_hunter",
            "source_path",
            "extraction_method",
        ]
    ].sort_values(["season", "hunt_date", "area", "unit"])

    expected = sum(len(values) for values in hunt_dates.values()) * len(
        EASTSIDE_UNITS + WESTSIDE_UNITS
    )
    if len(frame) != expected:
        raise ValueError(f"Expected {expected} unit rows, found {len(frame)}")
    if frame.duplicated(["season", "hunt_date", "area", "unit"]).any():
        raise ValueError("Duplicate unit harvest rows")
    return frame


def weather_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    weather = pd.read_csv(WEATHER_CSV, parse_dates=["hunt_date"])
    manifest = pd.read_csv(WEATHER_ROOT / "manifest.csv")
    raw_rows = []
    for row in manifest.itertuples():
        raw_rows.append(
            {
                "season": row.season,
                "source_url": row.source_url,
                "local_path": row.local_path,
                "sha256": row.sha256,
                "response_json": json.dumps(
                    json.loads((ROOT / row.local_path).read_text())
                ),
            }
        )
    return weather, pd.DataFrame(raw_rows)


def build_database() -> None:
    manifest = read_manifest()
    harvest = harvest_frame(manifest)
    weather, weather_raw = weather_frames()
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    DATABASE.unlink(missing_ok=True)

    connection = duckdb.connect(DATABASE)
    connection.register("harvest_df", harvest)
    connection.register("weather_df", weather)
    connection.register("odfw_manifest_df", manifest)
    connection.register("weather_raw_df", weather_raw)

    connection.execute(
        """
        CREATE TABLE harvest_daily_unit AS
        SELECT
            season::VARCHAR AS season,
            hunt_date::DATE AS hunt_date,
            season_day::INTEGER AS season_day,
            season_week::INTEGER AS season_week,
            area::VARCHAR AS area,
            unit::VARCHAR AS unit,
            hunters::INTEGER AS hunters,
            ducks::INTEGER AS ducks,
            ducks_per_hunter::DOUBLE AS ducks_per_hunter,
            source_path::VARCHAR AS source_path,
            extraction_method::VARCHAR AS extraction_method
        FROM harvest_df;

        CREATE TABLE hunt_day_weather AS SELECT * FROM weather_df;
        CREATE TABLE odfw_source_manifest AS SELECT * FROM odfw_manifest_df;

        CREATE TABLE weather_raw_response AS
        SELECT
            season::VARCHAR AS season,
            source_url::VARCHAR AS source_url,
            local_path::VARCHAR AS local_path,
            sha256::VARCHAR AS sha256,
            response_json::JSON AS response_json
        FROM weather_raw_df;

        CREATE VIEW weekly_unit_harvest AS
        SELECT
            season,
            season_week,
            area,
            unit,
            SUM(hunters)::INTEGER AS hunters,
            SUM(ducks)::INTEGER AS ducks,
            SUM(ducks)::DOUBLE / NULLIF(SUM(hunters), 0)
                AS ducks_per_hunter
        FROM harvest_daily_unit
        GROUP BY season, season_week, area, unit;

        CREATE VIEW season_unit_harvest AS
        SELECT
            season,
            area,
            unit,
            SUM(hunters)::INTEGER AS hunters,
            SUM(ducks)::INTEGER AS ducks,
            SUM(ducks)::DOUBLE / NULLIF(SUM(hunters), 0)
                AS ducks_per_hunter
        FROM harvest_daily_unit
        GROUP BY season, area, unit;

        CREATE VIEW all_seasons_unit_harvest AS
        SELECT
            area,
            unit,
            SUM(hunters)::INTEGER AS hunters,
            SUM(ducks)::INTEGER AS ducks,
            SUM(ducks)::DOUBLE / NULLIF(SUM(hunters), 0)
                AS ducks_per_hunter
        FROM harvest_daily_unit
        GROUP BY area, unit;

        CREATE VIEW harvest_with_weather AS
        SELECT harvest.*, weather.* EXCLUDE (season, hunt_date)
        FROM harvest_daily_unit AS harvest
        LEFT JOIN hunt_day_weather AS weather
            USING (season, hunt_date);

        CREATE VIEW reservation_report_sources AS
        SELECT *
        FROM odfw_source_manifest
        WHERE category = 'first_choice_applications';

        CREATE INDEX harvest_date_index
            ON harvest_daily_unit (season, hunt_date);
        CREATE INDEX harvest_unit_index
            ON harvest_daily_unit (area, unit);
        """
    )

    metadata = pd.DataFrame(
        [
            ("built_by", "scripts/build_database.py"),
            ("harvest_seasons", "2021-22 through 2025-26"),
            ("harvest_daily_unit_rows", str(len(harvest))),
            ("hunt_day_weather_rows", str(len(weather))),
            (
                "opening_weather_definition",
                "nearest hourly sample to 30 minutes before local sunrise",
            ),
        ],
        columns=["key", "value"],
    )
    connection.register("metadata_df", metadata)
    connection.execute("CREATE TABLE database_metadata AS SELECT * FROM metadata_df")
    connection.execute("CHECKPOINT")

    summary = connection.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM harvest_daily_unit) AS harvest_rows,
            (SELECT COUNT(*) FROM hunt_day_weather) AS weather_rows,
            (SELECT COUNT(*) FROM odfw_source_manifest) AS source_rows
        """
    ).fetchone()
    connection.close()
    print(
        f"Built {DATABASE} with {summary[0]} harvest rows, "
        f"{summary[1]} weather rows, and {summary[2]} ODFW sources"
    )


if __name__ == "__main__":
    build_database()
