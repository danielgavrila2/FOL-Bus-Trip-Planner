import subprocess, tempfile

def run_prover9(fol):
    with tempfile.NamedTemporaryFile("w", suffix=".in") as f:
        f.write(fol)
        f.flush()
        r = subprocess.run(["./prover9/prover9", "-f", f.name], stdout=subprocess.PIPE, text=True)
    
    return r.stdout

def run_mace4(fol):
    with tempfile.NamedTemporaryFile("w", suffix=".in") as f:
        f.write(fol)
        f.flush()
        r = subprocess.run(["./prover9/mace4", "-f", f.name], stdout=subprocess.PIPE, text=True)
    
    return r.stdout