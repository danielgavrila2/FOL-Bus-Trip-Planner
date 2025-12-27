from fastapi import FastAPI
from tranzy_api import fetch_stops, fetch_routes, fetch_trips
from fol_translator import generate_fol
from prover9_runner import run_prover9
from ticketing_engine import apply_ticket_constraints
from datetime import datetime

app = FastAPI()

@app.post("/post")
def plan(start: str, goal: str):
    stops = fetch_stops()[:15]
    lines = fetch_routes()[:5]

    connections = []
    for line in lines:
        ids = [st["id"] for st in line["stops"]]
        for i in range(len(ids) - 1):
            connections.append({
                "from": ids[i],
                "to": ids[i+1],
                "line": line["id"]
            })
    
    fol = generate_fol([x["id"] for x in stops], connections, start, goal)
    proof = run_prover9(fol)

    plan = [c for c in connections if c["from"] in proof]
    timed, cost = apply_ticket_constraints(plan, datetime.now())

    return {
        "route": timed,
        "total_cost": cost,
        "proof": proof
    }