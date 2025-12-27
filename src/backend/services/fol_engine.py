import subprocess
import tempfile
import os
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class FOLEngine:
    def __init__(self, prover9_path: str = "./prover9", mace4_path: str = "./mace4"):
        self.prover9_path = prover9_path
        self.mace4_path = mace4_path
    
    def generate_fol_reachability(
        self, 
        stops: List[str], 
        connections: List[Dict], 
        start: str, 
        goal: str
    ) -> str:
        """
        Generate FOL for reachability problem.
        We want to prove: Can we reach 'goal' from 'start'?
        """
        lines = []
        
        # Prover9 input format
        lines.append("formulas(assumptions).")
        lines.append("")
        
        # Define all stops as constants
        lines.append("% Stop declarations")
        for stop in stops[:100]:  # Limit for performance
            lines.append(f"stop({stop}).")
        lines.append("")
        
        # Define direct connections
        lines.append("% Direct connections between stops")
        for conn in connections:
            lines.append(f"connected({conn['from']}, {conn['to']}, {conn['route']}).")
        lines.append("")
        
        # Reachability rules
        lines.append("% Reachability axioms")
        lines.append("% Base case: start is reachable from start")
        lines.append(f"reachable({start}, {start}).")
        lines.append("")
        
        lines.append("% Inductive case: if X is reachable from S and X connects to Y, then Y is reachable from S")
        lines.append("all X all Y all R (reachable(" + start + ", X) & connected(X, Y, R) -> reachable(" + start + ", Y)).")
        lines.append("")
        
        lines.append("end_of_list.")
        lines.append("")
        
        # Goal to prove
        lines.append("formulas(goals).")
        lines.append(f"reachable({start}, {goal}).")
        lines.append("end_of_list.")
        
        return "\n".join(lines)
    
    def run_prover9(self, fol_input: str, timeout: int = 30) -> str:
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
    
    def run_mace4(self, fol_input: str, timeout: int = 30) -> str:
        """Run Mace4 model finder"""
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.in', delete=False) as f:
                f.write(fol_input)
                temp_file = f.name
            
            result = subprocess.run(
                [self.mace4_path, "-f", temp_file, "-n", "10"],
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