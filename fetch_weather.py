import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import requests


# GEUS Dataverse dataset
DATASET_API = (
    "https://dataverse.geus.dk/api/datasets/:persistentId/"
    "?persistentId=doi:10.22008/FK2/IW73UU"
)

OUTFILE = Path(__file__).with_name("weather.json")
CSVFILE = Path(__file__).with_name("SER_B_hour.csv")

HISTORY_HOURS = 7 * 24


def first_existing(columns, candidates):
    for name in candidates:
        if name in columns:
            return name
    return None


def clean_value(value):
    if pd.isna(value):
        return None

    try:
        return float(value)
    except Exception:
        return None


def find_ser_b_hour_file():
    print("Finding current SER_B_hour.csv in GEUS Dataverse...")

    response = requests.get(
        DATASET_API,
        timeout=120
    )

    response.raise_for_status()

    metadata = response.json()

    files = metadata["data"]["latestVersion"]["files"]

    for item in files:
        data_file = item.get("dataFile", {})

        if data_file.get("filename") == "SER_B_hour.csv":
            file_id = data_file["id"]

            print(f"Found SER_B_hour.csv")
            print(f"Dataverse file ID: {file_id}")

            return file_id

    raise RuntimeError(
        "Could not find SER_B_hour.csv in the current GEUS Dataverse dataset."
    )


def download_file(file_id):
    download_url = (
        f"https://dataverse.geus.dk/api/access/datafile/{file_id}"
    )

    print("Downloading SER_B_hour.csv...")

    response = requests.get(
        download_url,
        timeout=300,
        allow_redirects=True
    )

    response.raise_for_status()

    CSVFILE.write_bytes(response.content)

    print(
        f"Download completed: "
        f"{len(response.content) / 1024 / 1024:.2f} MB"
    )

    return download_url


def main():

    file_id = find_ser_b_hour_file()

    download_url = download_file(file_id)

    print("Reading CSV...")

    df = pd.read_csv(CSVFILE)

    print("Columns found:")
    print(list(df.columns))

    time_col = first_existing(
        df.columns,
        [
            "time",
            "timestamp",
            "datetime",
            "date"
        ]
    )

    if time_col is None:
        raise RuntimeError(
            f"No time column found. Columns are: {list(df.columns)}"
        )

    df[time_col] = pd.to_datetime(
        df[time_col],
        utc=True,
        errors="coerce"
    )

    df = (
        df
        .dropna(subset=[time_col])
        .sort_values(time_col)
    )

    mapping = {

        "temperature":
            first_existing(
                df.columns,
                ["t_u", "t_i", "air_temperature"]
            ),

        "humidity":
            first_existing(
                df.columns,
                ["rh_u", "rh_i", "relative_humidity"]
            ),

        "wind_speed":
            first_existing(
                df.columns,
                ["wspd_u", "wspd_i", "wind_speed"]
            ),

        "wind_direction":
            first_existing(
                df.columns,
                ["wdir_u", "wdir_i", "wind_direction"]
            ),

        "pressure":
            first_existing(
                df.columns,
                ["p_u", "p_i", "air_pressure"]
            ),

        "shortwave_down":
            first_existing(
                df.columns,
                ["dsr"]
            ),

        "shortwave_up":
            first_existing(
                df.columns,
                ["usr"]
            ),

        "longwave_down":
            first_existing(
                df.columns,
                ["dlr"]
            ),

        "longwave_up":
            first_existing(
                df.columns,
                ["ulr"]
            ),

        "surface_temperature":
            first_existing(
                df.columns,
                ["t_surf"]
            ),

        "snow_height":
            first_existing(
                df.columns,
                ["snow_height"]
            ),

        "battery_voltage":
            first_existing(
                df.columns,
                ["batt_v"]
            )
    }

    print("")
    print("Detected weather variables:")

    for key, value in mapping.items():
        print(f"{key}: {value}")

    if len(df) == 0:
        raise RuntimeError(
            "The downloaded SER_B file contains no valid observations."
        )

    latest = df.iloc[-1]

    history_df = df.tail(HISTORY_HOURS)

    payload = {

        "station": {
            "id": "SER_B",
            "name": "SER_B Weather Station",
            "source": "GEUS / PROMICE Dataverse",
            "source_url": download_url
        },

        "generated_at":
            datetime.now(timezone.utc).isoformat(),

        "latest": {
            "time": latest[time_col].isoformat()
        },

        "history": []
    }

    for output_name, column_name in mapping.items():

        if column_name is None:
            payload["latest"][output_name] = None

        else:
            payload["latest"][output_name] = clean_value(
                latest[column_name]
            )

    for _, row in history_df.iterrows():

        item = {
            "time": row[time_col].isoformat()
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

            column_name = mapping[output_name]

            if column_name is None:
                item[output_name] = None

            else:
                item[output_name] = clean_value(
                    row[column_name]
                )

        payload["history"].append(item)

    OUTFILE.write_text(
        json.dumps(
            payload,
            indent=2
        ),
        encoding="utf-8"
    )

    print("")
    print("SUCCESS")
    print(f"Station: SER_B")
    print(f"Latest observation: {payload['latest']['time']}")
    print(
        f"Weather history written: "
        f"{len(payload['history'])} hourly records"
    )


if __name__ == "__main__":
    main()
