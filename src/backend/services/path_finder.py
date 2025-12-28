from typing import List, Dict, Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)

class PathFinder:
    def __init__(self):
        self.graph_builder = None
    
    def set_graph_builder(self, graph_builder):
        """Set reference to graph builder for single-route checking"""
        self.graph_builder = graph_builder
    
    def find_optimal_path(
        self, 
        connections: List[Dict], 
        start: str, 
        goal: str,
        prefer_fewer_transfers: bool = True
    ) -> Optional[List[Dict]]:
        """
        Find optimal path with intelligent transfer minimization.
        First checks if destination is reachable on a single route.
        """
        logger.info(f"Pathfinding from {start} to {goal}")
        
        # PRIORITY 1: Check if we can reach goal on a single route (no transfers)
        if self.graph_builder:
            single_route = self.graph_builder.can_reach_on_single_route(start, goal)
            if single_route:
                logger.info(f"Found direct route: {single_route['route_name']} "
                           f"({single_route['num_stops']} stops, no transfers)")
                
                # Build path from the single route
                path = []
                stops = single_route['stops_between']
                for i in range(len(stops) - 1):
                    path.append({
                        "from": stops[i],
                        "to": stops[i+1],
                        "route": single_route['route_id'],
                        "route_name": single_route['route_name'],
                        "pattern": single_route['pattern'],
                        "duration_minutes": 3
                    })
                
                return path
        
        # PRIORITY 2: Use BFS with transfer penalty
        return self._bfs_with_transfer_penalty(connections, start, goal, prefer_fewer_transfers)
    
    def _bfs_with_transfer_penalty(
        self,
        connections: List[Dict],
        start: str,
        goal: str,
        prefer_fewer_transfers: bool
    ) -> Optional[List[Dict]]:
        """
        BFS that heavily penalizes transfers.
        Uses a priority queue based on: (num_transfers, num_stops, path)
        """
        import heapq
        
        # Build adjacency list grouped by route
        from collections import defaultdict
        graph = defaultdict(list)
        
        for conn in connections:
            graph[conn["from"]].append(conn)
        
        if start not in graph:
            logger.warning(f"Start stop {start} has no outgoing connections")
            if start == goal:
                return []
            return None
        
        # Priority queue: (transfers, stops, current_stop, path, current_route, current_pattern)
        pq = [(0, 0, start, [], None, None)]
        visited = {}  # (stop, route_pattern) -> (transfers, stops)
        
        best_solution = None
        best_transfers = float('inf')
        
        while pq:
            transfers, stops, current, path, current_route, current_pattern = heapq.heappop(pq)
            
            # Found goal
            if current == goal:
                if transfers < best_transfers or best_solution is None:
                    best_solution = path
                    best_transfers = transfers
                    logger.info(f"Found path with {transfers} transfers, {stops} stops")
                
                # If we found a solution with 0 or 1 transfers, that's optimal enough
                if transfers <= 1:
                    break
                
                continue
            
            # Skip if we've visited this state with fewer/equal transfers
            state = (current, current_pattern)
            if state in visited:
                prev_transfers, prev_stops = visited[state]
                if transfers > prev_transfers or (transfers == prev_transfers and stops >= prev_stops):
                    continue
            
            visited[state] = (transfers, stops)
            
            # Explore neighbors
            if current not in graph:
                continue
            
            # Group connections by route for better transfer handling
            connections_by_route = defaultdict(list)
            for conn in graph[current]:
                route_key = conn.get("pattern", conn["route"])
                connections_by_route[route_key].append(conn)
            
            # Process same-route connections first (no transfer)
            if current_pattern and current_pattern in connections_by_route:
                for conn in connections_by_route[current_pattern]:
                    next_stop = conn["to"]
                    new_path = path + [conn]
                    heapq.heappush(pq, (
                        transfers,  # Same route = no new transfer
                        stops + 1,
                        next_stop,
                        new_path,
                        conn["route"],
                        conn.get("pattern", conn["route"])
                    ))
            
            # Then process other routes (transfer required)
            for route_key, conns in connections_by_route.items():
                if route_key == current_pattern:
                    continue  # Already processed
                
                for conn in conns:
                    next_stop = conn["to"]
                    new_path = path + [conn]
                    new_transfers = transfers + (1 if current_route is not None else 0)
                    
                    heapq.heappush(pq, (
                        new_transfers,
                        stops + 1,
                        next_stop,
                        new_path,
                        conn["route"],
                        conn.get("pattern", conn["route"])
                    ))
        
        if best_solution:
            logger.info(f"Best path: {best_transfers} transfers, {len(best_solution)} stops")
            return best_solution
        
        logger.warning(f"No path found from {start} to {goal}")
        return None
    
    def count_transfers(self, path: List[Dict]) -> int:
        """Count number of transfers in a path"""
        if not path:
            return 0
        
        transfers = 0
        current_route = path[0]["route"]
        
        for segment in path[1:]:
            if segment["route"] != current_route:
                transfers += 1
                current_route = segment["route"]
        
        return transfers