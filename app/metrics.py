from __future__ import annotations

from collections import Counter
from math import ceil, floor
from statistics import mean

REQUEST_LATENCIES: list[int] = []
REQUEST_COSTS: list[float] = []
REQUEST_TOKENS_IN: list[int] = []
REQUEST_TOKENS_OUT: list[int] = []
ERRORS: Counter[str] = Counter()
TRAFFIC: int = 0
QUALITY_SCORES: list[float] = []


def _as_non_negative_int(value: int | float) -> int:
    try:
        return max(int(round(float(value))), 0)
    except (TypeError, ValueError):
        return 0


def _as_non_negative_float(value: int | float, precision: int = 6) -> float:
    try:
        return round(max(float(value), 0.0), precision)
    except (TypeError, ValueError):
        return 0.0


def record_request(
    latency_ms: int,
    cost_usd: float,
    tokens_in: int,
    tokens_out: int,
    quality_score: float,
) -> None:
    global TRAFFIC
    TRAFFIC += 1
    REQUEST_LATENCIES.append(_as_non_negative_int(latency_ms))
    REQUEST_COSTS.append(_as_non_negative_float(cost_usd))
    REQUEST_TOKENS_IN.append(_as_non_negative_int(tokens_in))
    REQUEST_TOKENS_OUT.append(_as_non_negative_int(tokens_out))
    QUALITY_SCORES.append(min(1.0, _as_non_negative_float(quality_score, precision=4)))



def record_error(error_type: str) -> None:
    normalized_error = str(error_type or "").strip() or "unknown_error"
    ERRORS[normalized_error] += 1



def percentile(values: list[int], p: int) -> float:
    if not values:
        return 0.0
    items = sorted(float(value) for value in values)
    bounded_percent = min(max(float(p), 0.0), 100.0)
    rank = (len(items) - 1) * (bounded_percent / 100.0)
    lower_index = floor(rank)
    upper_index = ceil(rank)

    if lower_index == upper_index:
        return round(items[lower_index], 2)

    interpolation = rank - lower_index
    result = items[lower_index] + (items[upper_index] - items[lower_index]) * interpolation
    return round(result, 2)



def snapshot() -> dict:
    p50 = percentile(REQUEST_LATENCIES, 50)
    p95 = percentile(REQUEST_LATENCIES, 95)
    p99 = percentile(REQUEST_LATENCIES, 99)
    avg_cost = round(mean(REQUEST_COSTS), 6) if REQUEST_COSTS else 0.0
    total_cost = round(sum(REQUEST_COSTS), 6)
    tokens_in_total = sum(REQUEST_TOKENS_IN)
    tokens_out_total = sum(REQUEST_TOKENS_OUT)
    error_breakdown = dict(sorted(ERRORS.items()))
    error_total = sum(error_breakdown.values())
    quality_avg = round(mean(QUALITY_SCORES), 4) if QUALITY_SCORES else 0.0

    return {
        "traffic": {
            "requests_total": TRAFFIC,
            "errors_total": error_total,
            "success_total": max(TRAFFIC - error_total, 0),
            "error_rate": round((error_total / TRAFFIC), 4) if TRAFFIC else 0.0,
        },
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "latency_p50": p50,
        "latency_p95": p95,
        "latency_p99": p99,
        "error_breakdown": error_breakdown,
        "token": {
            "input_total": tokens_in_total,
            "output_total": tokens_out_total,
            "total": tokens_in_total + tokens_out_total,
        },
        "tokens_in_total": tokens_in_total,
        "tokens_out_total": tokens_out_total,
        "cost": {
            "avg_usd": avg_cost,
            "total_usd": total_cost,
        },
        "avg_cost_usd": avg_cost,
        "total_cost_usd": total_cost,
        "quality_avg": quality_avg,
    }
