
from __future__ import annotations

import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.incidents import enable, disable, status, STATE


def test_incident_functions():
    print("Testing incident management functions...")
    
    # Check initial status
    initial_status = status()
    print("Initial status:", initial_status)
    assert initial_status == {
        "rag_slow": False,
        "tool_fail": False, 
        "cost_spike": False
    }
    print("OK - Initial status is correct")
    
    # Test enabling incidents one by one
    for incident in ["rag_slow", "tool_fail", "cost_spike"]:
        enable(incident)
        print(f"Enabled {incident}, current status:", status())
        assert status()[incident] is True
        disable(incident)
        print(f"Disabled {incident}, current status:", status())
        assert status()[incident] is False
    
    print("OK - Enable/disable functions work correctly")
    
    # Check incidents.json
    with open("data/incidents.json", "r", encoding="utf-8") as f:
        incidents_data = json.load(f)
        assert "rag_slow" in incidents_data
        assert "tool_fail" in incidents_data
        assert "cost_spike" in incidents_data
        print("OK - All incidents present in incidents.json with metadata")
        for key, value in incidents_data.items():
            assert "name" in value
            assert "description" in value
            assert "symptom" in value
            assert "root_cause" in value
            assert "expected_effect" in value
            print(f"  OK - {key} has all required metadata fields")
    
    print("\nAll tests passed!")


if __name__ == "__main__":
    test_incident_functions()
