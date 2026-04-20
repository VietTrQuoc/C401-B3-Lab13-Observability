# Alert Rules and Runbooks

This runbook assumes the app exposes `/health`, `/metrics`, `/chat`, Langfuse traces, and JSON logs in `data/logs.jsonl`.

## 1. High latency P95
- Severity: `P2`
- Metric source: `/metrics.latency_p95`
- Trigger: `latency_p95 > 2500 for 5m`
- User impact: chatbot responses feel slow and the tail of the distribution breaches SLO.
- Likely scenario: `rag_slow`
- First checks:
  1. Open the latest slow traces in Langfuse.
  2. Compare the retrieval span with the LLM generation span.
  3. Call `GET /health` and confirm whether `rag_slow` is enabled.
  4. Compare `latency_p50` vs `latency_p95` in `/metrics` to confirm this is tail latency, not total traffic growth.
- Expected evidence:
  - `response_sent` log lines with higher `latency_ms`
  - trace waterfall where retrieval dominates runtime
  - `/metrics.latency_p95` increases while error rate stays low
- Mitigation:
  - disable `rag_slow`
  - reduce retrieval fan-out or prompt size
  - add a fallback retrieval path for slow backends

## 2. High error rate
- Severity: `P1`
- Metric source: `/metrics.traffic.error_rate`
- Trigger: `traffic.error_rate > 0.05 for 5m`
- User impact: users receive `500` responses from `/chat`.
- Likely scenario: `tool_fail`
- First checks:
  1. Open `/metrics` and inspect `traffic.error_rate` and `error_breakdown`.
  2. Search logs for `event=request_failed`.
  3. Confirm `error_type` concentration, especially `RuntimeError`.
  4. Call `GET /health` and check whether `tool_fail` is enabled.
- Expected evidence:
  - `request_failed` log lines with `error_type`
  - `error_breakdown` spikes in `/metrics`
  - failed traces stop during retrieval/tool work
- Mitigation:
  - disable `tool_fail`
  - add retry or fallback retrieval behavior
  - keep the failing dependency behind a circuit breaker

## 3. Cost budget spike
- Severity: `P2`
- Metric source: `/metrics.avg_cost_usd`
- Secondary signal: `/metrics.tokens_out_total`
- Trigger: `avg_cost_usd > 0.0012 for 15m`
- User impact: response quality looks normal, but token burn and spend increase sharply.
- Likely scenario: `cost_spike`
- First checks:
  1. Compare `avg_cost_usd` and `total_cost_usd` before and after the spike.
  2. Compare `tokens_in_total` vs `tokens_out_total`.
  3. Check traces grouped by `feature` and `model`.
  4. Call `GET /health` and confirm whether `cost_spike` is enabled.
- Expected evidence:
  - `response_sent` log lines with abnormal `tokens_out`
  - higher `avg_cost_usd` in `/metrics`
  - no matching latency or error spike unless another incident is active
- Mitigation:
  - disable `cost_spike`
  - shorten prompts and output length
  - route easy requests to a cheaper model
  - cache or reuse repeated answers

## Demo command checklist
1. `python scripts/load_test.py --concurrency 3 --repeat 2`
2. `python scripts/validate_logs.py`
3. `python scripts/inject_incident.py --scenario rag_slow`
4. `python scripts/load_test.py --concurrency 5 --repeat 1`
5. Capture `/metrics`, logs, and one Langfuse trace waterfall.
