#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import requests

# Current GEUS THREDDS hourly Level-3 CSV for MIT_B.
CSV_URL = "https://www.thredds.geus.dk/thredds/fileServer/aws/l3sites/csv/hour/MIT_B_hour.csv"

OUTFILE = Path(__file__).with_name("weather.json")
HISTORY_HOURS = 7 * 24

def first_existing(columns, candidates):
    for name in candidates:
        if name in columns:
            return name
    return None

def clean_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    try:
        return float(value)
    except (TypeError, ValueError):
        return value

def main():
    response = requests.get(CSV_URL, timeout=60)
    response.raise_for_status()

    tmp = Path(__file__).with_name("MIT_B_hour.csv")
    tmp.write_bytes(response.content)

    df = pd.read_csv(tmp)

    # PROMICE/GEUS files normally use 'time', but this also tolerates common alternatives.
    time_col = first_existing(df.columns, ["time", "timestamp", "datetime", "date"])
    if not time_col:
        raise RuntimeError(f"No time column found. Columns are: {list(df.columns)}")

    df[time_col] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
    df = df.dropna(subset=[time_col]).sort_values(time_col)

    # Prefer processed upper-boom hourly variables.
    mapping = {
        "temperature": first_existing(df.columns, ["t_u", "t_i", "air_temperature"]),
        "humidity": first_existing(df.columns, ["rh_u", "rh_i", "relative_humidity"]),
        "wind_speed": first_existing(df.columns, ["wspd_u", "wspd_i", "wind_speed"]),
        "wind_direction": first_existing(df.columns, ["wdir_u", "wdir_i", "wind_direction"]),
        "pressure": first_existing(df.columns, ["p_u", "p_i", "air_pressure"]),
        "shortwave_down": first_existing(df.columns, ["dsr"]),
        "shortwave_up": first_existing(df.columns, ["usr"]),
        "longwave_down": first_existing(df.columns, ["dlr"]),
        "longwave_up": first_existing(df.columns, ["ulr"]),
        "surface_temperature": first_existing(df.columns, ["t_surf"]),
        "snow_height": first_existing(df.columns, ["snow_height"]),
        "battery_voltage": first_existing(df.columns, ["batt_v"]),
    }

    # Use the latest row containing at least temperature or wind data if possible.
    preferred = [c for c in [mapping["temperature"], mapping["wind_speed"]] if c]
    if preferred:
        valid = df.dropna(subset=preferred, how="all")
        latest = valid.iloc[-1] if not valid.empty else df.iloc[-1]
    else:
        latest = df.iloc[-1]

    hist = df.tail(HISTORY_HOURS).copy()

    payload = {
        "station": {
            "id": "MIT_B",
            "name": "MIT_B Weather Station",
            "latitude": 65.70607,
            "longitude": -37.81144,
            "elevation_m": 520,
            "source": "GEUS / PROMICE",
            "source_url": CSV_URL
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest": {
            "time": latest[time_col].isoformat(),
        },
        "history": []
    }

    for out_name, col in mapping.items():
        payload["latest"][out_name] = clean_value(latest[col]) if col else None

    for _, row in hist.iterrows():
        item = {"time": row[time_col].isoformat()}
        for out_name in ["temperature", "humidity", "wind_speed", "pressure",
                         "shortwave_down", "surface_temperature", "snow_height"]:
            col = mapping[out_name]
            item[out_name] = clean_value(row[col]) if col else None
        payload["history"].append(item)

    OUTFILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUTFILE} with {len(payload['history'])} hourly records.")
    print("Detected columns:", mapping)

if __name__ == "__main__":
    main()
