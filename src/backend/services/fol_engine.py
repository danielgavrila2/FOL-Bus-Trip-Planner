# fol_engine.py
import subprocess
import tempfile
import os
from typing import List, Dict, Optional
import logging
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class FOLEngine:
    def __init__(self, prover9_path: str = "src/backend/prover9/Prover9/LADR-2009-11A/bin/prover9", mace4_path: str = "src/backend/prover9/Prover9/LADR-2009-11A/bin/mace4"):
        self.prover9_path = prover9_path
        self.mace4_path = mace4_path

    def _write_fol_input(self, fol_input: str, prefix: str, save_input: bool) -> str:
        """
        Write FOL input to a temp file or persistent file for debugging.
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

        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".in", delete=False)
        tmp.write(fol_input)
        tmp.close()
        return tmp.name

    def generate_fol_existence(self, path: List[Dict], include_direct_routes: bool = True) -> str:
        """
        Generate FOL for Mace4 to check existence of a path from start to goal.
        Only includes nodes and routes in the path to reduce model size.
        If include_direct_routes=True, also allows direct connections between consecutive nodes.
        """
        if not path:
            raise ValueError("Path is empty")

        lines = []
        lines.append("set(production).")
        lines.append("formulas(assumptions).")

        used_routes = set()
        used_nodes = set()
        for seg in path:
            used_nodes.add(seg['from'])
            used_nodes.add(seg['to'])
            used_routes.add(seg['route'])
            # Include the connection
            lines.append(f"connected({seg['from']}, {seg['to']}, r{seg['route']}).")

        # Include direct route between consecutive steps if desired
        if include_direct_routes:
            for i in range(len(path)-1):
                lines.append(f"connected({path[i]['from']}, {path[i+1]['from']}, r_direct).")
                lines.append(f"connected({path[i]['from']}, {path[i+1]['to']}, r_direct).")

        # Reachability
        start_node = path[0]['from']
        goal_node = path[-1]['to']
        lines.append(f"reachable({start_node}).")
        lines.append("all X all Y all R (reachable(X) & connected(X,Y,R) -> reachable(Y)).")
        lines.append("end_of_list.")

        # Goal
        lines.append("formulas(goals).")
        lines.append(f"reachable({goal_node}).")
        lines.append("end_of_list.")

        return "\n".join(lines)


    # -----------------------------
    # PROVER9: Path verification
    # -----------------------------
    def generate_fol_verification(self, path: List[Dict]) -> str:
        """
        Generate FOL to verify a given path is valid.
        """
        if not path:
            raise ValueError("Path is empty")

        lines = []
        lines.append("formulas(assumptions).")

        # Declare all connections used in path
        for seg in path:
            lines.append(f"connected({seg['from']}, {seg['to']}, r{seg['route']}).")
            lines.append(f"on_route({seg['from']}, r{seg['route']}).")
            lines.append(f"on_route({seg['to']}, r{seg['route']}).")

        # Encode path steps
        for i, seg in enumerate(path):
            lines.append(f"step({i}, {seg['from']}).")
            lines.append(f"uses({i+1}, r{seg['route']}).")
        # Final step
        lines.append(f"step({len(path)}, {path[-1]['to']}).")

        # Logical constraints: consecutive steps must be connected
        lines.append(
            "all N all X all Y all R "
            "(step(N,X) & step(N+1,Y) & uses(N+1,R) -> connected(X,Y,R))."
        )
        lines.append("end_of_list.")

        # Goal
        lines.append("formulas(goals).")
        lines.append(f"step({len(path)}, {path[-1]['to']}).")
        lines.append("end_of_list.")

        return "\n".join(lines)

    # -----------------------------
    # Run Prover9
    # -----------------------------
    def run_prover9(self, fol_input: str, timeout: int = 600, save_input: bool = False) -> str:
        try:
            input_file = self._write_fol_input(fol_input, prefix="prover9", save_input=save_input)
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

    # -----------------------------
    # Run Mace4
    # -----------------------------
    def run_mace4(self, fol_input: str, timeout: int = 600, save_input: bool = False) -> str:
        try:
            input_file = self._write_fol_input(fol_input, prefix="mace4", save_input=save_input)
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
