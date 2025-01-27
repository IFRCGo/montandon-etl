import requests
import json
import os


# This is a secret key. This should be imported from env
client_id = "IDMCWSHSOLO009"

params = {"client_id": client_id}
headers = {"accept": "application/json"}


def get_disaggregated_geojson_data():
    base_url = "https://helix-tools-api.idmcdb.org/external-api/gidd/disaggregations/disaggregation-geojson/"

    try:
        response = requests.get(base_url, headers=headers, params=params)

        response_data = response.json()

        output_dir = "../../../../../tmp/gidd/"
        file_path = os.path.join(output_dir, "gidd_disaggregated.geojson")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(response_data, file, indent=4)

        print(f"GeoJSON data successfully saved to {file_path}")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")


def get_idu_last_180_days_data():
    base_url = "https://helix-tools-api.idmcdb.org/external-api/idus/last-180-days/"

    try:
        response = requests.get(base_url, headers=headers, params=params)
        response_data = response.json()

        output_dir = "../../../../../tmp/iduy"
        file_path = os.path.join(output_dir, "idu_data.json")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(response_data, file, indent=4)

        print(f"IDU last 180 days data successfully saved to {file_path}")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")


get_disaggregated_geojson_data()
get_idu_last_180_days_data()
