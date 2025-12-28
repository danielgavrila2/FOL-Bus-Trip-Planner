# main.py
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
    # Startup: Load and cache transit data
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
        
        # Build connection graph using shapes for better accuracy
        graph_builder.build_graph(stops, routes, trips, stop_times, shapes)
        logger.info(f"Built graph with {len(graph_builder.connections)} connections")
        
        # Connect path finder to graph builder for single-route optimization
        path_finder.set_graph_builder(graph_builder)
        
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise
    
    yield
    
    # Shutdown: cleanup if needed
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
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class TripRequest(BaseModel):
    start_stop: str  # Stop name or ID
    end_stop: str
    departure_time: Optional[str] = None  # ISO format or "now"
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
        # Allow automatic conversion from int to str
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
    """Debug: Show all stops on a route"""
    # Find route by name
    route_id = None
    for rid, route in graph_builder.routes.items():
        if route.get("route_short_name", route.get("short_name", "")) == route_name:
            route_id = rid
            break
    
    if not route_id:
        return {"error": f"Route {route_name} not found"}
    
    # Get all connections for this route
    route_connections = [c for c in graph_builder.connections if c["route"] == route_id]
    
    # Build ordered stop sequence
    stop_sequence = []
    visited = set()
    
    if route_connections:
        # Start from first connection
        current = route_connections[0]["from"]
        stop_sequence.append(current)
        visited.add(current)
        
        while True:
            # Find next connection
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
    
    # Get stop details
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
    """Check if two stops are connected by a single route"""
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
    Plan a bus trip using FOL reasoning with Prover9/Mace4
    """
    try:
        # Validate and resolve stop names/IDs
        start_stop_id = graph_builder.resolve_stop(request.start_stop)
        end_stop_id = graph_builder.resolve_stop(request.end_stop)
        
        logger.info(f"Request: {request.start_stop} -> {request.end_stop}")
        logger.info(f"Resolved to IDs: {start_stop_id} -> {end_stop_id}")
        
        if not start_stop_id:
            raise HTTPException(status_code=404, detail=f"Start stop '{request.start_stop}' not found")
        if not end_stop_id:
            raise HTTPException(status_code=404, detail=f"End stop '{request.end_stop}' not found")
        
        if start_stop_id == end_stop_id:
            raise HTTPException(status_code=400, detail="Start and end stops are the same")
        
        logger.info(f"Planning trip from {start_stop_id} to {end_stop_id}")
        
        # Check if direct route exists first (fastest)
        direct_route = graph_builder.can_reach_on_single_route(start_stop_id, end_stop_id)
        
        path = None
        proof_method = "None"
        
        if direct_route:
            # Direct route found - no need for FOL
            logger.info(f"Direct route found: {direct_route['route_name']}")
            proof_method = f"Direct Route ({direct_route['route_name']}) - No FOL needed"
            
            # Build path
            path = []
            stops = direct_route['stops_between']
            for i in range(len(stops) - 1):
                for conn in graph_builder.connections:
                    if conn['from'] == stops[i] and conn['to'] == stops[i+1] and conn['route'] == direct_route['route_id']:
                        path.append(conn)
                        break
        else:
            # Need transfers - use FOL reasoning
            logger.info("No direct route, using Prover9 for path planning...")
            
            # Get relevant connections (within reasonable distance)
            # relevant_connections = graph_builder.connections[:1000]
            relevant_connections = graph_builder.connections
            
            # Step 1: Try Prover9 with step-based path construction
            fol_input = fol_engine.generate_fol_for_path_planning(
                connections=relevant_connections,
                start=start_stop_id,
                goal=end_stop_id,
                max_steps=150
            )
            
            prover9_output = fol_engine.run_prover9(fol_input, timeout=600, save_input=True)
            
            if "THEOREM PROVED" in prover9_output:
                proof_method = "Prover9 (Theorem Proved)"
                logger.info("✓ Prover9 proved path exists")
                
                # Try to extract path from proof
                path = fol_engine.extract_path_from_prover9_proof(
                    prover9_output,
                    graph_builder.connections,
                    start_stop_id,
                    end_stop_id
                )
                
                if not path:
                    # Extraction failed, but Prover9 confirmed reachability
                    # Use optimized BFS
                    logger.info("Path extraction from proof failed, using BFS (Prover9 confirmed reachability)")
                    proof_method = "Prover9 (Proved) + BFS (Extraction)"
                    path = path_finder.find_optimal_path(
                        graph_builder.connections,
                        start_stop_id,
                        end_stop_id,
                        prefer_fewer_transfers=request.prefer_fewer_transfers
                    )
            else:
                # Prover9 failed, try Mace4
                logger.info("Prover9 failed/timeout, trying Mace4...")
                
                fol_mace4 = fol_engine.generate_fol_with_mace4(
                    connections=relevant_connections,
                    start=start_stop_id,
                    goal=end_stop_id,
                    route_patterns=graph_builder.route_patterns
                )
                
                mace4_output = fol_engine.run_mace4(fol_mace4, timeout=30, save_input=True)
                
                if "Exiting with" in mace4_output or "model" in mace4_output.lower():
                    proof_method = "Mace4 (Model Found)"
                    logger.info("✓ Mace4 found satisfying model")
                    
                    # Extract path using Mace4 confirmation
                    path = fol_engine.extract_path_from_mace4(
                        mace4_output,
                        graph_builder.connections,
                        start_stop_id,
                        end_stop_id,
                        graph_builder
                    )
                else:
                    # Both FOL methods failed, use BFS as last resort
                    logger.warning("Both Prover9 and Mace4 failed, using BFS fallback")
                    proof_method = "BFS (FOL methods failed)"
                    path = path_finder.find_optimal_path(
                        graph_builder.connections,
                        start_stop_id,
                        end_stop_id,
                        prefer_fewer_transfers=request.prefer_fewer_transfers
                    )
        
        if not path:
            return TripResponse(
                success=False,
                route=[],
                total_duration_minutes=0,
                total_transfers=0,
                total_cost=0.0,
                tickets_needed=0,
                proof_method=proof_method,
                error="Route exists but path finding failed"
            )
        
        # Step 3: Build route segments
        route_segments = []
        total_duration = 0
        
        for i, segment in enumerate(path):
            from_stop = graph_builder.stops.get(segment["from"], {})
            to_stop = graph_builder.stops.get(segment["to"], {})
            route = graph_builder.routes.get(segment["route"], {})
            
            # Estimate travel time (would use real schedules in production)
            duration = segment.get("duration_minutes", 5)
            
            route_segments.append(RouteSegment(
                from_stop=from_stop.get("stop_name", from_stop.get("name", "Unknown")),
                to_stop=to_stop.get("stop_name", to_stop.get("name", "Unknown")),
                route_name=str(route.get("route_short_name", route.get("short_name", "Unknown"))),
                route_id=str(segment["route"]),  # Explicitly convert to string
                duration_minutes=duration
            ))
            total_duration += duration
        
        # Step 4: Calculate transfers
        transfers = path_finder.count_transfers(path)
        
        # Step 5: Calculate ticket cost
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