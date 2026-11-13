import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

DATA_URL = "https://thredds.geus.dk/thredds/dodsC/aws/l3sites/netcdf/hour/MIT_B_hour.nc"

OUTFILE = Path(__file__).with_name("weather.json")
HISTORY_HOURS = 7 * 24


def first_existing(ds, candidates):
    for name in candidates:
        if name in ds.variables:
            return name
    return None


def safe_value(value):
    try:
        value = np.asarray(value).squeeze()
        if np.size(value) != 1:
            return None
        value = value.item()
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def main():
    print("Opening GEUS MIT_B OPeNDAP dataset...")

    ds = xr.open_dataset(
        DATA_URL,
        engine="netcdf4",
        decode_times=True
    )

    print("Dataset opened successfully.")

    time_name = first_existing(ds, ["time", "timestamp", "datetime"])
    if time_name is None:
        raise RuntimeError(
            f"Could not find time variable. Available variables: {list(ds.variables)}"
        )

    mapping = {
        "temperature": first_existing(ds, ["t_u", "t_i", "air_temperature"]),
        "humidity": first_existing(ds, ["rh_u", "rh_i", "relative_humidity"]),
        "wind_speed": first_existing(ds, ["wspd_u", "wspd_i", "wind_speed"]),
        "wind_direction": first_existing(ds, ["wdir_u", "wdir_i", "wind_direction"]),
        "pressure": first_existing(ds, ["p_u", "p_i", "air_pressure"]),
        "shortwave_down": first_existing(ds, ["dsr"]),
        "shortwave_up": first_existing(ds, ["usr"]),
        "longwave_down": first_existing(ds, ["dlr"]),
        "longwave_up": first_existing(ds, ["ulr"]),
        "surface_temperature": first_existing(ds, ["t_surf"]),
        "snow_height": first_existing(ds, ["snow_height"]),
        "battery_voltage": first_existing(ds, ["batt_v"]),
    }

    print("Detected variables:")
    for key, value in mapping.items():
        print(f"  {key}: {value}")

    times = pd.to_datetime(ds[time_name].values, utc=True)

    if len(times) == 0:
        raise RuntimeError("Dataset contains no timestamps.")

    latest_index = len(times) - 1
    start_index = max(0, len(times) - HISTORY_HOURS)

    latest = {
        "time": times[latest_index].isoformat()
    }

    for output_name, variable_name in mapping.items():
        if variable_name is None:
            latest[output_name] = None
        else:
            latest[output_name] = safe_value(
                ds[variable_name].isel({time_name: latest_index}).values
            )

    history = []

    for i in range(start_index, len(times)):
        row = {
            "time": times[i].isoformat()
        }

        for output_name in [
            "temperature",
            "humidity",
            "wind_speed",
            "pressure",
            "shortwave_down",
            "surface_temperature",
            "snow_height"
        ]:
            variable_name = mapping[output_name]

            if variable_name is None:
                row[output_name] = None
            else:
                row[output_name] = safe_value(
                    ds[variable_name].isel({time_name: i}).values
                )

        history.append(row)

    payload = {
        "station": {
            "id": "MIT_B",
            "name": "MIT_B Weather Station",
            "source": "GEUS / PROMICE",
            "source_url": DATA_URL
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest": latest,
        "history": history
    }

    OUTFILE.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8"
    )

    print(f"Wrote {OUTFILE}")
    print(f"Latest observation: {latest['time']}")
    print(f"History records: {len(history)}")

    ds.close()


if __name__ == "__main__":
    main()
