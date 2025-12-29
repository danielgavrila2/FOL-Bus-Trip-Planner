from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import logging

from services.tranzy_service import TranzyService
from services.graph_builder import GraphBuilder
from services.fol_engine import FOLEngine
from services.path_finder import PathFinder
from services.ticketing_service import TicketingService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global service instances
tranzy_service = TranzyService()
graph_builder = GraphBuilder()
fol_engine = FOLEngine()
path_finder = PathFinder()
ticketing_service = TicketingService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Loading transit data from Tranzy API...")
        stops = tranzy_service.fetch_stops()
        routes = tranzy_service.fetch_routes()
        logger.info(f"Loaded {len(stops)} stops and {len(routes)} routes")
        
        logger.info("Loading trips, stop times, and shapes...")
        trips = tranzy_service.fetch_trips()
        stop_times = tranzy_service.fetch_stop_times()
        shapes = tranzy_service.fetch_shapes()
        logger.info(f"Loaded {len(trips)} trips, {len(stop_times)} stop times, and {len(shapes)} shape points")
        
        graph_builder.build_graph(stops, routes, trips, stop_times, shapes)
        logger.info(f"Built graph with {len(graph_builder.connections)} connections")
        
        path_finder.set_graph_builder(graph_builder)
        
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise
    
    yield
    
    logger.info("Shutting down...")

app = FastAPI(
    title="Cluj-Napoca Bus Trip Planner",
    description="FOL-based bus route planning using Prover9/Mace4",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for web/mobile access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class TripRequest(BaseModel):
    start_stop: str  # Stop name or ID
    end_stop: str
    departure_time: Optional[str] = None  
    prefer_fewer_transfers: bool = True

class RouteSegment(BaseModel):
    from_stop: str
    to_stop: str
    route_name: str
    route_id: str
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    
    class Config:
        coerce_numbers_to_str = True

class TripResponse(BaseModel):
    success: bool
    route: List[RouteSegment]
    total_duration_minutes: int
    total_transfers: int
    total_cost: float
    tickets_needed: int
    proof_method: str
    alternative_routes: Optional[List[Any]] = None
    error: Optional[str] = None

@app.get("/")
def read_root():
    return {
        "message": "Cluj-Napoca Bus Trip Planner API",
        "endpoints": {
            "/plan": "POST - Plan a bus trip",
            "/stops": "GET - List all stops",
            "/routes": "GET - List all routes",
            "/health": "GET - Health check"
        }
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "stops_loaded": len(graph_builder.stops),
        "routes_loaded": len(graph_builder.routes),
        "connections": len(graph_builder.connections)
    }

@app.get("/stops")
def list_stops():
    """Get all available bus stops"""
    return {
        "stops": [
            {
                "id": s.get("stop_id", s.get("id")),
                "name": s.get("stop_name", s.get("name", "Unknown")),
                "lat": s.get("stop_lat", s.get("lat")),
                "lon": s.get("stop_lon", s.get("lon"))
            }
            for s in graph_builder.stops.values()
        ]
    }

@app.get("/routes")
def list_routes():
    """Get all available bus routes"""
    return {
        "routes": [
            {
                "id": r.get("route_id", r.get("id")),
                "name": r.get("route_short_name", r.get("short_name", "Unknown")),
                "long_name": r.get("route_long_name", r.get("long_name", ""))
            }
            for r in graph_builder.routes.values()
        ]
    }

@app.get("/debug/connections")
def debug_connections(limit: int = 50):
    """Debug: Show first N connections"""
    return {
        "total_connections": len(graph_builder.connections),
        "sample_connections": graph_builder.connections[:limit],
        "stops_count": len(graph_builder.stops),
        "routes_count": len(graph_builder.routes)
    }

@app.get("/debug/stop/{stop_identifier}")
def debug_stop(stop_identifier: str):
    """Debug: Find stop by name or ID"""
    stop_id = graph_builder.resolve_stop(stop_identifier)
    if not stop_id:
        return {"error": "Stop not found", "searched": stop_identifier}
    
    stop = graph_builder.stops[stop_id]
    
    # Find outgoing connections
    outgoing = [c for c in graph_builder.connections if c["from"] == stop_id]
    incoming = [c for c in graph_builder.connections if c["to"] == stop_id]
    
    # Group by route to see which routes serve this stop
    routes_serving = {}
    for conn in outgoing + incoming:
        route_id = conn["route"]
        route_name = conn["route_name"]
        if route_name not in routes_serving:
            routes_serving[route_name] = {
                "route_id": route_id,
                "route_name": route_name,
                "connections": 0
            }
        routes_serving[route_name]["connections"] += 1
    
    return {
        "stop_id": stop_id,
        "stop_name": stop.get("stop_name", stop.get("name")),
        "coordinates": {
            "lat": stop.get("stop_lat", stop.get("lat")),
            "lon": stop.get("stop_lon", stop.get("lon"))
        },
        "outgoing_connections": len(outgoing),
        "incoming_connections": len(incoming),
        "routes_serving": list(routes_serving.values()),
        "sample_outgoing": outgoing[:10],
        "sample_incoming": incoming[:10]
    }

@app.get("/debug/route/{route_name}")
def debug_route(route_name: str):
    route_id = None
    for rid, route in graph_builder.routes.items():
        if route.get("route_short_name", route.get("short_name", "")) == route_name:
            route_id = rid
            break
    
    if not route_id:
        return {"error": f"Route {route_name} not found"}

    route_connections = [c for c in graph_builder.connections if c["route"] == route_id]
    
    stop_sequence = []
    visited = set()
    
    if route_connections:
        current = route_connections[0]["from"]
        stop_sequence.append(current)
        visited.add(current)
        
        while True:
            next_conn = None
            for conn in route_connections:
                if conn["from"] == current and conn["to"] not in visited:
                    next_conn = conn
                    break
            
            if not next_conn:
                break
            
            current = next_conn["to"]
            stop_sequence.append(current)
            visited.add(current)
    
    stops_details = []
    for stop_id in stop_sequence:
        if stop_id in graph_builder.stops:
            stop = graph_builder.stops[stop_id]
            stops_details.append({
                "stop_id": stop_id,
                "stop_name": stop.get("stop_name", stop.get("name", "Unknown"))
            })
    
    return {
        "route_id": route_id,
        "route_name": route_name,
        "total_stops": len(stops_details),
        "total_connections": len(route_connections),
        "stops": stops_details
    }

@app.get("/debug/direct/{start}/{end}")
def check_direct_route(start: str, end: str):
    start_id = graph_builder.resolve_stop(start)
    end_id = graph_builder.resolve_stop(end)
    
    if not start_id or not end_id:
        return {
            "error": "One or both stops not found",
            "start_resolved": start_id,
            "end_resolved": end_id
        }
    
    direct = graph_builder.can_reach_on_single_route(start_id, end_id)
    
    if direct:
        stop_names = []
        for stop_id in direct['stops_between']:
            if stop_id in graph_builder.stops:
                stop_names.append(graph_builder.stops[stop_id].get("stop_name", stop_id))
        
        return {
            "direct_route_available": True,
            "route_name": direct['route_name'],
            "route_id": direct['route_id'],
            "num_stops": direct['num_stops'],
            "stops": stop_names
        }
    
    return {
        "direct_route_available": False,
        "message": "No single route connects these stops. Transfers required."
    }

@app.post("/plan", response_model=TripResponse)
def plan_trip(request: TripRequest):
    """
    Plan a bus trip using FOL reasoning with Mace4 and Prover9.
    """
    try:
        start_stop_id = graph_builder.resolve_stop(request.start_stop)
        end_stop_id = graph_builder.resolve_stop(request.end_stop)

        if not start_stop_id:
            raise HTTPException(status_code=404, detail=f"Start stop '{request.start_stop}' not found")
        if not end_stop_id:
            raise HTTPException(status_code=404, detail=f"End stop '{request.end_stop}' not found")
        if start_stop_id == end_stop_id:
            raise HTTPException(status_code=400, detail="Start and end stops are the same")

        proof_method = "None"
        path = None

        # Check direct route
        direct_route = graph_builder.can_reach_on_single_route(start_stop_id, end_stop_id)
        if direct_route:
            proof_method = f"Direct Route ({direct_route['route_name']})"
            stops = direct_route['stops_between']
            path = []
            for i in range(len(stops) - 1):
                for conn in graph_builder.connections:
                    if conn["from"] == stops[i] and conn["to"] == stops[i+1] and conn["route"] == direct_route['route_id']:
                        path.append(conn)
                        break

        # Use Mace4 to check existence
        if not path:
            # Get a candidate path first (BFS) to reduce node set for Mace4
            candidate_path = path_finder.find_optimal_path(
                graph_builder.connections,
                start_stop_id,
                end_stop_id,
                prefer_fewer_transfers=request.prefer_fewer_transfers
            )

            if candidate_path:
                # Generate FOL for Mace4 with only relevant nodes and optional direct routes
                fol_mace4 = fol_engine.generate_fol_existence(
                    path=candidate_path,
                    include_direct_routes=True
                )
                mace4_output = fol_engine.run_mace4(fol_mace4, 
                                                    timeout=600, #max(30, len(candidate_path) * 2), 
                                                    save_input=True
                                                    )

                # If Mace4 finds a model, path exists
                if "Exiting" in mace4_output or "model" in mace4_output.lower():
                    proof_method = "Mace4 (Path Exists)"
                else:
                    proof_method = "BFS (FOL failed)"
                
                path = candidate_path
            else:
                proof_method = "BFS (No candidate path)"
                path = candidate_path


        # Verify path with Prover9
        fol_prover9 = fol_engine.generate_fol_verification(path)
        prover9_output = fol_engine.run_prover9(fol_prover9, timeout=60, save_input=True)
        if "THEOREM PROVED" in prover9_output:
            proof_method += " + Prover9 Verified"
        else:
            proof_method += " + Prover9 Verification Failed"


        # Step 4: Build RouteSegments
        route_segments = []
        total_duration = 0
        for segment in path:
            from_stop = graph_builder.stops.get(segment["from"], {})
            to_stop = graph_builder.stops.get(segment["to"], {})
            route = graph_builder.routes.get(segment["route"], {})

            duration = segment.get("duration_minutes", 5)
            total_duration += duration

            route_segments.append(RouteSegment(
                from_stop=from_stop.get("stop_name", from_stop.get("name", "Unknown")),
                to_stop=to_stop.get("stop_name", to_stop.get("name", "Unknown")),
                route_name=str(route.get("route_short_name", route.get("short_name", "Unknown"))),
                route_id=str(segment["route"]),
                duration_minutes=duration
            ))

        # Calculate transfers and tickets
        transfers = path_finder.count_transfers(path)
        departure_time = datetime.now()
        if request.departure_time and request.departure_time != "now":
            try:
                departure_time = datetime.fromisoformat(request.departure_time)
            except ValueError:
                pass

        tickets_needed, total_cost = ticketing_service.calculate_tickets(
            total_duration,
            departure_time
        )

        return TripResponse(
            success=True,
            route=route_segments,
            total_duration_minutes=total_duration,
            total_transfers=transfers,
            total_cost=total_cost,
            tickets_needed=tickets_needed,
            proof_method=proof_method
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error planning trip: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)