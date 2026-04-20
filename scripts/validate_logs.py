import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_LOG_PATH = Path("data/logs.jsonl")
DEFAULT_SCHEMA_PATH = Path("config/logging_schema.json")
DEFAULT_MIN_CORRELATION_IDS = 2
BASE_REQUIRED_FIELDS = {"ts", "level", "service", "event"}
API_ENRICHMENT_FIELDS = {"correlation_id", "user_id_hash", "session_id", "feature", "model", "env"}
RESPONSE_FIELDS = {"latency_ms", "tokens_in", "tokens_out", "cost_usd"}
PII_PATTERNS = {
    "email": re.compile(r"[\w\.-]+@[\w\.-]+\.\w+", re.IGNORECASE),
    "phone_vn": re.compile(r"(?:\+84|0)[ \.-]?\d{3}[ \.-]?\d{3}[ \.-]?\d{3,4}"),
    "cccd": re.compile(r"\b\d{12}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    "passport": re.compile(r"\b[A-Z][0-9]{7}\b"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate JSON logs for schema, context and PII safety.")
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG_PATH, help="Path to logs.jsonl")
    parser.add_argument("--schema-path", type=Path, default=DEFAULT_SCHEMA_PATH, help="Path to JSON schema")
    parser.add_argument(
        "--min-correlation-ids",
        type=int,
        default=DEFAULT_MIN_CORRELATION_IDS,
        help="Minimum number of unique correlation IDs required for a pass",
    )
    return parser.parse_args()


def load_schema(path: Path) -> tuple[set[str], set[str]]:
    schema = json.loads(path.read_text(encoding="utf-8"))
    return set(schema.get("required", [])), set(schema.get("properties", {}).keys())


def load_records(path: Path) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    invalid_json_lines = 0

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            invalid_json_lines += 1
            continue
        if isinstance(record, dict):
            records.append(record)
        else:
            invalid_json_lines += 1
    return records, invalid_json_lines


def find_pii(raw_record: str) -> list[str]:
    hits: list[str] = []
    for name, pattern in PII_PATTERNS.items():
        if pattern.search(raw_record):
            hits.append(name)
    return hits


def main() -> None:
    args = parse_args()

    if not args.log_path.exists():
        print(f"Error: {args.log_path} not found. Run the app and send some requests first.")
        raise SystemExit(1)
    if not args.schema_path.exists():
        print(f"Error: {args.schema_path} not found.")
        raise SystemExit(1)

    schema_required_fields, schema_known_fields = load_schema(args.schema_path)
    records, invalid_json_lines = load_records(args.log_path)

    if not records:
        print(f"Error: No valid JSON logs found in {args.log_path}")
        raise SystemExit(1)

    missing_required = 0
    missing_enrichment = 0
    response_field_failures = 0
    request_flow_failures = 0
    pii_hits: list[dict[str, Any]] = []
    unknown_field_counter: Counter[str] = Counter()
    correlation_ids: set[str] = set()
    api_flow: dict[str, Counter[str]] = defaultdict(Counter)

    for record in records:
        missing_base_fields = schema_required_fields or BASE_REQUIRED_FIELDS
        if not missing_base_fields.issubset(record.keys()):
            missing_required += 1

        unknown_fields = set(record.keys()) - schema_known_fields
        for field in unknown_fields:
            unknown_field_counter[field] += 1

        if record.get("service") == "api":
            if not API_ENRICHMENT_FIELDS.issubset(record.keys()):
                missing_enrichment += 1
            elif any(not str(record.get(field, "")).strip() for field in API_ENRICHMENT_FIELDS):
                missing_enrichment += 1

            correlation_id = str(record.get("correlation_id", "")).strip()
            if not correlation_id or correlation_id == "MISSING":
                missing_required += 1
            else:
                correlation_ids.add(correlation_id)
                api_flow[correlation_id][record.get("event", "unknown")] += 1

            if record.get("event") == "response_sent":
                if not RESPONSE_FIELDS.issubset(record.keys()):
                    response_field_failures += 1
                elif any(record.get(field) is None for field in RESPONSE_FIELDS):
                    response_field_failures += 1

            if record.get("event") == "request_failed" and not str(record.get("error_type", "")).strip():
                response_field_failures += 1

        raw = json.dumps(record, ensure_ascii=False)
        pii_labels = find_pii(raw)
        if pii_labels:
            pii_hits.append(
                {
                    "event": record.get("event", "unknown"),
                    "correlation_id": record.get("correlation_id", ""),
                    "matches": pii_labels,
                }
            )

    for correlation_id, counts in api_flow.items():
        started = counts.get("request_received", 0)
        finished = counts.get("response_sent", 0) + counts.get("request_failed", 0)
        if started != 1 or finished != 1:
            request_flow_failures += 1

    print("--- Log Validation Results ---")
    print(f"Log file: {args.log_path}")
    print(f"Total valid JSON records: {len(records)}")
    print(f"Invalid JSON lines skipped: {invalid_json_lines}")
    print(f"Records missing required fields: {missing_required}")
    print(f"API records missing enrichment: {missing_enrichment}")
    print(f"API records missing response/error fields: {response_field_failures}")
    print(f"Request flow mismatches: {request_flow_failures}")
    print(f"Unique API correlation IDs: {len(correlation_ids)}")
    print(f"Potential PII leaks detected: {len(pii_hits)}")

    if unknown_field_counter:
        print(f"Unknown fields vs schema: {dict(sorted(unknown_field_counter.items()))}")
    if pii_hits:
        print("PII hit samples:")
        for hit in pii_hits[:5]:
            print(
                f"  - event={hit['event']} correlation_id={hit['correlation_id']} "
                f"matches={','.join(hit['matches'])}"
            )

    print("\n--- Scorecard ---")
    score = 100
    failed_checks: list[str] = []

    if invalid_json_lines > 0 or missing_required > 0:
        score -= 30
        failed_checks.append("JSON schema / required fields")
        print("- [FAILED] JSON schema / required fields")
    else:
        print("+ [PASSED] JSON schema / required fields")

    if len(correlation_ids) < args.min_correlation_ids or request_flow_failures > 0:
        score -= 20
        failed_checks.append("Correlation ID propagation / request lifecycle")
        print("- [FAILED] Correlation ID propagation / request lifecycle")
    else:
        print("+ [PASSED] Correlation ID propagation / request lifecycle")

    if missing_enrichment > 0 or response_field_failures > 0:
        score -= 20
        failed_checks.append("API enrichment / response fields")
        print("- [FAILED] API enrichment / response fields")
    else:
        print("+ [PASSED] API enrichment / response fields")

    if pii_hits:
        score -= 30
        failed_checks.append("PII scrubbing")
        print("- [FAILED] PII scrubbing")
    else:
        print("+ [PASSED] PII scrubbing")

    print(f"\nEstimated Score: {max(score, 0)}/100")
    if failed_checks:
        print("Failed checks: " + "; ".join(failed_checks))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
