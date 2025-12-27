from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class GraphBuilder:
    def __init__(self):
        self.stops: Dict[str, Dict] = {}
        self.routes: Dict[str, Dict] = {}
        self.connections: List[Dict[str, Any]] = []
        self.stop_name_to_id: Dict[str, str] = {}
    
    def build_graph(self, stops: List[Dict], routes: List[Dict], trips: List[Dict] = None, stop_times: List[Dict] = None):
        """Build graph from stops, routes, trips, and stop_times data"""
        # Index stops
        for stop in stops:
            # Handle different field name possibilities
            stop_id = str(stop.get("stop_id", stop.get("id", "")))
            if not stop_id:
                continue
                
            self.stops[stop_id] = stop
            
            # Create name mapping for flexible lookup
            name = stop.get("stop_name", stop.get("name", "")).lower().strip()
            if name:
                self.stop_name_to_id[name] = stop_id
        
        # Index routes
        for route in routes:
            route_id = str(route.get("route_id", route.get("id", "")))
            if not route_id:
                continue
            self.routes[route_id] = route
        
        # Build connections from trips and stop_times
        if trips and stop_times:
            self._build_connections_from_trips(trips, stop_times)
        else:
            logger.warning("No trips or stop_times provided, connections may be limited")
        
        logger.info(f"Built graph: {len(self.stops)} stops, {len(self.routes)} routes, {len(self.connections)} connections")
    
    def _build_connections_from_trips(self, trips: List[Dict], stop_times: List[Dict]):
        """Build connections from trips and stop_times"""
        # Group stop_times by trip_id
        from collections import defaultdict
        trip_stops = defaultdict(list)
        
        for st in stop_times:
            trip_id = str(st.get("trip_id", ""))
            if trip_id:
                trip_stops[trip_id].append(st)
        
        # Sort stop_times by stop_sequence for each trip
        for trip_id in trip_stops:
            trip_stops[trip_id].sort(key=lambda x: x.get("stop_sequence", 0))
        
        # Create map of trip_id to route_id
        trip_to_route = {}
        for trip in trips:
            trip_id = str(trip.get("trip_id", ""))
            route_id = str(trip.get("route_id", ""))
            if trip_id and route_id:
                trip_to_route[trip_id] = route_id
        
        # Build connections
        connection_set = set()  # To avoid duplicates
        
        for trip_id, stops_sequence in trip_stops.items():
            route_id = trip_to_route.get(trip_id)
            if not route_id or route_id not in self.routes:
                continue
            
            # Create connections between consecutive stops
            for i in range(len(stops_sequence) - 1):
                from_stop = str(stops_sequence[i].get("stop_id", ""))
                to_stop = str(stops_sequence[i + 1].get("stop_id", ""))
                
                if from_stop and to_stop and from_stop in self.stops and to_stop in self.stops:
                    # Use tuple to avoid duplicate connections
                    conn_key = (from_stop, to_stop, route_id)
                    if conn_key not in connection_set:
                        connection_set.add(conn_key)
                        
                        route = self.routes[route_id]
                        self.connections.append({
                            "from": from_stop,
                            "to": to_stop,
                            "route": route_id,
                            "route_name": route.get("route_short_name", route.get("short_name", route_id)),
                            "duration_minutes": 5  # Default estimate
                        })
    
    def resolve_stop(self, stop_identifier: str) -> Optional[str]:
        """Resolve stop name or ID to stop ID"""
        # Try as ID first
        if stop_identifier in self.stops:
            return stop_identifier
        
        # Try as name (case-insensitive, fuzzy)
        normalized = stop_identifier.lower().strip()
        
        # Exact match
        if normalized in self.stop_name_to_id:
            return self.stop_name_to_id[normalized]
        
        # Partial match
        for name, stop_id in self.stop_name_to_id.items():
            if normalized in name or name in normalized:
                return stop_id
        
        return None
