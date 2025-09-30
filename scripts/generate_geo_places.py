from __future__ import annotations

import csv
import json
import sys
from io import StringIO
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from newsreader.settings import get_settings

CITIES_URL = "https://simplemaps.com/static/data/world-cities/basic/simplemaps_worldcities_basicv1.75/worldcities.csv"
COUNTRIES_URL = "https://datahub.io/core/country-list/r/data.csv"


def fetch_csv(url: str) -> str:
    print(f"Downloading: {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_cities(csv_text: str) -> set[str]:
    cities: set[str] = set()
    reader = csv.DictReader(StringIO(csv_text))
    for row in reader:
        city = row.get("city")
        if city:
            cities.add(city.strip())
    return cities


def extract_countries(csv_text: str) -> set[str]:
    countries: set[str] = set()
    reader = csv.DictReader(StringIO(csv_text))
    for row in reader:
        country = row.get("Name")
        if country:
            countries.add(country.strip())
    return countries


def main() -> None:
    settings = get_settings()
    output_path = settings.default_geo_places_path

    cities_csv = fetch_csv(CITIES_URL)
    countries_csv = fetch_csv(COUNTRIES_URL)
    cities = extract_cities(cities_csv)
    countries = extract_countries(countries_csv)
    all_places = sorted(cities | countries)
    print(f"Total unique places: {len(all_places)}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(all_places, fh, ensure_ascii=False, indent=2)

    print(f"geo_places list written to {output_path}.")


if __name__ == "__main__":
    main()
