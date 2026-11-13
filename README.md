# MIT_B live weather dashboard

Prototype dashboard for GEUS / PROMICE station MIT_B.

## What it does

- Downloads the current hourly Level-3 CSV from GEUS THREDDS
- Detects the relevant PROMICE variables
- Writes the latest values and the last 7 days to `weather.json`
- Displays temperature, wind, humidity and pressure in `index.html`
- Refreshes the browser every 5 minutes
- Includes a GitHub Actions workflow that can fetch new data automatically

## Main GEUS variables used

- `t_u` — air temperature, upper boom [°C]
- `rh_u` — relative humidity, upper boom [%]
- `wspd_u` — wind speed, upper boom [m/s]
- `wdir_u` — wind-from direction [degrees]
- `p_u` — air pressure [hPa]
- `dsr` — downwelling shortwave radiation [W m-2]
- `usr` — upwelling shortwave radiation [W m-2]
- `dlr` — downwelling longwave radiation [W m-2]
- `ulr` — upwelling longwave radiation [W m-2]
- `t_surf` — surface temperature [°C]
- `snow_height` — snow height
- `batt_v` — battery voltage [V]

## Run locally

```bash
pip install -r requirements.txt
python fetch_weather.py
python -m http.server 8000
```

Then open:

http://localhost:8000

Do not open `index.html` directly as a `file://` URL because browsers commonly block `fetch()` for local files.

## GitHub Pages

1. Create a GitHub repository.
2. Put these files in the repository root.
3. Move `update-weather.yml` to `.github/workflows/update-weather.yml`.
4. Run the workflow manually once.
5. Enable GitHub Pages from the repository's main branch/root.

The scheduled job is set to run at minute 7 of each hour. It can be changed in the YAML.

## Notes

The THREDDS endpoint is preferable here to scraping the Dataverse web interface, because it exposes the current operational Level-3 hourly product directly. If GEUS changes its data layout, only `CSV_URL` and/or the mapping in `fetch_weather.py` should need adjustment.
