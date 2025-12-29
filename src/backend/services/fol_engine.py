import subprocess
import tempfile
import os
from typing import List, Dict
import logging
from datetime import datetime
import hashlib
import re

logger = logging.getLogger(__name__)


class FOLEngine:
    """
    The core of our application. 
    Here we perform the formalization, create and run provers to prove the goal.
    """

    def __init__(
        self,
        prover9_path: str = "src/backend/prover9/Prover9/LADR-2009-11A/bin/prover9", # If not working, paste your full path to Prover9/Mace4
        mace4_path: str = "src/backend/prover9/Prover9/LADR-2009-11A/bin/mace4",
    ):
        self.prover9_path = prover9_path
        self.mace4_path = mace4_path

# ----------------------------------------------------------------------------------------- #

    # File helpers
    def _write_fol_input(self, fol_input: str, prefix: str, save_input: bool = True) -> str:
        if fol_input is None:
            raise ValueError("FOL input is None")

        if save_input:
            os.makedirs("src/backend/fol_inputs", exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
            content_hash = hashlib.md5(fol_input.encode()).hexdigest()[:8]
            filename = f"{prefix}_{timestamp}_{content_hash}.in"
            path = os.path.join("src/backend/fol_inputs", filename)
            with open(path, "w") as f:
                f.write(fol_input)
            logger.info(f"Saved FOL input to {path}")
            return path

        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".in", delete=True)
        tmp.write(fol_input)
        tmp.close()
        return tmp.name

    def _save_fol_output(self, output: str, prefix: str, fol_input: str):
        if output is None:
            output = ""

        os.makedirs("src/backend/fol_outputs", exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
        content_hash = hashlib.md5(fol_input.encode()).hexdigest()[:8]
        filename = f"{prefix}_{timestamp}_{content_hash}.out"
        path = os.path.join("src/backend/fol_outputs", filename)

        with open(path, "w") as f:
            f.write(output)

        logger.info(f"Saved FOL output to {path}")

        return filename, path

# ----------------------------------------------------------------------------------------- #


    # Node remapping (used for reducing complexity on Prover9/Mace4 files)
    def _remap_nodes(self, fol_input: str):
        pattern = re.compile(r"\b\d+\b")
        numbers = sorted({int(x) for x in pattern.findall(fol_input)})
        mapping = {old: new for new, old in enumerate(numbers)}

        def repl(match):
            return str(mapping[int(match.group(0))])

        remapped = pattern.sub(repl, fol_input)
        return remapped, mapping



    # Mace4: existence of the route (check if we can find a route, including changes to reach the goal)
    def generate_fol_existence(self, path: List[Dict], include_direct_routes: bool = True, save_input : bool = False) -> str:
        if not path:
            raise ValueError("Path is empty")

        lines = ["formulas(assumptions)."]
        reachable_nodes = set()

        for seg in path:
            lines.append(f"connected({seg['from']},{seg['to']},r{seg['route']}).")
            reachable_nodes.add(seg["from"])
            reachable_nodes.add(seg["to"])

        if include_direct_routes:
            for i in range(len(path) - 1):
                a = path[i]["from"]
                b = path[i + 1]["from"]
                c = path[i + 1]["to"]
                lines.append(f"connected({a},{b},r_direct).")
                lines.append(f"connected({a},{c},r_direct).")

        for n in reachable_nodes:
            lines.append(f"reachable({n}).")

        goal = path[-1]["to"]
        lines.append(f"reachable({goal}).")
        lines.append("end_of_list.")

        fol_input = "\n".join(lines)

        if save_input:
            self._write_fol_input(fol_input, "mace4", True)

        fol_input_remapped, mapping = self._remap_nodes(fol_input)
        logger.info(
            f"Remapped {len(mapping)} nodes. Largest node: {max(mapping.values())}"
        )

        return fol_input_remapped


    # Prover9: verification of the route (proof)
    def generate_fol_verification(self, path: List[Dict]) -> str:
        if not path:
            raise ValueError("Path is empty")
        
        lines = ["set(production)."] 
        lines.append("formulas(assumptions).")

        # Essential update. Very important, due to Prover9's technical limitations.
        lines.append("assign(max_weight, 30).")
        lines.append("assign(max_proofs, 1).")  
        lines.append("assign(max_seconds, 30).")      
        lines.append("assign(sos_limit, 500).")   
        
        # Add connections
        for seg in path:
            lines.append(f"connected({seg['from']},{seg['to']},r{seg['route']}).")
            # lines.append(f"on_route({seg['from']},r{seg['route']}).")
            # lines.append(f"on_route({seg['to']},r{seg['route']}).")
        
        # Forward chain
        for i in range(len(path)):
            lines.append(f"succ({i},{i+1}).")
        
        # Start point
        lines.append(f"step(0,{path[0]['from']}).")
        
        # Uses (route per step)
        for i, seg in enumerate(path):
            lines.append(f"uses({i+1},r{seg['route']}).")
        
        # Main axiom
        lines.append(
            "all N all M all X all Y all R "
            "(step(N,X) & succ(N,M) & uses(M,R) & connected(X,Y,R) -> step(M,Y))."
        )
        lines.append("end_of_list.")
        
        # Goal
        lines.append("formulas(goals).")
        lines.append(f"step({len(path)},{path[-1]['to']}).")
        lines.append("end_of_list.")
        
        fol_input = "\n".join(lines)
        
        # Apply remapping (reduce the number of variables in Prover9 .in file)
        fol_input_remapped, mapping = self._remap_nodes(fol_input)
        
        logger.info(
            f"Prover9 remapped {len(mapping)} nodes. Largest node: {max(mapping.values())}"
        )
        
        return fol_input_remapped

# ----------------------------------------------------------------------------------------- #

    def run_prover9(self, fol_input: str, timeout: int = 600, save_input: bool = False) -> str:
        try:
            input_file = self._write_fol_input(fol_input, "prover9", save_input=save_input)
            
            result = subprocess.run(
                [self.prover9_path, "-f", input_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )

            filename = ""
            filepath = ""
            if save_input:
                filename, filepath = self._save_fol_output(result.stdout, "prover9", fol_input)

            os.unlink(input_file)
            logger.info(f"Prover9 exit code: {result.returncode}")
            return result.stdout, filepath

        except subprocess.TimeoutExpired:
            return "TIMEOUT"
        except Exception as e:
            logger.error(f"Prover9 error: {e}")
            return f"ERROR: {e}"

    # Run Mace4
    def run_mace4(self, fol_input: str, timeout: int = 600, save_input: bool = False) -> str:
        try:
            input_file = self._write_fol_input(fol_input, "mace4", save_input=save_input)
            result = subprocess.run(
                [self.mace4_path, "-f", input_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout + 5,
            )

            output = result.stdout or ""

            filename = ""
            filepath = ""
            if save_input:
                filename, filepath = self._save_fol_output(output, "mace4", fol_input)

            os.unlink(input_file)
            logger.info(f"Mace4 exit code: {result.returncode}")
            return output, filepath

        except subprocess.TimeoutExpired:
            return "TIMEOUT"
        except Exception as e:
            logger.error(f"Mace4 error: {e}")
            return f"ERROR: {e}"
