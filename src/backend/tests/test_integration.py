import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

class TestAPI:
    def test_health_endpoint(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()
    
    def test_stops_endpoint(self):
        response = client.get("/stops")
        assert response.status_code == 200
        assert "stops" in response.json()
    
    def test_routes_endpoint(self):
        response = client.get("/routes")
        assert response.status_code == 200
        assert "routes" in response.json()
    
    def test_plan_missing_parameters(self):
        response = client.post("/plan", json={})
        assert response.status_code == 422
    
    def test_plan_invalid_stop(self):
        response = client.post("/plan", json={
            "start_stop": "INVALID_STOP_12345",
            "end_stop": "ANOTHER_INVALID"
        })
        assert response.status_code == 404