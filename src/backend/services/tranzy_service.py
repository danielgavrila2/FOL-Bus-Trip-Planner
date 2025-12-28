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
        self.agency_id = os.getenv("AGENCY_ID", "2")  # Cluj-Napoca
        self.base_url = "https://api.tranzy.ai/v1/opendata"
        
        if not self.api_key:
            raise ValueError("TRANZY_API_KEY not set in environment")
        
        self.headers = {
            "Accept": "application/json",
            "X-API-KEY": self.api_key,
            "X-Agency-Id": self.agency_id
        }
    
    def fetch_stops(self) -> List[Dict[str, Any]]:
        """Fetch all bus stops"""
        try:
            response = requests.get(
                f"{self.base_url}/stops",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Fetched {len(data)} stops")
            return data
        except Exception as e:
            logger.error(f"Error fetching stops: {e}")
            raise
    
    def fetch_routes(self) -> List[Dict[str, Any]]:
        """Fetch all bus routes"""
        try:
            response = requests.get(
                f"{self.base_url}/routes",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Fetched {len(data)} routes")
            return data
        except Exception as e:
            logger.error(f"Error fetching routes: {e}")
            raise
    
    def fetch_trips(self) -> List[Dict[str, Any]]:
        """Fetch all trips (schedules)"""
        try:
            response = requests.get(
                f"{self.base_url}/trips",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Fetched {len(data)} trips")
            return data
        except Exception as e:
            logger.error(f"Error fetching trips: {e}")
            raise
    
    def fetch_stop_times(self) -> List[Dict[str, Any]]:
        """Fetch stop times (stop sequences for trips)"""
        try:
            response = requests.get(
                f"{self.base_url}/stop_times",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Fetched {len(data)} stop times")
            return data
        except Exception as e:
            logger.error(f"Error fetching stop times: {e}")
            raise
    
    def fetch_shapes(self) -> List[Dict[str, Any]]:
        """Fetch shapes (route geometries)"""
        try:
            response = requests.get(
                f"{self.base_url}/shapes",
                headers=self.headers,
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Fetched {len(data)} shape points")
            return data
        except Exception as e:
            logger.error(f"Error fetching shapes: {e}")
            raise
