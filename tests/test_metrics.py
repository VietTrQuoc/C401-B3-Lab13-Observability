import pytest

from app import metrics


@pytest.fixture(autouse=True)
def reset_metrics_state() -> None:
    metrics.REQUEST_LATENCIES.clear()
    metrics.REQUEST_COSTS.clear()
    metrics.REQUEST_TOKENS_IN.clear()
    metrics.REQUEST_TOKENS_OUT.clear()
    metrics.ERRORS.clear()
    metrics.QUALITY_SCORES.clear()
    metrics.TRAFFIC = 0


def test_percentile_basic() -> None:
    assert metrics.percentile([100, 200, 300, 400], 50) == 250.0
    assert metrics.percentile([100, 200, 300, 400], 95) == 385.0
    assert metrics.percentile([], 95) == 0.0
    assert metrics.percentile([100, 200, 300], 120) == 300.0


def test_snapshot_empty() -> None:
    assert metrics.snapshot() == {
        "traffic": {
            "requests_total": 0,
            "errors_total": 0,
            "success_total": 0,
            "error_rate": 0.0,
        },
        "p50": 0.0,
        "p95": 0.0,
        "p99": 0.0,
        "latency_p50": 0.0,
        "latency_p95": 0.0,
        "latency_p99": 0.0,
        "error_breakdown": {},
        "token": {
            "input_total": 0,
            "output_total": 0,
            "total": 0,
        },
        "tokens_in_total": 0,
        "tokens_out_total": 0,
        "cost": {
            "avg_usd": 0.0,
            "total_usd": 0.0,
        },
        "avg_cost_usd": 0.0,
        "total_cost_usd": 0.0,
        "quality_avg": 0.0,
    }


def test_snapshot_with_data() -> None:
    metrics.record_request(latency_ms=100, cost_usd=0.1, tokens_in=10, tokens_out=20, quality_score=0.8)
    metrics.record_request(latency_ms=200, cost_usd=0.2, tokens_in=30, tokens_out=40, quality_score=1.2)
    metrics.record_request(latency_ms=400, cost_usd=0.05, tokens_in=-3, tokens_out=5, quality_score=-1)
    metrics.record_error("TimeoutError")

    result = metrics.snapshot()

    assert result["traffic"] == {
        "requests_total": 3,
        "errors_total": 1,
        "success_total": 2,
        "error_rate": 0.3333,
    }
    assert result["p50"] == 200.0
    assert result["p95"] == 380.0
    assert result["p99"] == 396.0
    assert result["token"] == {
        "input_total": 40,
        "output_total": 65,
        "total": 105,
    }
    assert result["cost"] == {
        "avg_usd": pytest.approx(0.116667),
        "total_usd": pytest.approx(0.35),
    }
    assert result["quality_avg"] == 0.6


def test_error_breakdown_normalizes_names() -> None:
    metrics.record_error("TimeoutError")
    metrics.record_error(" TimeoutError ")
    metrics.record_error("")
    metrics.record_error("ValueError")

    assert metrics.snapshot()["error_breakdown"] == {
        "TimeoutError": 2,
        "ValueError": 1,
        "unknown_error": 1,
    }
