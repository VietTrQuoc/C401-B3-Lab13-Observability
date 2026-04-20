import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agent import LabAgent

BASE_URL = "http://127.0.0.1:8000"
EXPECTED_ANSWERS = Path("data/expected_answers.jsonl")
SAMPLE_QUERIES = Path("data/sample_queries.jsonl")


@dataclass
class Case:
    feature: str
    message: str
    must_include: list[str]
    must_not_include: list[str]
    expect_fallback: bool = False


EXTRA_CASES = [
    Case(
        feature="qa",
        message="Can I get a refund if I still have proof of purchase?",
        must_include=["7 days", "proof of purchase"],
        must_not_include=[],
    ),
    Case(
        feature="qa",
        message="How do metrics, traces, and logs help together?",
        must_include=["metrics", "traces", "logs"],
        must_not_include=[],
    ),
    Case(
        feature="qa",
        message="What should not appear in application logs? My phone is 0987654321",
        must_include=["PII", "sanitized"],
        must_not_include=["0987654321"],
    ),
    Case(
        feature="qa",
        message="Is credit card data allowed in logs?",
        must_include=["PII", "sensitive"],
        must_not_include=["credit card"],
    ),
    Case(
        feature="qa",
        message="How should alerts be designed?",
        must_include=["triggers", "mitigation"],
        must_not_include=[],
    ),
    Case(
        feature="qa",
        message="How do I debug tail latency?",
        must_include=["traces", "rag_slow"],
        must_not_include=[],
    ),
    Case(
        feature="summary",
        message="Summarize the monitoring policy for production logging",
        must_include=["metrics", "traces", "PII"],
        must_not_include=[],
    ),
    Case(
        feature="qa",
        message="What is your office address?",
        must_include=["could not find", "matching document"],
        must_not_include=[],
        expect_fallback=True,
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["local", "http"], default="local", help="Run against LabAgent or the live API")
    parser.add_argument("--base-url", default=BASE_URL, help="API base URL when --mode=http")
    args = parser.parse_args()

    cases = _load_cases()
    failures: list[str] = []

    for index, case in enumerate(cases, start=1):
        answer, quality = _ask(case, args.mode, args.base_url)
        issues = _validate(case, answer)
        label = "PASS" if not issues else "FAIL"
        print(f"[{label}] case={index} feature={case.feature} quality={quality:.2f}")
        print(f"  Q: {case.message}")
        print(f"  A: {answer}")
        if issues:
            for issue in issues:
                print(f"  - {issue}")
            failures.append(f"case {index}: {case.message}")
        print()

    print(f"Completed {len(cases)} chatbot smoke tests.")
    if failures:
        print(f"Failures: {len(failures)}")
        for failure in failures:
            print(f" - {failure}")
        sys.exit(1)

    print("All smoke tests passed.")


def _load_cases() -> list[Case]:
    cases: list[Case] = []

    for line in EXPECTED_ANSWERS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        cases.append(
            Case(
                feature="qa",
                message=item["question"],
                must_include=item["must_include"],
                must_not_include=[],
            )
        )

    sample_by_message = {
        item["message"]: item["feature"]
        for item in _read_jsonl(SAMPLE_QUERIES)
    }
    for case in EXTRA_CASES:
        if case.message in sample_by_message:
            case.feature = sample_by_message[case.message]
        cases.append(case)
    return cases


def _read_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            items.append(json.loads(line))
    return items


def _ask(case: Case, mode: str, base_url: str) -> tuple[str, float]:
    if mode == "http":
        payload = {
            "user_id": "u_smoke",
            "session_id": "s_smoke",
            "feature": case.feature,
            "message": case.message,
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{base_url}/chat", json=payload)
            response.raise_for_status()
            body = response.json()
            return str(body["answer"]), float(body["quality_score"])

    agent = LabAgent()
    result = agent.run(
        user_id="u_smoke",
        feature=case.feature,
        session_id="s_smoke",
        message=case.message,
    )
    return result.answer, result.quality_score


def _validate(case: Case, answer: str) -> list[str]:
    issues: list[str] = []
    lowered = answer.lower()

    for token in case.must_include:
        if token.lower() not in lowered:
            issues.append(f"missing required token: {token}")

    for token in case.must_not_include:
        if token.lower() in lowered:
            issues.append(f"unexpected token found in answer: {token}")

    fallback_detected = "could not find a matching document" in lowered
    if case.expect_fallback and not fallback_detected:
        issues.append("expected fallback answer")
    if not case.expect_fallback and fallback_detected:
        issues.append("unexpected fallback answer")

    return issues


if __name__ == "__main__":
    main()
