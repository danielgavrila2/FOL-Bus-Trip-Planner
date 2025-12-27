import pytest
from services.graph_builder import GraphBuilder
from services.path_finder import PathFinder
from services.ticketing_service import TicketingService
from services.fol_engine import FOLEngine
from datetime import datetime

class TestGraphBuilder:
    def test_build_graph(self):
        builder = GraphBuilder()
        
        stops = [
            {"id": "1", "name": "Stop A"},
            {"id": "2", "name": "Stop B"},
            {"id": "3", "name": "Stop C"}
        ]
        
        routes = [
            {
                "id": "R1",
                "short_name": "35",
                "stops": [
                    {"id": "1"},
                    {"id": "2"},
                    {"id": "3"}
                ]
            }
        ]
        
        builder.build_graph(stops, routes)
        
        assert len(builder.stops) == 3
        assert len(builder.routes) == 1
        assert len(builder.connections) == 2
    
    def test_resolve_stop_by_id(self):
        builder = GraphBuilder()
        builder.stops = {"1": {"id": "1", "name": "Stop A"}}
        builder.stop_name_to_id = {"stop a": "1"}
        
        assert builder.resolve_stop("1") == "1"
    
    def test_resolve_stop_by_name(self):
        builder = GraphBuilder()
        builder.stops = {"1": {"id": "1", "name": "Stop A"}}
        builder.stop_name_to_id = {"stop a": "1"}
        
        assert builder.resolve_stop("Stop A") == "1"
        assert builder.resolve_stop("stop a") == "1"


class TestPathFinder:
    def test_find_simple_path(self):
        finder = PathFinder()
        
        connections = [
            {"from": "1", "to": "2", "route": "R1"},
            {"from": "2", "to": "3", "route": "R1"}
        ]
        
        path = finder.find_optimal_path(connections, "1", "3")
        
        assert path is not None
        assert len(path) == 2
        assert path[0]["from"] == "1"
        assert path[1]["to"] == "3"
    
    def test_no_path(self):
        finder = PathFinder()
        
        connections = [
            {"from": "1", "to": "2", "route": "R1"}
        ]
        
        path = finder.find_optimal_path(connections, "1", "999")
        assert path is None
    
    def test_count_transfers(self):
        finder = PathFinder()
        
        path = [
            {"from": "1", "to": "2", "route": "R1"},
            {"from": "2", "to": "3", "route": "R1"},
            {"from": "3", "to": "4", "route": "R2"}
        ]
        
        transfers = finder.count_transfers(path)
        assert transfers == 1


class TestTicketingService:
    def test_single_ticket(self):
        service = TicketingService()
        tickets, cost = service.calculate_tickets(30, datetime.now())
        
        assert tickets == 1
        assert cost == 3.5
    
    def test_two_tickets(self):
        service = TicketingService()
        tickets, cost = service.calculate_tickets(60, datetime.now())
        
        assert tickets == 2
        assert cost == 7.0
    
    def test_edge_case_45_minutes(self):
        service = TicketingService()
        tickets, cost = service.calculate_tickets(45, datetime.now())
        
        assert tickets == 1
        assert cost == 3.5
    
    def test_edge_case_46_minutes(self):
        service = TicketingService()
        tickets, cost = service.calculate_tickets(46, datetime.now())
        
        assert tickets == 2
        assert cost == 7.0


class TestFOLEngine:
    def test_generate_fol(self):
        engine = FOLEngine()
        
        stops = ["1", "2", "3"]
        connections = [
            {"from": "1", "to": "2", "route": "R1"},
            {"from": "2", "to": "3", "route": "R1"}
        ]
        
        fol = engine.generate_fol_reachability(stops, connections, "1", "3")
        
        assert "reachable(1, 1)" in fol
        assert "connected(1, 2, R1)" in fol
        assert "reachable(1, 3)" in fol
        assert "formulas(goals)" in fol

