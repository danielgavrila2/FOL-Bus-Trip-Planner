"""
Example usage of the Bus Trip Planner API
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def example_plan_trip():
    """Example: Plan a trip from Observatorului N to Piata Garii"""
    
    response = requests.post(
        f"{BASE_URL}/plan",
        json={
            "start_stop": "Observatorului N",
            "end_stop": "Piata Garii",
            "prefer_fewer_transfers": True
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        
        if result["success"]:
            print("✅ Trip planned successfully!")
            print(f"\n📍 Route: {result['route'][0]['from_stop']} → {result['route'][-1]['to_stop']}")
            print(f"⏱️  Duration: {result['total_duration_minutes']} minutes")
            print(f"🔄 Transfers: {result['total_transfers']}")
            print(f"🎫 Tickets needed: {result['tickets_needed']}")
            print(f"💰 Total cost: {result['total_cost']} RON")
            print(f"🧠 Proof method: {result['proof_method']}")
            
            print("\n🚌 Detailed Route:")
            for i, segment in enumerate(result["route"], 1):
                print(f"  {i}. Bus {segment['route_name']}: {segment['from_stop']} → {segment['to_stop']}")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
    else:
        print(f"❌ HTTP Error: {response.status_code}")
        print(response.text)


def example_list_stops():
    """Example: List all available stops"""
    
    response = requests.get(f"{BASE_URL}/stops")
    
    if response.status_code == 200:
        stops = response.json()["stops"]
        print(f"📍 Total stops: {len(stops)}")
        print("\nFirst 10 stops:")
        for stop in stops[:10]:
            print(f"  - {stop['name']} (ID: {stop['id']})")


def example_search_by_fuzzy_name():
    """Example: Search for stops with fuzzy matching"""
    
    search_term = "observator"  # Partial match
    
    response = requests.get(f"{BASE_URL}/stops")
    
    if response.status_code == 200:
        stops = response.json()["stops"]
        matching = [s for s in stops if search_term.lower() in s["name"].lower()]
        
        print(f"🔍 Stops matching '{search_term}':")
        for stop in matching:
            print(f"  - {stop['name']}")


def example_multiple_transfers():
    """Example: Plan a trip that requires multiple transfers"""
    
    # This would require a trip across the city
    response = requests.post(
        f"{BASE_URL}/plan",
        json={
            "start_stop": "Strada Campului",
            "end_stop": "Fabricii",
            "prefer_fewer_transfers": False  # Show all options
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        
        if result["success"]:
            print(f"✅ Complex route with {result['total_transfers']} transfer(s)")
            
            # Show transfer points
            current_route = None
            transfers = []
            
            for segment in result["route"]:
                if current_route and segment["route_id"] != current_route:
                    transfers.append(segment["from_stop"])
                current_route = segment["route_id"]
            
            if transfers:
                print("\n🔄 Transfer points:")
                for transfer in transfers:
                    print(f"  - {transfer}")


def example_cost_comparison():
    """Example: Compare costs for different routes"""
    
    routes = [
        ("Observatorului N", "Piata Garii"),
        ("Strada Campului", "Strada Moților"),
        ("Fabricii", "Piata Unirii")
    ]
    
    print("💰 Cost Comparison:\n")
    
    for start, end in routes:
        response = requests.post(
            f"{BASE_URL}/plan",
            json={"start_stop": start, "end_stop": end}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                print(f"{start[:20]} → {end[:20]}")
                print(f"  Cost: {result['total_cost']} RON ({result['tickets_needed']} ticket(s))")
                print(f"  Duration: {result['total_duration_minutes']} min")
                print()


if __name__ == "__main__":
    print("=" * 60)
    print("Cluj-Napoca Bus Trip Planner - Examples")
    print("=" * 60)
    
    print("\n1. Planning a basic trip:")
    print("-" * 60)
    example_plan_trip()
    
    print("\n\n2. Listing available stops:")
    print("-" * 60)
    example_list_stops()
    
    print("\n\n3. Fuzzy stop search:")
    print("-" * 60)
    example_search_by_fuzzy_name()
    
    print("\n\n4. Complex route with transfers:")
    print("-" * 60)
    example_multiple_transfers()
    
    print("\n\n5. Cost comparison:")
    print("-" * 60)
    example_cost_comparison()

