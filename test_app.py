"""
Test script to verify the Gala Seating System
Run this after starting the application to test basic functionality
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_home_page():
    """Test that home page loads"""
    print("Testing home page...")
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200
    print("✓ Home page loads successfully")

def test_ticket_validation():
    """Test ticket validation"""
    print("\nTesting ticket validation...")
    
    # Test valid tickets
    valid_data = {
        "tickets": [
            {"full_name": "Test Guest 1", "ticket_number": "GALA-0001"},
            {"full_name": "Test Guest 2", "ticket_number": "GALA-0002"}
        ]
    }
    
    response = requests.post(
        f"{BASE_URL}/api/validate-tickets",
        json=valid_data,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    print("✓ Valid tickets accepted")
    
    # Test invalid ticket
    invalid_data = {
        "tickets": [
            {"full_name": "Test Guest", "ticket_number": "INVALID-999"}
        ]
    }
    
    response = requests.post(
        f"{BASE_URL}/api/validate-tickets",
        json=invalid_data,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 400
    print("✓ Invalid tickets rejected")

def test_get_tables():
    """Test getting table status"""
    print("\nTesting table status retrieval...")
    response = requests.get(f"{BASE_URL}/api/get-tables")
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert len(data["tables"]) == 25  # Should have 25 tables
    
    # Check first table structure
    table = data["tables"][0]
    assert "number" in table
    assert "capacity" in table
    assert "occupied" in table
    assert "occupants" in table
    
    print(f"✓ Retrieved {len(data['tables'])} tables")
    print(f"  Table 1: {table['occupied']}/{table['capacity']} seats occupied")

def test_reset_demo():
    """Test demo reset functionality"""
    print("\nTesting demo reset...")
    response = requests.get(f"{BASE_URL}/admin/reset-demo")
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    print("✓ Demo reset successful")

def run_all_tests():
    """Run all tests"""
    print("=" * 50)
    print("GALA SEATING SYSTEM - TEST SUITE")
    print("=" * 50)
    
    try:
        test_home_page()
        test_get_tables()
        test_reset_demo()
        test_ticket_validation()
        
        print("\n" + "=" * 50)
        print("ALL TESTS PASSED! ✓")
        print("=" * 50)
        print("\nApplication is working correctly!")
        print(f"Access it at: {BASE_URL}")
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
    except requests.exceptions.ConnectionError:
        print(f"\n✗ Could not connect to {BASE_URL}")
        print("Make sure the application is running!")
        print("Run: python app.py")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")

if __name__ == "__main__":
    run_all_tests()
