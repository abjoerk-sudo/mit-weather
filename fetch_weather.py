import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import requests


THREDDS_URL = (
    "https://thredds.geus.dk/thredds/fileServer/"
    "aws/l3sites/csv/hour/SER_B_hour.csv"
)

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


def download_from_thredds():
    print("Trying GEUS THREDDS...")

    response = requests.get(
        THREDDS_URL,
        timeout=120,
        allow_redirects=True
    )

    response.raise_for_status()

    CSVFILE.write_bytes(response.content)

    print(
        f"THREDDS download successful: "
        f"{len(response.content) / 1024 / 1024:.2f} MB"
    )

    return {
        "source": "GEUS THREDDS",
        "source_url": THREDDS_URL
    }


def find_dataverse_file():
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
            return data_file["id"]

    raise RuntimeError(
        "Could not find SER_B_hour.csv in GEUS Dataverse."
    )


def download_from_dataverse():
    print("Trying GEUS Dataverse fallback...")

    file_id = find_dataverse_file()

    download_url = (
        f"https://dataverse.geus.dk/api/access/datafile/{file_id}"
    )

    response = requests.get(
        download_url,
        timeout=300,
        allow_redirects=True
    )

    response.raise_for_status()

    CSVFILE.write_bytes(response.content)

    print(
        f"Dataverse download successful: "
        f"{len(response.content) / 1024 / 1024:.2f} MB"
    )

    return {
        "source": "GEUS Dataverse fallback",
        "source_url": download_url
    }


def download_data():
    try:
        return download_from_thredds()

    except Exception as error:
        print("")
        print("THREDDS failed.")
        print(f"Reason: {error}")
        print("")
        print("Switching automatically to Dataverse...")
        print("")

        return download_from_dataverse()


def main():

    source_info = download_data()

    print("")
    print("Reading SER_B CSV...")

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

    if len(df) == 0:
        raise RuntimeError(
            "SER_B file contains no valid observations."
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

    latest = df.iloc[-1]

    history_df = df.tail(HISTORY_HOURS)

    payload = {

        "station": {
            "id": "SER_B",
            "name": "SER_B Weather Station",
            "source": source_info["source"],
            "source_url": source_info["source_url"]
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
    print("Station: SER_B")
    print(f"Data source used: {source_info['source']}")
    print(f"Latest observation: {payload['latest']['time']}")
    print(
        f"Weather history written: "
        f"{len(payload['history'])} hourly records"
    )


if __name__ == "__main__":
    main()
