# Sauvie Island hunt-day weather

`hunt-day-weather.csv` contains one weather record for each of the 256 hunt
dates represented by the ODFW daily harvest archive. It covers the 2021-22
through 2025-26 seasons.

## Coverage

Each row includes:

- Temperature, apparent temperature, humidity, cloud cover, precipitation,
  conditions, wind speed, gusts, and wind direction near estimated opening.
- Daily mean, high, and low temperature.
- Daily precipitation, rain, snowfall, and precipitation hours.
- Daily maximum wind, maximum gust, and dominant wind direction.
- WMO weather codes plus readable condition labels.
- Requested location, returned weather grid, model, timezone, and sample time.

Temperatures are Fahrenheit, wind speeds are miles per hour, precipitation is
inches, direction is both degrees and a 16-point compass value, and all times
are local `America/Los_Angeles` time.

## Location and opening-time methodology

The requested point is `45.7200, -122.8030`, representing the Sauvie Island
Wildlife Area. Open-Meteo resolved all five seasons to its nearby
`45.729347, -122.791794` weather grid.

`estimated_open_time_local` is 30 minutes before Open-Meteo's local sunrise.
`opening_sample_time_local` is the nearest available hourly reanalysis value;
`opening_sample_offset_minutes` records the signed difference and is never
more than 30 minutes. This is an analytical opening-time estimate, not the
official historical ODFW Zone A shooting-hours table.

Hourly precipitation fields report the sum during the preceding hour. Daily
fields report the local calendar day's total.

One area-wide weather value is assigned to each hunt date. It can be joined to
all units and blinds for that date; it does not claim to capture
blind-to-blind microclimate differences.

## Source and limitations

The records use the fixed `ecmwf_ifs` model from the [Open-Meteo Historical
Weather API][api]. This is hourly reanalysis—a model informed by observations,
not a reading from a weather station at an individual blind. Open-Meteo
describes the model resolution as approximately 9 km.

The five original API responses and their checksums are preserved under
`data/raw/open-meteo/sauvie-island/`. The query and transformation can be
reproduced from the repository root:

```sh
python3 scripts/download_sauvie_weather.py
```

Weather data by [Open-Meteo.com][open-meteo], used and transformed under
[CC BY 4.0][license]. Open-Meteo's historical service incorporates ECMWF and
Copernicus Climate Change Service data.

[api]: https://open-meteo.com/en/docs/historical-weather-api
[open-meteo]: https://open-meteo.com/
[license]: https://creativecommons.org/licenses/by/4.0/
