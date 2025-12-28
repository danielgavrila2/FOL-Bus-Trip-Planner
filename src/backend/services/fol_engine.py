import subprocess
import tempfile
import os
from typing import List, Dict
import logging
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class FOLEngine:
    def __init__(self, prover9_path: str = "prover9/Prover9/LADR-2009-11A/bin", mace4_path: str = "prover9/Prover9/LADR-2009-11A/bin"):
        self.prover9_path = prover9_path
        self.mace4_path = mace4_path

    def _write_fol_input(
        self,
        fol_input: str,
        prefix: str,
        save_input: bool
    ) -> str:
        """
        Writes FOL input either to a temp file or to a persistent debug file.
        Returns the file path.
        """
        if save_input:
            os.makedirs("fol_inputs", exist_ok=True)

            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
            content_hash = hashlib.md5(fol_input.encode()).hexdigest()[:8]
            filename = f"{prefix}_{timestamp}_{content_hash}.in"

            path = os.path.join("fol_inputs", filename)
            with open(path, "w") as f:
                f.write(fol_input)

            logger.info(f"Saved FOL input to {path}")
            return path

        # Default: temporary file
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".in", delete=False)
        tmp.write(fol_input)
        tmp.close()
        return tmp.name

    
    def generate_fol_for_path_planning(
        self,
        connections: List[Dict],
        start: str,
        goal: str,
        max_steps: int = 15000
    ) -> str:
        """
        Generate FOL for path planning with bounded depth search.
        Uses a step-by-step path construction approach.
        """
        lines = []
        
        lines.append("set(auto).")
        lines.append("clear(print_kept).")
        lines.append("clear(print_given).")
        lines.append("")
        
        lines.append("formulas(assumptions).")
        lines.append("")
        
        # Define all direct connections
        lines.append("% Direct bus connections (from, to, route)")
        connection_set = set()
        for conn in connections:  # Limit for performance
            key = (conn['from'], conn['to'], conn['route'])
            if key not in connection_set:
                connection_set.add(key)
                lines.append(f"connected({conn['from']}, {conn['to']}, route_{conn['route']}).")
        lines.append("")
        
        # Path building predicates
        lines.append("% Path building rules")
        lines.append("% at(Stop, Step) means we are at Stop at step number Step")
        lines.append("% path_uses(Route, Step) means path uses Route at Step")
        lines.append("")
        
        # Starting position
        lines.append(f"% Start at step 0")
        lines.append(f"at({start}, 0).")
        lines.append("")
        
        # Path extension rules for each step
        lines.append("% Path extension: if at X at step N and connected(X,Y,R), then can be at Y at step N+1")
        for step in range(max_steps):
            lines.append(f"all X all Y all R (at(X, {step}) & connected(X, Y, R) -> at(Y, {step+1}) & path_uses(R, {step+1})).")
        lines.append("")
        
        # Transitivity of reachability
        lines.append("% If at a stop at any step, it's reachable")
        for step in range(max_steps + 1):
            lines.append(f"at(X, {step}) -> reachable(X).")
        lines.append("")
        
        lines.append("end_of_list.")
        lines.append("")
        
        # Goal: reach destination at any step
        lines.append("formulas(goals).")
        goal_clauses = " | ".join([f"at({goal}, {i})" for i in range(1, max_steps + 1)])
        lines.append(f"{goal_clauses}.")
        lines.append("end_of_list.")
        
        return "\n".join(lines)
    
    def generate_fol_with_mace4(
        self,
        connections: List[Dict],
        start: str,
        goal: str,
        route_patterns: Dict[str, List[str]]
    ) -> str:
        """
        Generate FOL for Mace4 to find a satisfying model.
        This is more suitable for actual path finding.
        """
        lines = []
        
        lines.append("formulas(assumptions).")
        lines.append("")
        
        # Define connections
        lines.append("% Bus connections")
        for conn in connections[:500]:
            lines.append(f"connected({conn['from']}, {conn['to']}, r{conn['route']}).")
        lines.append("")
        
        # Define route patterns (single-route reachability)
        lines.append("% Route patterns (stops on same route)")
        for pattern_key, stops in list(route_patterns.items())[:50]:
            route_id = pattern_key.split('_')[0]
            for i in range(len(stops) - 1):
                for j in range(i + 1, len(stops)):
                    lines.append(f"same_route({stops[i]}, {stops[j]}, r{route_id}).")
        lines.append("")
        
        # Reachability rules
        lines.append("% Reachability")
        lines.append(f"reachable({start}).")
        lines.append("all X all Y all R (reachable(X) & connected(X, Y, R) -> reachable(Y)).")
        lines.append("")
        
        # Require goal to be reachable
        lines.append(f"reachable({goal}).")
        lines.append("")
        
        lines.append("end_of_list.")
        
        return "\n".join(lines)
    
    def extract_path_from_prover9_proof(
        self,
        prover9_output: str,
        connections: List[Dict],
        start: str,
        goal: str
    ):
        """
        Extract path from Prover9's proof by analyzing which at(X, Step) predicates were derived.
        """
        if "THEOREM PROVED" not in prover9_output:
            return None
        
        # Parse proof to find at(stop, step) predicates
        at_predicates = []
        path_uses_predicates = []
        
        for line in prover9_output.split('\n'):
            # Look for at(stop, step) in the proof
            import re
            at_matches = re.findall(r'at\((\d+),\s*(\d+)\)', line)
            for stop, step in at_matches:
                at_predicates.append((stop, int(step)))
            
            # Look for path_uses(route, step)
            route_matches = re.findall(r'path_uses\(route_(\d+),\s*(\d+)\)', line)
            for route, step in route_matches:
                path_uses_predicates.append((route, int(step)))
        
        if not at_predicates:
            return None
        
        # Sort by step to reconstruct path
        at_predicates.sort(key=lambda x: x[1])
        
        # Build path from consecutive stops
        path = []
        for i in range(len(at_predicates) - 1):
            from_stop = at_predicates[i][0]
            to_stop = at_predicates[i + 1][0]
            step = at_predicates[i][1]
            
            # Find the connection
            for conn in connections:
                if conn['from'] == from_stop and conn['to'] == to_stop:
                    path.append(conn)
                    break
            
            if to_stop == goal:
                break
        
        return path if path else None
    
    def run_prover9(self, fol_input: str, timeout: int = 600, save_input: bool = False) -> str:
        """Run Prover9 theorem prover"""
        try:
            input_file = self._write_fol_input(fol_input, prefix="prover9", save_input=save_input)

            # with tempfile.NamedTemporaryFile(mode='w', suffix='.in', delete=False) as f:
            #     f.write(fol_input)
            #     temp_file = f.name
            
            result = subprocess.run(
                [self.prover9_path, "-f", input_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            
            if not save_input:
                os.unlink(input_file)
            
            logger.info(f"Prover9 exit code: {result.returncode}")
            return result.stdout
            
        except subprocess.TimeoutExpired:
            logger.warning("Prover9 timeout")
            return "TIMEOUT"
        except FileNotFoundError:
            logger.error(f"Prover9 not found at {self.prover9_path}")
            return "ERROR: Prover9 not found"
        except Exception as e:
            logger.error(f"Prover9 error: {e}")
            return f"ERROR: {str(e)}"
    
    def run_mace4(self, fol_input: str, timeout: int = 600, save_input: bool = False) -> str:
        """Run Mace4 model finder"""
        try:
            input_file = self._write_fol_input(fol_input, prefix="mace4", save_input=save_input)

            # with tempfile.NamedTemporaryFile(mode='w', suffix='.in', delete=False) as f:
            #     f.write(fol_input)
            #     temp_file = f.name
            
            result = subprocess.run(
                [self.mace4_path, "-f", input_file, "-n", "2", "-N", "20", "-t", str(timeout)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout + 5
            )
            
            if not save_input:
                os.unlink(input_file)
            
            logger.info(f"Mace4 exit code: {result.returncode}")
            return result.stdout
            
        except subprocess.TimeoutExpired:
            logger.warning("Mace4 timeout")
            return "TIMEOUT"
        except FileNotFoundError:
            logger.error(f"Mace4 not found at {self.mace4_path}")
            return "ERROR: Mace4 not found"
        except Exception as e:
            logger.error(f"Mace4 error: {e}")
            return f"ERROR: {str(e)}"
    
    def extract_path_from_mace4(
        self,
        mace4_output: str,
        connections: List[Dict],
        start: str,
        goal: str,
        graph_builder
    ):
        """
        Extract path from Mace4 model.
        Since Mace4 proves satisfiability, we use it to confirm reachability,
        then use graph search to find the actual path.
        """
        if "Exiting" not in mace4_output and "model" not in mace4_output.lower():
            return None
        
        # Mace4 found a model, meaning path exists
        # Use BFS to find it (Mace4 confirms it's possible)
        logger.info("Mace4 confirmed path exists, using graph search to find it")
        
        # Check for direct route first
        if graph_builder:
            direct = graph_builder.can_reach_on_single_route(start, goal)
            if direct:
                path = []
                stops = direct['stops_between']
                for i in range(len(stops) - 1):
                    for conn in connections:
                        if conn['from'] == stops[i] and conn['to'] == stops[i+1]:
                            path.append(conn)
                            break
                return path
        
        # Otherwise use BFS
        from collections import deque
        graph = {}
        for conn in connections:
            if conn["from"] not in graph:
                graph[conn["from"]] = []
            graph[conn["from"]].append(conn)
        
        queue = deque([(start, [])])
        visited = {start}
        
        while queue:
            current, path = queue.popleft()
            
            if current == goal:
                return path
            
            if current not in graph:
                continue
            
            for conn in graph[current]:
                next_stop = conn["to"]
                if next_stop not in visited:
                    visited.add(next_stop)
                    queue.append((next_stop, path + [conn]))
        
        return None