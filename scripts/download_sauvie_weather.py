#!/usr/bin/env python3
"""Download and derive hunt-day weather for the Sauvie Island archive."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
ODFW_MANIFEST = (
    ROOT / "data" / "raw" / "odfw" / "sauvie-island" / "manifest.csv"
)
RAW_ROOT = ROOT / "data" / "raw" / "open-meteo" / "sauvie-island"
OUTPUT = (
    ROOT / "data" / "processed" / "sauvie-island" / "hunt-day-weather.csv"
)

API_URL = "https://archive-api.open-meteo.com/v1/archive"
USER_AGENT = "duckit-oregon weather archiver/1.0"
REQUESTED_LATITUDE = 45.72
REQUESTED_LONGITUDE = -122.803
TIMEZONE = "America/Los_Angeles"
MODEL = "ecmwf_ifs"

HOURLY_FIELDS = [
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation",
    "rain",
    "snowfall",
    "weather_code",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
]

DAILY_FIELDS = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
    "precipitation_hours",
    "sunrise",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
]

WMO_CONDITIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

OUTPUT_FIELDS = [
    "season",
    "hunt_date",
    "timezone",
    "sunrise_local",
    "estimated_open_time_local",
    "opening_sample_time_local",
    "opening_sample_offset_minutes",
    "opening_weather_code",
    "opening_conditions",
    "opening_temperature_f",
    "opening_apparent_temperature_f",
    "opening_relative_humidity_pct",
    "opening_cloud_cover_pct",
    "opening_precipitation_in",
    "opening_rain_in",
    "opening_snowfall_in",
    "opening_wind_speed_mph",
    "opening_wind_gust_mph",
    "opening_wind_direction_deg",
    "opening_wind_direction_cardinal",
    "daily_weather_code",
    "daily_conditions",
    "daily_temperature_mean_f",
    "daily_temperature_high_f",
    "daily_temperature_low_f",
    "daily_precipitation_in",
    "daily_rain_in",
    "daily_snowfall_in",
    "daily_precipitation_hours",
    "daily_wind_speed_max_mph",
    "daily_wind_gust_max_mph",
    "daily_wind_direction_dominant_deg",
    "daily_wind_direction_dominant_cardinal",
    "requested_latitude",
    "requested_longitude",
    "weather_grid_latitude",
    "weather_grid_longitude",
    "weather_grid_elevation_m",
    "weather_model",
]


def hunt_dates() -> dict[str, list[str]]:
    by_season: dict[str, list[str]] = defaultdict(list)
    with ODFW_MANIFEST.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if row["category"] != "daily_harvest":
                continue
            hunt_date = Path(row["local_path"]).stem
            datetime.strptime(hunt_date, "%Y-%m-%d")
            by_season[row["season"]].append(hunt_date)
    return {
        season: sorted(set(dates))
        for season, dates in sorted(by_season.items())
    }


def api_url(start_date: str, end_date: str) -> str:
    parameters = {
        "latitude": REQUESTED_LATITUDE,
        "longitude": REQUESTED_LONGITUDE,
        "start_date": start_date,
        "end_date": end_date,
        "models": MODEL,
        "timezone": TIMEZONE,
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "hourly": ",".join(HOURLY_FIELDS),
        "daily": ",".join(DAILY_FIELDS),
    }
    return f"{API_URL}?{urlencode(parameters)}"


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=90) as response:
        if response.headers.get_content_type() != "application/json":
            raise ValueError(f"Expected JSON from {url}")
        return response.read()


def cardinal(degrees: int | float | None) -> str:
    if degrees is None:
        return ""
    names = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]
    return names[int((float(degrees) + 11.25) // 22.5) % 16]


def condition(code: int | float | None) -> str:
    if code is None:
        return ""
    return WMO_CONDITIONS.get(int(code), f"Unknown WMO code {code}")


def indexed(values: dict[str, list], index: int, key: str):
    return values[key][index]


def derive_rows(
    season: str, dates: list[str], payload: dict
) -> list[dict[str, object]]:
    daily = payload["daily"]
    hourly = payload["hourly"]
    daily_indexes = {value: index for index, value in enumerate(daily["time"])}
    hourly_times = [
        datetime.fromisoformat(value)
        for value in hourly["time"]
    ]
    hourly_indexes_by_date: dict[str, list[int]] = defaultdict(list)
    for index, value in enumerate(hourly_times):
        hourly_indexes_by_date[value.date().isoformat()].append(index)

    rows: list[dict[str, object]] = []
    for hunt_date in dates:
        daily_index = daily_indexes[hunt_date]
        sunrise = datetime.fromisoformat(
            indexed(daily, daily_index, "sunrise")
        )
        estimated_open = sunrise - timedelta(minutes=30)
        opening_index = min(
            hourly_indexes_by_date[hunt_date],
            key=lambda index: abs(hourly_times[index] - estimated_open),
        )
        opening_time = hourly_times[opening_index]

        opening_code = indexed(hourly, opening_index, "weather_code")
        opening_direction = indexed(
            hourly, opening_index, "wind_direction_10m"
        )
        daily_code = indexed(daily, daily_index, "weather_code")
        daily_direction = indexed(
            daily, daily_index, "wind_direction_10m_dominant"
        )
        rows.append(
            {
                "season": season,
                "hunt_date": hunt_date,
                "timezone": payload["timezone"],
                "sunrise_local": sunrise.isoformat(timespec="minutes"),
                "estimated_open_time_local": estimated_open.isoformat(
                    timespec="minutes"
                ),
                "opening_sample_time_local": opening_time.isoformat(
                    timespec="minutes"
                ),
                "opening_sample_offset_minutes": int(
                    (opening_time - estimated_open).total_seconds() / 60
                ),
                "opening_weather_code": opening_code,
                "opening_conditions": condition(opening_code),
                "opening_temperature_f": indexed(
                    hourly, opening_index, "temperature_2m"
                ),
                "opening_apparent_temperature_f": indexed(
                    hourly, opening_index, "apparent_temperature"
                ),
                "opening_relative_humidity_pct": indexed(
                    hourly, opening_index, "relative_humidity_2m"
                ),
                "opening_cloud_cover_pct": indexed(
                    hourly, opening_index, "cloud_cover"
                ),
                "opening_precipitation_in": indexed(
                    hourly, opening_index, "precipitation"
                ),
                "opening_rain_in": indexed(hourly, opening_index, "rain"),
                "opening_snowfall_in": indexed(
                    hourly, opening_index, "snowfall"
                ),
                "opening_wind_speed_mph": indexed(
                    hourly, opening_index, "wind_speed_10m"
                ),
                "opening_wind_gust_mph": indexed(
                    hourly, opening_index, "wind_gusts_10m"
                ),
                "opening_wind_direction_deg": opening_direction,
                "opening_wind_direction_cardinal": cardinal(
                    opening_direction
                ),
                "daily_weather_code": daily_code,
                "daily_conditions": condition(daily_code),
                "daily_temperature_mean_f": indexed(
                    daily, daily_index, "temperature_2m_mean"
                ),
                "daily_temperature_high_f": indexed(
                    daily, daily_index, "temperature_2m_max"
                ),
                "daily_temperature_low_f": indexed(
                    daily, daily_index, "temperature_2m_min"
                ),
                "daily_precipitation_in": indexed(
                    daily, daily_index, "precipitation_sum"
                ),
                "daily_rain_in": indexed(daily, daily_index, "rain_sum"),
                "daily_snowfall_in": indexed(
                    daily, daily_index, "snowfall_sum"
                ),
                "daily_precipitation_hours": indexed(
                    daily, daily_index, "precipitation_hours"
                ),
                "daily_wind_speed_max_mph": indexed(
                    daily, daily_index, "wind_speed_10m_max"
                ),
                "daily_wind_gust_max_mph": indexed(
                    daily, daily_index, "wind_gusts_10m_max"
                ),
                "daily_wind_direction_dominant_deg": daily_direction,
                "daily_wind_direction_dominant_cardinal": cardinal(
                    daily_direction
                ),
                "requested_latitude": REQUESTED_LATITUDE,
                "requested_longitude": REQUESTED_LONGITUDE,
                "weather_grid_latitude": payload["latitude"],
                "weather_grid_longitude": payload["longitude"],
                "weather_grid_elevation_m": payload["elevation"],
                "weather_model": MODEL,
            }
        )
    return rows


def write_raw_manifest(rows: list[dict[str, object]]) -> None:
    path = RAW_ROOT / "manifest.csv"
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "season",
                "local_path",
                "source_url",
                "bytes",
                "sha256",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_output(rows: list[dict[str, object]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    try:
        dates_by_season = hunt_dates()
        RAW_ROOT.mkdir(parents=True, exist_ok=True)
        raw_manifest: list[dict[str, object]] = []
        output_rows: list[dict[str, object]] = []

        for season, dates in dates_by_season.items():
            url = api_url(dates[0], dates[-1])
            content = fetch(url)
            payload = json.loads(content)
            raw_path = RAW_ROOT / f"{season}.json"
            raw_path.write_bytes(content)
            raw_manifest.append(
                {
                    "season": season,
                    "local_path": raw_path.relative_to(ROOT).as_posix(),
                    "source_url": url,
                    "bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
            output_rows.extend(derive_rows(season, dates, payload))

        write_raw_manifest(raw_manifest)
        write_output(output_rows)
        print(
            f"Wrote {len(output_rows)} hunt-day weather rows to {OUTPUT}"
        )
        return 0
    except (
        HTTPError,
        URLError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(f"Weather download failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
