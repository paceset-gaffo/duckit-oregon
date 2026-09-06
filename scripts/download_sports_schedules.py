#!/usr/bin/env python3
"""Archive and normalize Oregon, Oregon State, and Seahawks schedules."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw" / "espn" / "football-schedules"
OUTPUT = ROOT / "data" / "processed" / "sports" / "football-games.csv"
API_ROOT = "https://site.api.espn.com/apis/site/v2/sports/football"
PACIFIC = ZoneInfo("America/Los_Angeles")
SEASONS = range(2021, 2026)
SEASON_TYPES = {2: "regular", 3: "postseason"}
TEAMS = {
    "oregon": {
        "name": "Oregon Ducks",
        "league": "college-football",
        "team_id": "2483",
    },
    "oregon-state": {
        "name": "Oregon State Beavers",
        "league": "college-football",
        "team_id": "204",
    },
    "seattle-seahawks": {
        "name": "Seattle Seahawks",
        "league": "nfl",
        "team_id": "26",
    },
}
USER_AGENT = "duckit-oregon schedule archiver/1.0"

OUTPUT_FIELDS = [
    "team",
    "team_slug",
    "league",
    "football_season",
    "season_type",
    "season_type_name",
    "event_id",
    "event_name",
    "short_name",
    "game_datetime_utc",
    "game_datetime_pacific",
    "game_date_pacific",
    "kickoff_time_pacific",
    "time_valid",
    "week",
    "home_away",
    "opponent_id",
    "opponent",
    "opponent_abbreviation",
    "team_score",
    "opponent_score",
    "result",
    "completed",
    "status",
    "neutral_site",
    "venue",
    "venue_city",
    "venue_state",
    "broadcasts",
    "notes",
    "source_url",
]


def source_url(league: str, team_id: str, year: int, season_type: int) -> str:
    return (
        f"{API_ROOT}/{league}/teams/{team_id}/schedule"
        f"?season={year}&seasontype={season_type}"
    )


def score(competitor: dict) -> int | None:
    value = competitor.get("score", {}).get("value")
    return int(value) if value is not None else None


def normalize_event(
    event: dict,
    team_slug: str,
    team: dict[str, str],
    source: str,
) -> dict[str, object]:
    competition = event["competitions"][0]
    competitors = competition["competitors"]
    selected = next(
        value for value in competitors if value["team"]["id"] == team["team_id"]
    )
    opponent = next(value for value in competitors if value is not selected)
    status = competition["status"]["type"]
    completed = bool(status["completed"])
    team_score = score(selected)
    opponent_score = score(opponent)
    result = ""
    if completed and team_score is not None and opponent_score is not None:
        result = "W" if team_score > opponent_score else "L"
        if team_score == opponent_score:
            result = "T"

    game_utc = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
    game_pacific = game_utc.astimezone(PACIFIC)
    venue = competition.get("venue", {})
    address = venue.get("address", {})
    broadcasts = sorted(
        {
            name
            for item in competition.get("broadcasts", [])
            for name in item.get("names", [])
        }
    )
    notes = [
        item["headline"]
        for item in competition.get("notes", [])
        if item.get("headline")
    ]
    season_type = event["seasonType"]

    return {
        "team": team["name"],
        "team_slug": team_slug,
        "league": team["league"],
        "football_season": event["season"]["year"],
        "season_type": season_type["type"],
        "season_type_name": season_type["name"],
        "event_id": event["id"],
        "event_name": event["name"],
        "short_name": event["shortName"],
        "game_datetime_utc": game_utc.isoformat(),
        "game_datetime_pacific": game_pacific.isoformat(),
        "game_date_pacific": game_pacific.date().isoformat(),
        "kickoff_time_pacific": game_pacific.strftime("%H:%M"),
        "time_valid": event.get("timeValid", competition.get("timeValid", False)),
        "week": event.get("week", {}).get("number"),
        "home_away": selected["homeAway"],
        "opponent_id": opponent["team"]["id"],
        "opponent": opponent["team"]["displayName"],
        "opponent_abbreviation": opponent["team"]["abbreviation"],
        "team_score": team_score,
        "opponent_score": opponent_score,
        "result": result,
        "completed": completed,
        "status": status["description"],
        "neutral_site": competition.get("neutralSite", False),
        "venue": venue.get("fullName", ""),
        "venue_city": address.get("city", ""),
        "venue_state": address.get("state", ""),
        "broadcasts": "|".join(broadcasts),
        "notes": "|".join(notes),
        "source_url": source,
    }


def main() -> None:
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    retrieved_at = datetime.now(UTC).isoformat(timespec="seconds")
    manifest_rows = []
    games: dict[tuple[str, str], dict[str, object]] = {}

    for team_slug, team in TEAMS.items():
        team_root = RAW_ROOT / team_slug
        team_root.mkdir(parents=True, exist_ok=True)
        for year in SEASONS:
            for season_type, type_slug in SEASON_TYPES.items():
                url = source_url(
                    team["league"], team["team_id"], year, season_type
                )
                response = session.get(url, timeout=60)
                response.raise_for_status()
                payload = response.json()
                content = response.content
                raw_path = team_root / f"{year}-{type_slug}.json"
                raw_path.write_bytes(content)
                manifest_rows.append(
                    {
                        "team": team["name"],
                        "football_season": year,
                        "season_type": season_type,
                        "local_path": raw_path.relative_to(ROOT).as_posix(),
                        "source_url": url,
                        "retrieved_at_utc": retrieved_at,
                        "bytes": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                )
                for event in payload["events"]:
                    row = normalize_event(event, team_slug, team, url)
                    games[(team_slug, event["id"])] = row

    manifest_path = RAW_ROOT / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "team",
                "football_season",
                "season_type",
                "local_path",
                "source_url",
                "retrieved_at_utc",
                "bytes",
                "sha256",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    with OUTPUT.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file, fieldnames=OUTPUT_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(
            sorted(
                games.values(),
                key=lambda row: (
                    row["game_datetime_utc"],
                    row["team_slug"],
                ),
            )
        )
    print(
        f"Wrote {len(games)} team-game rows to {OUTPUT} "
        f"from {len(manifest_rows)} archived responses"
    )


if __name__ == "__main__":
    main()
