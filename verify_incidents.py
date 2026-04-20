
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app import incidents
from app.mock_rag import retrieve
from app.mock_llm import FakeLLM

print('Testing all incidents...')
print()

# Test rag_slow
print('1. Testing rag_slow:')
incidents.enable('rag_slow')
print('   rag_slow enabled:', incidents.STATE['rag_slow'])
assert incidents.STATE['rag_slow'] is True, 'rag_slow should be True'
incidents.disable('rag_slow')
print('   OK')
print()

# Test tool_fail
print('2. Testing tool_fail:')
incidents.enable('tool_fail')
print('   tool_fail enabled:', incidents.STATE['tool_fail'])
assert incidents.STATE['tool_fail'] is True, 'tool_fail should be True'
try:
    retrieve('test')
    print('   ERROR: Should have raised exception!')
    sys.exit(1)
except Exception as e:
    print(f'   OK - Raised expected exception: {type(e).__name__} - {e}')
incidents.disable('tool_fail')
print()

# Test cost_spike
print('3. Testing cost_spike:')
llm = FakeLLM()
incidents.enable('cost_spike')
print('   cost_spike enabled:', incidents.STATE['cost_spike'])
assert incidents.STATE['cost_spike'] is True, 'cost_spike should be True'
response_with_spike = llm.generate('Feature=qa\nDocs=[]\nQuestion=test')
print(f'   Output tokens with spike: {response_with_spike.usage.output_tokens}')
incidents.disable('cost_spike')
response_normal = llm.generate('Feature=qa\nDocs=[]\nQuestion=test')
print(f'   Output tokens normal: {response_normal.usage.output_tokens}')
assert response_with_spike.usage.output_tokens == 4 * response_normal.usage.output_tokens, 'cost_spike should multiply by 4'
print('   OK - cost_spike multiplies output tokens by 4')
print()

print('Testing incidents.json metadata:')
import json
with open('data/incidents.json', 'r', encoding='utf-8') as f:
    incidents_data = json.load(f)
    assert len(incidents_data) == 3, 'Should have 3 incidents'
    for incident_name in ['rag_slow', 'tool_fail', 'cost_spike']:
        assert incident_name in incidents_data
        incident_meta = incidents_data[incident_name]
        assert 'name' in incident_meta
        assert 'description' in incident_meta
        assert 'symptom' in incident_meta
        assert 'root_cause' in incident_meta
        assert 'expected_effect' in incident_meta
        assert 'detection_hints' in incident_meta
        print(f'   OK - {incident_name} has all required metadata')

print()
print('All tests passed!')
