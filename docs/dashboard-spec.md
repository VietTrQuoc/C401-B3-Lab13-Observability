# Dashboard Spec

Build one dashboard with 6 main panels backed by the current `/metrics` shape.

## Required main panels
1. Latency trend
   Use `/metrics.latency_p50`, `/metrics.latency_p95`, `/metrics.latency_p99` as three lines on one panel.
2. Traffic summary
   Use `/metrics.traffic.requests_total`, `/metrics.traffic.success_total`, and optionally derive request rate from the sampling interval.
3. Error rate and breakdown
   Plot `/metrics.traffic.error_rate` and show `/metrics.error_breakdown` as a table or stacked bar.
4. Cost
   Show `/metrics.avg_cost_usd` and `/metrics.total_cost_usd`.
5. Tokens
   Show `/metrics.tokens_in_total`, `/metrics.tokens_out_total`, and optionally `/metrics.token.total`.
6. Quality proxy
   Plot `/metrics.quality_avg` with an SLO/reference line at `0.75`.

## Presentation requirements
- Default time range: `1h`
- Auto refresh: every `15-30s`
- Units must be labeled: `ms`, `ratio`, `USD`, `tokens`, `score`
- Keep the main dashboard to `6-8` panels
- At least one panel should show the incident effect before/after toggling a scenario

## Suggested thresholds
- Latency panel: mark `2000ms` and `2500ms`
- Error rate panel: mark `0.05`
- Cost panel: mark `0.0012 avg_cost_usd`
- Quality panel: mark `0.75`

## Demo walkthrough
1. Show the steady-state dashboard after `python scripts/load_test.py --concurrency 3 --repeat 2`.
2. Enable one incident with `python scripts/inject_incident.py --scenario <name>`.
3. Re-run load with `--concurrency 5`.
4. Explain which panel moved first and how that maps to logs and traces.
