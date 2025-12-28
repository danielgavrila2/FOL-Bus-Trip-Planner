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
        
        logger.info("Loading trips and stop times...")
        trips = tranzy_service.fetch_trips()
        stop_times = tranzy_service.fetch_stop_times()
        logger.info(f"Loaded {len(trips)} trips and {len(stop_times)} stop times")
        
        # Build connection graph
        graph_builder.build_graph(stops, routes, trips, stop_times)
        logger.info(f"Built graph with {len(graph_builder.connections)} connections")
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
    
    return {
        "stop_id": stop_id,
        "stop_data": stop,
        "outgoing_connections": len(outgoing),
        "incoming_connections": len(incoming),
        "sample_outgoing": outgoing[:10],
        "sample_incoming": incoming[:10]
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
        
        # Get relevant connections (limit for performance)
        relevant_connections = graph_builder.connections[:1000]
        
        # Step 1: Use Prover9 for reachability with path construction
        fol_input = fol_engine.generate_fol_reachability(
            stops=list(graph_builder.stops.keys())[:200],
            connections=relevant_connections,
            start=start_stop_id,
            goal=end_stop_id
        )
        
        logger.info("Running Prover9...")
        prover9_output = fol_engine.run_prover9(fol_input, timeout=30)
        
        path = None
        proof_method = "None"
        
        if "THEOREM PROVED" in prover9_output:
            proof_method = "Prover9 (Theorem Proved)"
            logger.info("Prover9 proved reachability")
            
            # Try to extract path from proof
            path = fol_engine.extract_path_from_proof(prover9_output, graph_builder.connections)
            
            if not path:
                # Fallback: use BFS since we know path exists
                logger.info("Extracting path with BFS (Prover9 confirmed reachability)")
                path = path_finder.find_optimal_path(
                    graph_builder.connections,
                    start_stop_id,
                    end_stop_id,
                    prefer_fewer_transfers=request.prefer_fewer_transfers
                )
        else:
            # Try Mace4 to find a model
            logger.info("Prover9 couldn't prove, trying Mace4...")
            mace4_output = fol_engine.run_mace4(fol_input, timeout=30)
            
            if "Exiting with" in mace4_output or "model" in mace4_output.lower():
                proof_method = "Mace4 (Model Found)"
                logger.info("Mace4 found a model")
                
                # Extract path from Mace4 model
                path = fol_engine.extract_path_from_mace4(
                    mace4_output,
                    start_stop_id,
                    end_stop_id,
                    graph_builder.connections
                )
            else:
                # Last resort: try BFS directly
                logger.info("FOL methods failed, using BFS as fallback")
                proof_method = "BFS (Fallback)"
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