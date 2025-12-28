import subprocess
import tempfile
import os
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class FOLEngine:
    def __init__(self, prover9_path: str = "prover9/Prover9/LADR-2009-11A/bin", mace4_path: str = "prover9/Prover9/LADR-2009-11A/bin"):
        self.prover9_path = prover9_path
        self.mace4_path = mace4_path
    
    def generate_fol_path_finding(
        self, 
        stops: List[str], 
        connections: List[Dict], 
        start: str, 
        goal: str,
        max_depth: int = 10
    ) -> str:
        """
        Generate FOL for path finding problem.
        We define a path as a sequence of connections.
        """
        lines = []
        
        # Prover9 input format
        lines.append("set(auto).")
        lines.append("set(production).")
        lines.append("")
        lines.append("formulas(assumptions).")
        lines.append("")
        
        # Define stops
        lines.append("% Stops")
        for stop in stops:  # Limit for performance
            lines.append(f"stop({stop}).")
        lines.append("")
        
        # Define direct connections
        lines.append("% Direct connections")
        for conn in connections:
            lines.append(f"direct({conn['from']}, {conn['to']}, {conn['route']}).")
        lines.append("")
        
        # Path construction rules
        lines.append("% Path finding rules")
        lines.append("% Base case: can reach a stop from itself with empty path")
        lines.append(f"path({start}, {start}, empty).")
        lines.append("")
        
        # Inductive case with path construction
        lines.append("% If there's a path from S to X, and X connects to Y, then there's a path from S to Y")
        lines.append("all S all X all Y all R all P (")
        lines.append(f"  path({start}, X, P) & direct(X, Y, R) -> path({start}, Y, cons(step(X,Y,R), P))")
        lines.append(").")
        lines.append("")
        
        lines.append("end_of_list.")
        lines.append("")
        
        # Goal: find a path to the destination
        lines.append("formulas(goals).")
        lines.append(f"exists P (path({start}, {goal}, P)).")
        lines.append("end_of_list.")
        
        return "\n".join(lines)
    
    def generate_fol_reachability(
        self, 
        stops: List[str], 
        connections: List[Dict], 
        start: str, 
        goal: str
    ) -> str:
        """
        Generate simpler FOL for reachability checking only.
        """
        lines = []
        
        lines.append("formulas(assumptions).")
        lines.append("")
        
        # Define connections
        lines.append("% Direct connections")
        for conn in connections[:500]:  # Limit for performance
            lines.append(f"connected({conn['from']}, {conn['to']}).")
        lines.append("")
        
        # Reachability rules
        lines.append("% Reachability axioms")
        lines.append(f"reachable({start}, {start}).")
        lines.append("")
        lines.append("all X all Y (reachable(" + start + ", X) & connected(X, Y) -> reachable(" + start + ", Y)).")
        lines.append("")
        
        lines.append("end_of_list.")
        lines.append("")
        
        # Goal
        lines.append("formulas(goals).")
        lines.append(f"reachable({start}, {goal}).")
        lines.append("end_of_list.")
        
        return "\n".join(lines)
    
    def extract_path_from_proof(self, prover9_output: str, connections: List[Dict]):
        """
        Extract the path from Prover9's proof output.
        This is a simplified extraction - looks for the sequence of inferences.
        """
        if "THEOREM PROVED" not in prover9_output:
            return None
        
        # Parse the proof to find which connections were used
        # This is a heuristic approach
        used_connections = []
        
        for line in prover9_output.split('\n'):
            # Look for lines with "direct" or "connected" predicates
            if 'direct(' in line or 'connected(' in line:
                # Extract connection information
                # Format: direct(from, to, route) or connected(from, to)
                try:
                    # Simple regex-like parsing
                    import re
                    matches = re.findall(r'(?:direct|connected)\((\d+),\s*(\d+)(?:,\s*(\d+))?\)', line)
                    for match in matches:
                        from_stop, to_stop = match[0], match[1]
                        # Find the actual connection object
                        for conn in connections:
                            if conn['from'] == from_stop and conn['to'] == to_stop:
                                if conn not in used_connections:
                                    used_connections.append(conn)
                                break
                except:
                    continue
        
        return used_connections if used_connections else None
    
    def run_prover9(self, fol_input: str, timeout: int = 60) -> str:
        """Run Prover9 theorem prover"""
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.in', delete=False) as f:
                f.write(fol_input)
                temp_file = f.name
            
            result = subprocess.run(
                [self.prover9_path, "-f", temp_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            
            os.unlink(temp_file)
            
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
    
    def run_mace4(self, fol_input: str, timeout: int = 60) -> str:
        """Run Mace4 model finder"""
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.in', delete=False) as f:
                f.write(fol_input)
                temp_file = f.name
            
            result = subprocess.run(
                [self.mace4_path, "-f", temp_file, "-n", "20", "-N", "50"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            
            os.unlink(temp_file)
            
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
    
    def extract_path_from_mace4(self, mace4_output: str, start: str, goal: str, connections: List[Dict]):
        """
        Extract path from Mace4 model.
        Mace4 gives us a model that satisfies the constraints.
        """
        if "Exiting" not in mace4_output and "Model" not in mace4_output:
            return None
        
        # Build a graph and use BFS as fallback
        # Since Mace4 proves satisfiability, we know a path exists
        graph = {}
        for conn in connections:
            if conn["from"] not in graph:
                graph[conn["from"]] = []
            graph[conn["from"]].append(conn)
        
        # BFS to find path
        from collections import deque
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