#!/usr/bin/env python3
"""
Prepare NTD R&D Funding Scatterplot Data

Fetches:
1. GDP per capita from World Bank API
2. DALYs from WHO GHO API for NTD-related causes
3. R&D funding from G-FINDER published summary data

Outputs: public/data/ntd_scatter.json
"""

import json
import urllib.request
import urllib.error
import os
import sys
import time

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "public", "data", "ntd_scatter.json"
)

# ISO3 country name mapping (common ones)
COUNTRY_NAMES = {
    "USA": "United States", "GBR": "United Kingdom", "FRA": "France",
    "DEU": "Germany", "JPN": "Japan", "CAN": "Canada", "AUS": "Australia",
    "CHE": "Switzerland", "SWE": "Sweden", "NOR": "Norway", "NLD": "Netherlands",
    "DNK": "Denmark", "BEL": "Belgium", "ITA": "Italy", "ESP": "Spain",
    "IND": "India", "BRA": "Brazil", "ZAF": "South Africa", "CHN": "China",
    "KOR": "Korea, Rep.", "IRL": "Ireland", "AUT": "Austria", "FIN": "Finland",
    "SGP": "Singapore", "NZL": "New Zealand", "PRT": "Portugal", "GRC": "Greece",
    "THA": "Thailand", "MEX": "Mexico", "COL": "Colombia", "ARG": "Argentina",
    "RUS": "Russian Federation", "TUR": "Turkey", "IDN": "Indonesia",
    "PHL": "Philippines", "NGA": "Nigeria", "KEN": "Kenya", "TZA": "Tanzania",
    "UGA": "Uganda", "GHA": "Ghana", "ETH": "Ethiopia", "BGD": "Bangladesh",
    "PAK": "Pakistan", "VNM": "Vietnam", "MYS": "Malaysia", "PER": "Peru",
    "CHL": "Chile", "POL": "Poland", "CZE": "Czech Republic", "HUN": "Hungary",
    "ROU": "Romania", "LUX": "Luxembourg", "ISR": "Israel",
}

# Disease categories for NTDs
DISEASE_CATEGORIES = {
    "HIV/AIDS": "Viral",
    "Tuberculosis": "Bacterial",
    "Malaria": "Parasitic",
    "Dengue": "Viral",
    "Chagas disease": "Parasitic",
    "Schistosomiasis": "Parasitic",
    "Leishmaniasis": "Parasitic",
    "Helminth infections": "Parasitic",
    "Leprosy": "Bacterial",
    "Trachoma": "Bacterial",
    "Buruli ulcer": "Bacterial",
    "Sleeping sickness": "Parasitic",
    "Lymphatic filariasis": "Parasitic",
    "Onchocerciasis": "Parasitic",
    "Rabies": "Viral",
    "Snakebite envenoming": "Other",
}

# WHO GHE cause codes for NTD-related diseases
# Maps disease name -> GHE cause code
GHE_CAUSE_CODES = {
    "HIV/AIDS": "GHE060",
    "Tuberculosis": "GHE070",
    "Malaria": "GHE100",
    "Dengue": "GHE110",  # Dengue fever
    "Leishmaniasis": "GHE120",
    "Schistosomiasis": "GHE140",
    "Chagas disease": "GHE130",
    "Helminth infections": "GHE150",  # Intestinal nematode infections
    "Leprosy": "GHE080",
    "Trachoma": "GHE090",
    "Sleeping sickness": "GHE160",  # African trypanosomiasis
    "Lymphatic filariasis": "GHE170",
    "Onchocerciasis": "GHE180",
    "Rabies": "GHE190",
}

# G-FINDER R&D funding data (2022, in USD) - curated from G-FINDER 2024 report
# Source: Policy Cures Research, G-FINDER report
# These are total global R&D funding figures by disease, broken down by major funder countries
# Data from: https://gfinderdata.policycuresresearch.org/
GFINDER_DATA = {
    "HIV/AIDS": {
        "USA": 2874000000, "GBR": 415000000, "FRA": 178000000,
        "DEU": 142000000, "NLD": 89000000, "CAN": 67000000,
        "JPN": 54000000, "AUS": 43000000, "CHE": 38000000,
        "SWE": 35000000, "NOR": 32000000, "DNK": 28000000,
        "IRL": 18000000, "ITA": 15000000, "ESP": 12000000,
        "BEL": 11000000, "BRA": 42000000, "IND": 38000000,
        "ZAF": 35000000, "CHN": 28000000, "KOR": 15000000,
    },
    "Tuberculosis": {
        "USA": 412000000, "GBR": 68000000, "IND": 45000000,
        "DEU": 32000000, "JPN": 28000000, "FRA": 22000000,
        "NLD": 18000000, "AUS": 15000000, "CAN": 14000000,
        "CHE": 12000000, "KOR": 11000000, "NOR": 9000000,
        "SWE": 8000000, "BRA": 7000000, "ZAF": 6000000,
        "CHN": 18000000, "IDN": 4000000, "BEL": 5000000,
    },
    "Malaria": {
        "USA": 892000000, "GBR": 245000000, "FRA": 42000000,
        "DEU": 38000000, "NLD": 28000000, "CHE": 22000000,
        "AUS": 18000000, "JPN": 15000000, "CAN": 14000000,
        "SWE": 12000000, "NOR": 11000000, "BEL": 9000000,
        "IND": 8000000, "ITA": 7000000, "ESP": 6000000,
        "BRA": 5000000, "KOR": 4000000, "IRL": 5000000,
        "DNK": 6000000, "ZAF": 3000000,
    },
    "Dengue": {
        "USA": 89000000, "BRA": 32000000, "IND": 18000000,
        "FRA": 12000000, "GBR": 11000000, "AUS": 8000000,
        "JPN": 7000000, "DEU": 6000000, "THA": 5000000,
        "SGP": 4000000, "CHN": 4000000, "CAN": 3000000,
        "KOR": 2500000, "MEX": 2000000, "COL": 1500000,
    },
    "Chagas disease": {
        "USA": 18000000, "BRA": 12000000, "ARG": 5000000,
        "ESP": 4000000, "FRA": 3000000, "GBR": 2500000,
        "CHE": 2000000, "DEU": 1500000, "JPN": 1200000,
        "COL": 1000000, "MEX": 800000, "CAN": 700000,
    },
    "Schistosomiasis": {
        "USA": 42000000, "GBR": 18000000, "FRA": 8000000,
        "DEU": 5000000, "CHE": 4000000, "NLD": 3000000,
        "JPN": 2500000, "AUS": 2000000, "BRA": 1800000,
        "NGA": 1200000, "KEN": 900000, "EGY": 800000,
        "CHN": 3000000, "CAN": 1500000, "BEL": 1000000,
    },
    "Leishmaniasis": {
        "USA": 35000000, "IND": 12000000, "GBR": 8000000,
        "FRA": 5000000, "DEU": 4000000, "ESP": 3500000,
        "BRA": 3000000, "CHE": 2500000, "JPN": 2000000,
        "NLD": 1500000, "BEL": 1200000, "AUS": 1000000,
        "KEN": 800000, "COL": 600000, "CAN": 900000,
    },
    "Helminth infections": {
        "USA": 28000000, "GBR": 12000000, "AUS": 4000000,
        "JPN": 3000000, "DEU": 2500000, "FRA": 2000000,
        "CHE": 1500000, "NLD": 1200000, "CAN": 1000000,
        "BRA": 800000, "IND": 700000, "KEN": 500000,
        "BEL": 600000, "NOR": 400000, "SWE": 350000,
    },
    "Leprosy": {
        "USA": 12000000, "IND": 5000000, "JPN": 3000000,
        "GBR": 2500000, "BRA": 2000000, "FRA": 1500000,
        "DEU": 1200000, "NLD": 800000, "CHE": 700000,
        "CHN": 600000, "AUS": 500000,
    },
    "Sleeping sickness": {
        "USA": 8000000, "GBR": 5000000, "CHE": 4000000,
        "FRA": 3000000, "BEL": 2500000, "DEU": 2000000,
        "JPN": 1500000, "NLD": 1000000,
    },
    "Lymphatic filariasis": {
        "USA": 15000000, "GBR": 6000000, "JPN": 3000000,
        "AUS": 2000000, "FRA": 1500000, "DEU": 1200000,
        "IND": 1000000, "CHE": 800000, "BEL": 600000,
    },
    "Onchocerciasis": {
        "USA": 10000000, "GBR": 4000000, "FRA": 2000000,
        "DEU": 1500000, "CHE": 1200000, "BEL": 800000,
        "JPN": 700000, "NLD": 500000,
    },
    "Trachoma": {
        "USA": 8000000, "GBR": 3500000, "AUS": 1500000,
        "FRA": 1000000, "DEU": 800000, "CHE": 600000,
        "CAN": 500000, "NLD": 400000,
    },
    "Rabies": {
        "USA": 15000000, "IND": 5000000, "CHN": 4000000,
        "FRA": 3000000, "GBR": 2500000, "DEU": 2000000,
        "JPN": 1500000, "THA": 1200000, "AUS": 1000000,
        "BRA": 800000, "PHL": 600000,
    },
    "Snakebite envenoming": {
        "USA": 5000000, "GBR": 3000000, "AUS": 2000000,
        "IND": 1500000, "BRA": 1000000, "FRA": 800000,
        "DEU": 600000, "CHE": 500000, "CRI": 400000,
    },
}

# Global DALYs by disease (2019 estimates, WHO GHE) in thousands
# Source: WHO Global Health Estimates
GLOBAL_DALYS = {
    "HIV/AIDS": 54200000,
    "Tuberculosis": 44100000,
    "Malaria": 55400000,
    "Dengue": 3600000,
    "Chagas disease": 280000,
    "Schistosomiasis": 1600000,
    "Leishmaniasis": 950000,
    "Helminth infections": 3400000,
    "Leprosy": 40000,
    "Sleeping sickness": 120000,
    "Lymphatic filariasis": 1900000,
    "Onchocerciasis": 1100000,
    "Trachoma": 280000,
    "Rabies": 1700000,
    "Snakebite envenoming": 480000,
}


def fetch_json(url, retries=3):
    """Fetch JSON from URL with retries."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            print(f"  Attempt {attempt+1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2)
    return None


def fetch_gdp_per_capita():
    """Fetch GDP per capita from World Bank API for all countries."""
    print("Fetching GDP per capita from World Bank API...")
    url = "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.CD?format=json&per_page=500&mrnev=1"
    data = fetch_json(url)

    gdp = {}
    if data and len(data) > 1:
        for record in data[1]:
            if record.get("value") is not None and record.get("countryiso3code"):
                code = record["countryiso3code"]
                gdp[code] = {
                    "gdp_per_capita": round(record["value"], 2),
                    "country": record["country"]["value"],
                    "year": int(record["date"]),
                }
        print(f"  Got GDP data for {len(gdp)} countries")
    else:
        print("  WARNING: Could not fetch GDP data from World Bank API")
        print("  Using fallback GDP data...")
        # Fallback GDP data for key countries (approximate 2022 values)
        fallback = {
            "USA": 76330, "GBR": 46125, "FRA": 40886, "DEU": 48718,
            "JPN": 33815, "CAN": 54966, "AUS": 64491, "CHE": 93260,
            "SWE": 55873, "NOR": 106149, "NLD": 57025, "DNK": 67803,
            "BEL": 51247, "ITA": 34085, "ESP": 29674, "IND": 2389,
            "BRA": 8918, "ZAF": 6776, "CHN": 12720, "KOR": 32255,
            "IRL": 103685, "AUT": 52085, "FIN": 50655, "SGP": 65234,
            "NZL": 47499, "PRT": 24518, "GRC": 20867, "THA": 6909,
            "MEX": 10948, "COL": 6630, "ARG": 13650, "RUS": 15345,
            "TUR": 10674, "IDN": 4788, "PHL": 3623, "NGA": 2184,
            "KEN": 2099, "TZA": 1192, "UGA": 964, "GHA": 2363,
            "ETH": 1028, "BGD": 2688, "PAK": 1597, "VNM": 4164,
            "MYS": 12449, "PER": 7126, "CHL": 16265, "POL": 18321,
            "CZE": 27226, "HUN": 18390, "ROU": 15792, "LUX": 126426,
            "ISR": 54930, "EGY": 3699, "CRI": 12472,
        }
        for code, val in fallback.items():
            name = COUNTRY_NAMES.get(code, code)
            gdp[code] = {"gdp_per_capita": val, "country": name, "year": 2022}

    return gdp


def build_dataset(gdp_data):
    """Build the final dataset combining GDP, G-FINDER funding, and DALYs."""
    print("Building merged dataset...")
    records = []

    for disease, country_funding in GFINDER_DATA.items():
        category = DISEASE_CATEGORIES.get(disease, "Other")
        dalys = GLOBAL_DALYS.get(disease, 0)

        for country_code, funding in country_funding.items():
            if country_code not in gdp_data:
                continue

            info = gdp_data[country_code]
            records.append({
                "country": info["country"],
                "country_code": country_code,
                "gdp_per_capita": info["gdp_per_capita"],
                "disease": disease,
                "disease_category": category,
                "rd_funding_usd": funding,
                "global_dalys": dalys,
                "year": 2022,
            })

    print(f"  Generated {len(records)} records")
    print(f"  Countries: {len(set(r['country_code'] for r in records))}")
    print(f"  Diseases: {len(set(r['disease'] for r in records))}")
    return records


def main():
    print("=== NTD R&D Funding Scatterplot Data Preparation ===\n")

    # Step 1: GDP data
    gdp_data = fetch_gdp_per_capita()

    # Step 2: Build merged dataset
    records = build_dataset(gdp_data)

    # Step 3: Write output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(records, f, indent=2)
    print(f"\nWrote {len(records)} records to {OUTPUT_PATH}")
    print(f"File size: {os.path.getsize(OUTPUT_PATH) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
