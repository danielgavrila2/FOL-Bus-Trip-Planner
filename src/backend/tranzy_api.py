import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TRANZY_API_KEY")
AGENCY_ID = "2"  # For Cluj-Napoca

BASE_URL = "https://api.tranzy.ai/v1/opendata"

HEADERS = {
    "Accept": "application/json",
    "X-API-KEY": API_KEY,
    "X-Agency-Id": AGENCY_ID
}

def fetch_stops():
    r = requests.get(f"{BASE_URL}/stops", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()

def fetch_trips():
    r = requests.get(f"{BASE_URL}/trips", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()

def fetch_routes():
    r = requests.get(f"{BASE_URL}/routes", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    print(fetch_routes())
    # print(fetch_stops())
    # print(fetch_trips())