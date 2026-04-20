# Evidence Collection Sheet

## Minimum command checklist
1. Start the API: `uvicorn app.main:app --reload`
2. Generate baseline traffic: `python scripts/load_test.py --concurrency 3 --repeat 2`
3. Validate logs: `python scripts/validate_logs.py`
4. Capture `/metrics`
5. Enable one incident and generate traffic again

## Required screenshots
- Langfuse trace list showing at least `10` traces
- One full trace waterfall with retrieval and model activity visible
- JSON logs with `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`
- A log line where message preview or answer preview is redacted
- `/metrics` or dashboard view showing all 6 required panels
- Alert rules view with runbook links

## Required command outputs to save
- The summary block from `python scripts/load_test.py --concurrency 3 --repeat 2`
- The final score from `python scripts/validate_logs.py`
- The JSON returned by `GET /metrics` after baseline load
- The JSON returned by `GET /metrics` during one enabled incident

## Optional evidence
- Before/after comparison for `rag_slow`
- Error spike evidence for `tool_fail`
- Cost spike evidence for `cost_spike`
- Improvements after mitigation
