#!/usr/bin/env python3
"""Download the public ODFW Sauvie Island waterfowl source documents."""

from __future__ import annotations

import csv
import hashlib
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "raw" / "odfw" / "sauvie-island"
USER_AGENT = "duckit-oregon source archiver/1.0"

HARVEST_PAGE = (
    "https://myodfw.com/"
    "2025-26-sauvie-island-wildlife-area-game-bird-harvest-statistics"
)
RESERVATION_PAGE = (
    "https://myodfw.com/"
    "sauvie-island-wildlife-area-game-bird-reservation-summaries"
)

HISTORICAL_SEASONS = {
    "2021-22": (date(2021, 10, 1), date(2022, 1, 31)),
    "2022-23": (date(2022, 10, 1), date(2023, 1, 31)),
    "2023-24": (date(2023, 10, 1), date(2024, 1, 31)),
    "2024-25": (date(2024, 10, 1), date(2025, 1, 31)),
}

REFERENCE_DOCUMENTS = {
    "references/eastside-units-map.pdf": (
        "https://www.dfw.state.or.us/resources/hunting/waterfowl/"
        "sauvie/docs/EastUnits.pdf"
    ),
    "references/eastside-blinds-map.pdf": (
        "https://www.dfw.state.or.us/resources/hunting/waterfowl/"
        "sauvie/docs/BlindsEast.pdf"
    ),
    "references/oak-island-map.pdf": (
        "https://www.dfw.state.or.us/resources/hunting/waterfowl/"
        "sauvie/docs/OakUnit.pdf"
    ),
    "references/westside-units-map.pdf": (
        "https://www.dfw.state.or.us/resources/hunting/waterfowl/"
        "sauvie/docs/WestUnits.pdf"
    ),
    "references/westside-blinds-map.pdf": (
        "https://www.dfw.state.or.us/resources/hunting/waterfowl/"
        "sauvie/docs/BlindsWest.pdf"
    ),
    "references/reservations-available-by-unit-and-period.pdf": (
        "https://myodfw.com/sites/default/files/2025-10/"
        "Number_of_Reservations_Available_for_the_Eastside_and_Oak_Island"
        "%20updated%20Nov2021.pdf"
    ),
    "references/daily-harvest-by-unit-2013-14-to-2024-25.pdf": (
        "https://myodfw.com/sites/default/files/2025-10/"
        "2013-14%20to%202024-25%20Hunters%20Ducks%20DucksPerHunter"
        "%20by%20Unit%20by%20Day.pdf"
    ),
    "references/waterfowl-harvest-50-year-average-1976-2026.pdf": (
        "https://myodfw.com/sites/default/files/2026-01/"
        "WATERFOWL%20HARVEST%20WORKSHEET%20%2050YR.%20AVERAGE.pdf"
    ),
}

SEASON_SUMMARIES = {
    "2023-24/harvest/season-summary-by-unit-and-blind.pdf": (
        "https://myodfw.com/sites/default/files/2025-10/2023SeasonSummary.pdf"
    ),
    "2024-25/harvest/season-summary-by-unit-and-blind.pdf": (
        "https://myodfw.com/sites/default/files/2025-10/"
        "2024_25_SIWASeasonSummary.pdf"
    ),
    "2025-26/harvest/season-summary-by-unit-and-blind.pdf": (
        "https://myodfw.com/sites/default/files/2026-01/"
        "2025SeasonSummary_8.pdf"
    ),
}


@dataclass(frozen=True)
class Source:
    category: str
    season: str
    relative_path: str
    url: str


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            text = " ".join("".join(self._text).split())
            self.links.append((text, self._href))
            self._href = None
            self._text = []


def request_bytes(url: str, timeout: int = 30) -> tuple[bytes, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return response.read(), response.headers.get_content_type()


def page_links(url: str) -> list[tuple[str, str]]:
    content, _ = request_bytes(url)
    parser = LinkParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    return [(text, urljoin(url, href)) for text, href in parser.links]


def current_daily_sources() -> list[Source]:
    sources: list[Source] = []
    for _, url in page_links(HARVEST_PAGE):
        decoded_name = unquote(Path(urlparse(url).path).name)
        match = re.search(r"(\d{2})(\d{2})(\d{4})s(?:_\d+)?\.pdf$", decoded_name)
        if not match:
            continue
        month, day, year = map(int, match.groups())
        hunt_date = date(year, month, day)
        sources.append(
            Source(
                category="daily_harvest",
                season="2025-26",
                relative_path=(
                    f"2025-26/harvest/daily/{hunt_date.isoformat()}.pdf"
                ),
                url=url,
            )
        )
    return sources


def reservation_sources() -> list[Source]:
    sources: list[Source] = []
    for text, url in page_links(RESERVATION_PAGE):
        if "First Choice Applications" not in text:
            continue
        decoded_name = unquote(Path(urlparse(url).path).name)
        match = re.search(r"(202[1-5]) SIWA ([A-G]) Draw", decoded_name)
        if not match:
            raise ValueError(f"Unrecognized reservation link: {url}")
        year, period = match.groups()
        season = f"{year}-{str(int(year[-2:]) + 1).zfill(2)}"
        sources.append(
            Source(
                category="first_choice_applications",
                season=season,
                relative_path=(
                    f"{season}/reservations/period-{period.lower()}-"
                    "first-choice-applications.pdf"
                ),
                url=url,
            )
        )
    return sources


def historical_daily_candidates() -> list[Source]:
    sources: list[Source] = []
    for season, (start, end) in HISTORICAL_SEASONS.items():
        current = start
        while current <= end:
            url = (
                "https://www.dfw.state.or.us/resources/hunting/waterfowl/"
                f"counts/sauvie_island/{season}/{current:%m%d%Y}s.pdf"
            )
            sources.append(
                Source(
                    category="daily_harvest",
                    season=season,
                    relative_path=(
                        f"{season}/harvest/daily/{current.isoformat()}.pdf"
                    ),
                    url=url,
                )
            )
            current += timedelta(days=1)
    return sources


def existing_historical_sources(candidates: list[Source]) -> list[Source]:
    def exists(source: Source) -> tuple[Source, bool]:
        request = Request(source.url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=20) as response:
                return source, response.status == 200 and (
                    response.headers.get_content_type() == "application/pdf"
                )
        except HTTPError as error:
            if error.code == 404:
                return source, False
            raise

    found: list[Source] = []
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(exists, source) for source in candidates]
        for future in as_completed(futures):
            source, is_present = future.result()
            if is_present:
                found.append(source)
    return found


def static_sources() -> list[Source]:
    sources = [
        Source(
            category="season_harvest",
            season=path.split("/", 1)[0],
            relative_path=path,
            url=url,
        )
        for path, url in SEASON_SUMMARIES.items()
    ]
    sources.extend(
        Source(
            category="reference",
            season="",
            relative_path=path,
            url=url,
        )
        for path, url in REFERENCE_DOCUMENTS.items()
    )
    return sources


def download(source: Source) -> dict[str, str | int]:
    content, content_type = request_bytes(source.url, timeout=60)
    if content_type != "application/pdf" or not content.startswith(b"%PDF"):
        raise ValueError(
            f"Expected PDF at {source.url}; received {content_type!r}"
        )
    destination = DATA_ROOT / source.relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return {
        "category": source.category,
        "season": source.season,
        "local_path": destination.relative_to(ROOT).as_posix(),
        "source_url": source.url,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def write_manifest(rows: list[dict[str, str | int]]) -> None:
    manifest = DATA_ROOT / "manifest.csv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "category",
        "season",
        "local_path",
        "source_url",
        "bytes",
        "sha256",
    ]
    with manifest.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: str(row["local_path"])))


def main() -> int:
    try:
        sources = current_daily_sources()
        sources.extend(reservation_sources())
        sources.extend(
            existing_historical_sources(historical_daily_candidates())
        )
        sources.extend(static_sources())

        unique = {source.relative_path: source for source in sources}
        if len(unique) != len(sources):
            raise ValueError("Multiple sources resolve to the same local path")

        rows: list[dict[str, str | int]] = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(download, source): source
                for source in unique.values()
            }
            for future in as_completed(futures):
                rows.append(future.result())

        write_manifest(rows)
        print(f"Downloaded {len(rows)} ODFW documents to {DATA_ROOT}")
        return 0
    except (HTTPError, URLError, OSError, ValueError) as error:
        print(f"Download failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
