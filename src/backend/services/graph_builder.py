from typing import List, Dict, Any, Optional
import logging
import math

logger = logging.getLogger(__name__)

class GraphBuilder:
    def __init__(self):
        self.stops: Dict[str, Dict] = {}
        self.routes: Dict[str, Dict] = {}
        self.connections: List[Dict[str, Any]] = []
        self.stop_name_to_id: Dict[str, str] = {}
        self.shapes: Dict[str, List[Dict]] = {}
    
    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points in meters using Haversine formula
        """
        R = 6371000  # Earth radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def find_stops_along_shape(self, shape_points: List[Dict], threshold_meters: float = 50) -> List[str]:
        """
        Find all stops that are within threshold distance of the shape path.
        Returns stops in order along the shape.
        """
        stops_on_route = []
        
        for stop_id, stop in self.stops.items():
            stop_lat = stop.get("stop_lat", stop.get("lat"))
            stop_lon = stop.get("stop_lon", stop.get("lon"))
            
            if stop_lat is None or stop_lon is None:
                continue
            
            # Find closest point on shape to this stop
            min_distance = float('inf')
            closest_sequence = -1
            
            for point in shape_points:
                point_lat = point.get("shape_pt_lat", point.get("lat"))
                point_lon = point.get("shape_pt_lon", point.get("lon"))
                point_seq = point.get("shape_pt_sequence", point.get("sequence", 0))
                
                if point_lat is None or point_lon is None:
                    continue
                
                distance = self.haversine_distance(stop_lat, stop_lon, point_lat, point_lon)
                
                if distance < min_distance:
                    min_distance = distance
                    closest_sequence = point_seq
            
            # If stop is within threshold, add it with its sequence
            if min_distance <= threshold_meters:
                stops_on_route.append({
                    "stop_id": stop_id,
                    "sequence": closest_sequence,
                    "distance": min_distance
                })
        
        # Sort by sequence to get stops in order
        stops_on_route.sort(key=lambda x: x["sequence"])
        
        return [s["stop_id"] for s in stops_on_route]
    
    def build_graph(self, stops: List[Dict], routes: List[Dict], trips: List[Dict] = None, 
                    stop_times: List[Dict] = None, shapes: List[Dict] = None):
        """Build graph from stops, routes, trips, stop_times, and shapes data"""
        # Index stops
        for stop in stops:
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
        
        # Index shapes by shape_id
        if shapes:
            logger.info(f"Processing {len(shapes)} shape points...")
            from collections import defaultdict
            shape_groups = defaultdict(list)
            
            for shape_point in shapes:
                shape_id = str(shape_point.get("shape_id", ""))
                if shape_id:
                    shape_groups[shape_id].append(shape_point)
            
            # Sort each shape by sequence
            for shape_id, points in shape_groups.items():
                self.shapes[shape_id] = sorted(
                    points, 
                    key=lambda x: x.get("shape_pt_sequence", x.get("sequence", 0))
                )
            
            logger.info(f"Indexed {len(self.shapes)} unique shapes")
        
        # Build connections using shapes
        if trips and self.shapes:
            logger.info("Building connections using shape-based matching...")
            self._build_connections_from_shapes(trips)
        elif trips and stop_times:
            logger.info("Building connections from trips and stop_times...")
            self._build_connections_from_trips(trips, stop_times)
        else:
            logger.warning("No trips, stop_times, or shapes provided, connections may be limited")
        
        logger.info(f"Built graph: {len(self.stops)} stops, {len(self.routes)} routes, {len(self.connections)} connections")
    
    def _build_connections_from_shapes(self, trips: List[Dict], threshold_meters: float = 20):
        """
        Build connections using shape data to match stops.
        This provides more accurate connections than stop_times alone.
        """
        from collections import defaultdict
        
        # Group trips by route
        route_trips = defaultdict(list)
        for trip in trips:
            route_id = str(trip.get("route_id", ""))
            shape_id = str(trip.get("shape_id", ""))
            if route_id and shape_id:
                route_trips[route_id].append({
                    "trip_id": trip.get("trip_id"),
                    "shape_id": shape_id
                })
        
        connection_set = set()
        
        for route_id, trip_list in route_trips.items():
            if route_id not in self.routes:
                continue
            
            # Use first trip's shape as representative for the route
            shape_id = trip_list[0]["shape_id"]
            
            if shape_id not in self.shapes:
                continue
            
            shape_points = self.shapes[shape_id]
            
            # Find all stops along this shape
            stops_on_route = self.find_stops_along_shape(shape_points, threshold_meters)
            
            if len(stops_on_route) < 2:
                continue
            
            route = self.routes[route_id]
            route_name = route.get("route_short_name", route.get("short_name", route_id))
            
            # Create connections between consecutive stops
            for i in range(len(stops_on_route) - 1):
                from_stop = stops_on_route[i]
                to_stop = stops_on_route[i + 1]
                
                conn_key = (from_stop, to_stop, route_id)
                if conn_key not in connection_set:
                    connection_set.add(conn_key)
                    
                    self.connections.append({
                        "from": from_stop,
                        "to": to_stop,
                        "route": route_id,
                        "route_name": route_name,
                        "duration_minutes": 5  # Default estimate
                    })
        
        logger.info(f"Created {len(self.connections)} connections using shape matching")
    
    def _build_connections_from_trips(self, trips: List[Dict], stop_times: List[Dict]):
        """Build connections from trips and stop_times (fallback method)"""
        from collections import defaultdict
        
        trip_stops = defaultdict(list)
        
        for st in stop_times:
            trip_id = str(st.get("trip_id", ""))
            if trip_id:
                trip_stops[trip_id].append(st)
        
        for trip_id in trip_stops:
            trip_stops[trip_id].sort(key=lambda x: x.get("stop_sequence", 0))
        
        trip_to_route = {}
        for trip in trips:
            trip_id = str(trip.get("trip_id", ""))
            route_id = str(trip.get("route_id", ""))
            if trip_id and route_id:
                trip_to_route[trip_id] = route_id
        
        connection_set = set()
        
        for trip_id, stops_sequence in trip_stops.items():
            route_id = trip_to_route.get(trip_id)
            if not route_id or route_id not in self.routes:
                continue
            
            for i in range(len(stops_sequence) - 1):
                from_stop = str(stops_sequence[i].get("stop_id", ""))
                to_stop = str(stops_sequence[i + 1].get("stop_id", ""))
                
                if from_stop and to_stop and from_stop in self.stops and to_stop in self.stops:
                    conn_key = (from_stop, to_stop, route_id)
                    if conn_key not in connection_set:
                        connection_set.add(conn_key)
                        
                        route = self.routes[route_id]
                        self.connections.append({
                            "from": from_stop,
                            "to": to_stop,
                            "route": route_id,
                            "route_name": route.get("route_short_name", route.get("short_name", route_id)),
                            "duration_minutes": 5
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