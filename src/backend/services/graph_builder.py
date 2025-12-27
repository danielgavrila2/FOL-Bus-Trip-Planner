import logging

logger = logging.getLogger(__name__)

class GraphBuilder:
    def __init__(self):
        self.stops = {}
        self.routes = {}
        self.connections = []
        self.stop_name_to_id = {}

    def build_graph(self, stops, routes):
        # Index the stops
        for stop in stops:
            stop_id = str(stop.get("id", stop.get("stop_id")))
            self.stops[stop_id] = stop

            # Create name mapping for flexible lookup
            name = stop.get("name", "").lower().strip()
            if name:
                self.stop_name_to_id[name] = stop_id

        # Index the routes and link the connections
        for route in routes:
            route_id = str(route.get("id", route.get("route_id")))
            self.routes[route_id] = route

            route_stops = route.get("stops", [])

            for i in range(len(route_stops) - 1):
                from_stop = str(route_stops[i].get("id", route_stops[i].get("stop_id")))
                to_stop = str(route_stops[i+1].get("id", route_stops[i+1].get("stop_id")))

                if from_stop in self.stops and to_stop in self.stops:
                    self.connections.append({
                        "from": from_stop,
                        "to": to_stop,
                        "route": route_id,
                        "route_name": route.get("short_name", route_id),
                        "duration_minutes": 5 # default estimation
                    })

        logger.info(f"Built graph: {len(self.stops)} stops, {len(self.routes)} routes, {len(self.connections)} connections")
    
    def resolve_stop(self, stop_identifier: str):
        if stop_identifier in self.stops:
            return stop_identifier
        
        normalized = stop_identifier.lower().strip()

        if normalized in self.stop_name_to_id:
            return self.stop_name_to_id[normalized]
        
        for name, stop_id in self.stop_name_to_id.items():
            if normalized in name or name in normalized:
                return stop_id
            
        return None