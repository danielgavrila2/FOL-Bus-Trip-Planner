from typing import List, Dict, Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)

class PathFinder:
    def find_optimal_path(
        self, 
        connections: List[Dict], 
        start: str, 
        goal: str,
        prefer_fewer_transfers: bool = True
    ) -> Optional[List[Dict]]:
        """
        Find optimal path using BFS (fewest stops) or modified Dijkstra (fewest transfers)
        """
        # Build adjacency list
        graph = {}
        for conn in connections:
            if conn["from"] not in graph:
                graph[conn["from"]] = []
            graph[conn["from"]].append(conn)
        
        logger.info(f"Pathfinding from {start} to {goal}")
        logger.info(f"Start node in graph: {start in graph}")
        logger.info(f"Goal node exists in stops: {goal in [c['to'] for c in connections] or goal in graph}")
        
        if start not in graph:
            logger.warning(f"Start stop {start} has no outgoing connections")
            # Check if start equals goal
            if start == goal:
                return []
            return None
        
        # BFS with path tracking
        queue = deque([(start, [], None)])  # (current_stop, path, current_route)
        visited = {start}
        nodes_explored = 0
        
        while queue:
            current, path, current_route = queue.popleft()
            nodes_explored += 1
            
            if nodes_explored % 100 == 0:
                logger.debug(f"Explored {nodes_explored} nodes, queue size: {len(queue)}")
            
            if current == goal:
                logger.info(f"Path found! Length: {len(path)}, Nodes explored: {nodes_explored}")
                return path
            
            if current not in graph:
                continue
            
            # Sort by route preference (prefer same route to minimize transfers)
            neighbors = graph[current]
            if prefer_fewer_transfers and current_route:
                neighbors = sorted(
                    neighbors, 
                    key=lambda x: 0 if x["route"] == current_route else 1
                )
            
            for conn in neighbors:
                next_stop = conn["to"]
                if next_stop not in visited:
                    visited.add(next_stop)
                    new_path = path + [conn]
                    queue.append((next_stop, new_path, conn["route"]))
        
        logger.warning(f"No path found from {start} to {goal}. Explored {nodes_explored} nodes, visited {len(visited)} stops")
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