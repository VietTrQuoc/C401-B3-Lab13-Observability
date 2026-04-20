import argparse
import concurrent.futures
import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_QUERIES = Path("data/sample_queries.jsonl")
DEFAULT_EXPECTATIONS = Path("data/expected_answers.jsonl")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    return records


def load_expectations(path: Path) -> dict[str, dict[str, Any]]:
    expectations: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return expectations

    for record in load_jsonl(path):
        message = str(record.get("message") or record.get("question") or "").strip()
        if message:
            expectations[message] = record
    return expectations


def summarize_text(text: str, max_len: int = 72) -> str:
    compact = " ".join(str(text).split())
    return compact[:max_len] + ("..." if len(compact) > max_len else "")


def percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((p / 100) * len(ordered) + 0.5) - 1))
    return round(ordered[index], 2)


def build_jobs(records: list[dict[str, Any]], repeat: int) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    request_index = 0
    for cycle in range(1, repeat + 1):
        for record in records:
            request_index += 1
            jobs.append(
                {
                    "request_index": request_index,
                    "cycle": cycle,
                    "payload": dict(record),
                }
            )
    return jobs


def ensure_server_ready(client: httpx.Client, *, base_url: str, timeout: float) -> None:
    try:
        response = client.get(f"{base_url}/health", timeout=timeout)
        response.raise_for_status()
    except Exception as exc:
        raise SystemExit(
            "Load test aborted: cannot reach the API at "
            f"{base_url}. Start `uvicorn app.main:app --reload` in another terminal first. "
            f"Original error: {exc}"
        ) from exc


def evaluate_answer(answer: str, expectation: dict[str, Any] | None) -> tuple[bool, list[str]]:
    if not expectation:
        return True, []

    normalized_answer = answer.lower()
    missing = [
        token
        for token in expectation.get("must_include", [])
        if str(token).lower() not in normalized_answer
    ]
    leaked = [
        token
        for token in expectation.get("must_not_include", [])
        if str(token).lower() in normalized_answer
    ]

    problems: list[str] = []
    if missing:
        problems.append("missing=" + ", ".join(missing))
    if leaked:
        problems.append("must_not_include=" + ", ".join(leaked))
    return not problems, problems


def send_request(
    client: httpx.Client,
    *,
    base_url: str,
    timeout: float,
    job: dict[str, Any],
    expectation: dict[str, Any] | None,
    request_id_prefix: str,
) -> dict[str, Any]:
    payload = job["payload"]
    headers: dict[str, str] = {}
    if request_id_prefix:
        headers["x-request-id"] = f"{request_id_prefix}-{job['request_index']:03d}-{uuid.uuid4().hex[:6]}"

    try:
        start = time.perf_counter()
        response = client.post(
            f"{base_url}/chat",
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        try:
            response_body = response.json()
        except ValueError:
            response_body = {}

        answer = str(response_body.get("answer", ""))
        answer_ok, answer_notes = evaluate_answer(answer, expectation)
        correlation_id = (
            response.headers.get("x-request-id")
            or response_body.get("correlation_id")
            or "missing"
        )

        return {
            "ok": response.status_code == 200,
            "answer_ok": answer_ok,
            "answer_notes": answer_notes,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "correlation_id": correlation_id,
            "feature": payload.get("feature", "qa"),
            "message": payload["message"],
            "cycle": job["cycle"],
            "request_index": job["request_index"],
        }
    except Exception as exc:
        return {
            "ok": False,
            "answer_ok": False,
            "answer_notes": [str(exc)],
            "status_code": "ERROR",
            "latency_ms": 0.0,
            "correlation_id": "missing",
            "feature": payload.get("feature", "qa"),
            "message": payload["message"],
            "cycle": job["cycle"],
            "request_index": job["request_index"],
        }


def print_result(result: dict[str, Any]) -> None:
    answer_status = "answer=PASS" if result["answer_ok"] else "answer=FAIL"
    detail = ""
    if result["answer_notes"]:
        detail = " | " + " ; ".join(result["answer_notes"])

    print(
        f"[{result['status_code']}] {result['correlation_id']} | "
        f"#{result['request_index']:03d}/cycle-{result['cycle']} | "
        f"{result['feature']} | {result['latency_ms']:.2f}ms | "
        f"{answer_status} | {summarize_text(result['message'])}{detail}"
    )


def print_summary(results: list[dict[str, Any]]) -> None:
    latencies = [result["latency_ms"] for result in results if result["ok"]]
    success_total = sum(1 for result in results if result["ok"])
    request_failures = len(results) - success_total
    answer_failures = sum(1 for result in results if result["ok"] and not result["answer_ok"])

    print("\n--- Load Test Summary ---")
    print(f"Total requests: {len(results)}")
    print(f"Successful responses: {success_total}")
    print(f"Request failures: {request_failures}")
    print(f"Answer expectation failures: {answer_failures}")
    print(f"Latency p50: {percentile(latencies, 50):.2f}ms")
    print(f"Latency p95: {percentile(latencies, 95):.2f}ms")
    print(f"Latency p99: {percentile(latencies, 99):.2f}ms")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate chat traffic and optionally verify answers.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="FastAPI base URL")
    parser.add_argument("--input", type=Path, default=DEFAULT_QUERIES, help="JSONL file of chat requests")
    parser.add_argument(
        "--expectations",
        type=Path,
        default=DEFAULT_EXPECTATIONS,
        help="JSONL file of expected answer fragments",
    )
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent requests")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat the whole input set N times")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout in seconds")
    parser.add_argument(
        "--request-id-prefix",
        default="demo",
        help="Prefix for x-request-id header. Use empty string to disable custom request IDs.",
    )
    parser.add_argument(
        "--skip-answer-check",
        action="store_true",
        help="Disable answer-content checks from the expectations JSONL file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    requests = load_jsonl(args.input)
    expectations = {} if args.skip_answer_check else load_expectations(args.expectations)
    jobs = build_jobs(requests, max(args.repeat, 1))

    with httpx.Client(timeout=args.timeout) as client:
        ensure_server_ready(client, base_url=args.base_url, timeout=args.timeout)
        if args.concurrency > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
                futures = [
                    executor.submit(
                        send_request,
                        client,
                        base_url=args.base_url,
                        timeout=args.timeout,
                        job=job,
                        expectation=expectations.get(job["payload"]["message"]),
                        request_id_prefix=args.request_id_prefix,
                    )
                    for job in jobs
                ]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
        else:
            results = [
                send_request(
                    client,
                    base_url=args.base_url,
                    timeout=args.timeout,
                    job=job,
                    expectation=expectations.get(job["payload"]["message"]),
                    request_id_prefix=args.request_id_prefix,
                )
                for job in jobs
            ]

    ordered_results = sorted(results, key=lambda item: item["request_index"])
    for result in ordered_results:
        print_result(result)

    print_summary(ordered_results)

    if any(not result["ok"] for result in ordered_results):
        raise SystemExit(1)
    if any(result["ok"] and not result["answer_ok"] for result in ordered_results):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
