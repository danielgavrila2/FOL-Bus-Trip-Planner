import os
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

class TranzyService:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("TRANZY_API_KEY")
        self.agency_id = os.getenv("AGENCY_ID", "2") # 2 for Cluj-Napoca
        self.base_url = "https://api.tranzy.ai/v1/opendata"

        if not self.api_key:
            raise ValueError("TRANZY_API_KEY is missing in your environment")
        
        self.headers = {
            "Accept": "application/json",
            "X-API-KEY": self.api_key,
            "X-Agency-Id": self.agency_id
        }

    def fetch_stops(self) -> List[Dict[str, Any]]:
        try:
            r = requests.get(
                f"{self.base_url}/stops", 
                headers=self.headers, 
                timeout=30
            )
            r.raise_for_status()
            data = r.json()

            logger.info(f"Fetched {len(data)} stops")
            
            return data
        except Exception as e:
            logger.error(f"Error fetching stops: {e}")
            raise
        

    def fetch_trips(self) -> List[Dict[str, Any]]:
        try:
            r = requests.get(
                f"{self.base_url}/trips", 
                headers=self.headers, 
                timeout=30
            )
            r.raise_for_status()
            data = r.json()

            logger.info(f"Fetched {len(data)} trips")
            
            return data
        except Exception as e:
            logger.error(f"Error fetching trips: {e}")
            raise

    def fetch_routes(self) -> List[Dict[str, Any]]:
        try:
            r = requests.get(
                f"{self.base_url}/routes", 
                headers=self.headers, 
                timeout=30
            )
            r.raise_for_status()
            data = r.json()

            logger.info(f"Fetched {len(data)} routes")
            
            return data
        except Exception as e:
            logger.error(f"Error fetching routes: {e}")
            raise