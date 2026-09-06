# Football schedules

`football-games.csv` contains 222 team-game records for:

- Oregon Ducks
- Oregon State Beavers
- Seattle Seahawks

Coverage includes the 2021 through 2025 football seasons. Regular season,
conference championship, bowl, College Football Playoff, and NFL postseason
games are included; preseason games are excluded. Kickoff timestamps are
converted from ESPN's UTC values to `America/Los_Angeles` before matching them
to Sauvie Island hunt dates.

The raw responses and checksum manifest are in
`data/raw/espn/football-schedules/`. Reproduce them with:

```sh
python3 scripts/download_sports_schedules.py
```

## Source and limitations

Data comes from ESPN's public Site API and was spot-checked against the three
teams' official 2025 schedules. The API requires no key but is undocumented
and has no schema or availability guarantee, so the raw responses are
archived.

The sports comparison is observational. Game days are concentrated on
particular weekdays and parts of the hunting season. A relationship with
applications, turnout, or harvest does not establish that games caused the
difference.
