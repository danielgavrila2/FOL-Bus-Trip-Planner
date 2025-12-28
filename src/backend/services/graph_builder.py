from typing import List, Dict, Any, Optional, Set, Tuple
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
        # New: Store route patterns (each direction separately)
        self.route_patterns: Dict[str, List[str]] = {}  # route_id+direction -> ordered stop list
        # New: Adjacency list for quick neighbor lookup
        self.stop_neighbors: Dict[str, List[Dict]] = {}  # stop_id -> [{to, route, route_name}]
    
    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters using Haversine formula"""
        R = 6371000  # Earth radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def find_stops_along_shape(self, shape_points: List[Dict], threshold_meters: float = 20) -> List[str]:
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
    
    def extract_direction_from_shape_id(self, shape_id: str) -> Tuple[str, str]:
        """
        Extract route base and direction from shape_id.
        Examples: "35_0" -> ("35", "0"), "35_1" -> ("35", "1")
        """
        parts = shape_id.split('_')
        if len(parts) >= 2:
            return '_'.join(parts[:-1]), parts[-1]
        return shape_id, "0"
    
    def build_graph(self, stops: List[Dict], routes: List[Dict], trips: List[Dict] = None, 
                    stop_times: List[Dict] = None, shapes: List[Dict] = None):
        """Build graph from stops, routes, trips, stop_times, and shapes data"""
        # Index stops
        for stop in stops:
            stop_id = str(stop.get("stop_id", stop.get("id", "")))
            if not stop_id:
                continue
                
            self.stops[stop_id] = stop
            self.stop_neighbors[stop_id] = []
            
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
        
        # Build connections using shapes (considering direction)
        if trips and self.shapes:
            logger.info("Building connections using shape-based matching with directions...")
            self._build_connections_from_shapes_with_direction(trips)
        elif trips and stop_times:
            logger.info("Building connections from trips and stop_times...")
            self._build_connections_from_trips(trips, stop_times)
        else:
            logger.warning("No trips, stop_times, or shapes provided")
        
        # Build adjacency list for fast neighbor lookup
        self._build_adjacency_list()
        
        logger.info(f"Built graph: {len(self.stops)} stops, {len(self.routes)} routes, "
                   f"{len(self.connections)} connections, {len(self.route_patterns)} route patterns")
    
    def _build_connections_from_shapes_with_direction(self, trips: List[Dict], threshold_meters: float = 20):
        """
        Build connections using shape data, treating each direction separately.
        Stores route patterns for direct route checking.
        """
        from collections import defaultdict
        
        # Group trips by route and shape
        route_shapes = defaultdict(set)
        shape_to_route = {}
        
        for trip in trips:
            route_id = str(trip.get("route_id", ""))
            shape_id = str(trip.get("shape_id", ""))
            if route_id and shape_id and shape_id in self.shapes:
                route_shapes[route_id].add(shape_id)
                shape_to_route[shape_id] = route_id
        
        connection_set = set()
        
        # Process each unique shape (each represents a direction)
        for shape_id, shape_points in self.shapes.items():
            route_id = shape_to_route.get(shape_id)
            
            if not route_id or route_id not in self.routes:
                continue
            
            # Find all stops along this shape
            stops_on_route = self.find_stops_along_shape(shape_points, threshold_meters)
            
            if len(stops_on_route) < 2:
                continue
            
            # Store this as a route pattern (route + direction)
            route_base, direction = self.extract_direction_from_shape_id(shape_id)
            pattern_key = f"{route_id}_{direction}"
            self.route_patterns[pattern_key] = stops_on_route
            
            route = self.routes[route_id]
            route_name = route.get("route_short_name", route.get("short_name", route_id))
            
            # Create connections between consecutive stops
            for i in range(len(stops_on_route) - 1):
                from_stop = stops_on_route[i]
                to_stop = stops_on_route[i + 1]
                
                # Use pattern_key to distinguish directions
                conn_key = (from_stop, to_stop, pattern_key)
                if conn_key not in connection_set:
                    connection_set.add(conn_key)
                    
                    self.connections.append({
                        "from": from_stop,
                        "to": to_stop,
                        "route": route_id,
                        "route_name": route_name,
                        "pattern": pattern_key,
                        "duration_minutes": 3  # Reduced from 5 for more realistic times
                    })
        
        logger.info(f"Created {len(self.connections)} connections from {len(self.route_patterns)} route patterns")
    
    def _build_adjacency_list(self):
        """Build adjacency list for O(1) neighbor lookup"""
        for conn in self.connections:
            from_stop = conn["from"]
            if from_stop in self.stop_neighbors:
                self.stop_neighbors[from_stop].append({
                    "to": conn["to"],
                    "route": conn["route"],
                    "route_name": conn["route_name"],
                    "pattern": conn.get("pattern", ""),
                    "duration": conn.get("duration_minutes", 3)
                })
    
    def can_reach_on_single_route(self, start: str, goal: str) -> Optional[Dict]:
        """
        Check if goal can be reached from start using a single route (no transfers).
        Returns route info if possible, None otherwise.
        """
        for pattern_key, stops in self.route_patterns.items():
            if start in stops and goal in stops:
                start_idx = stops.index(start)
                goal_idx = stops.index(goal)
                
                # Check if goal comes after start (correct direction)
                if goal_idx > start_idx:
                    route_id = pattern_key.rsplit('_', 1)[0]
                    if route_id in self.routes:
                        route = self.routes[route_id]
                        return {
                            "route_id": route_id,
                            "route_name": route.get("route_short_name", route.get("short_name", route_id)),
                            "pattern": pattern_key,
                            "stops_between": stops[start_idx:goal_idx+1],
                            "num_stops": goal_idx - start_idx
                        }
        
        return None
    
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
                            "duration_minutes": 3
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
