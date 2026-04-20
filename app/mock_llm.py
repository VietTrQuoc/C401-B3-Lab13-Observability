from __future__ import annotations

import ast
import time
from dataclasses import dataclass

from .incidents import STATE


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class FakeResponse:
    text: str
    usage: FakeUsage
    model: str


class FakeLLM:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model

    def generate(self, prompt: str) -> FakeResponse:
        time.sleep(0.15)
        question, feature, docs = _parse_prompt(prompt)
        answer = self._build_answer(question=question, feature=feature, docs=docs)
        input_tokens = max(20, len(prompt) // 4)
        output_tokens = max(24, len(answer) // 4)
        if STATE["cost_spike"]:
            output_tokens *= 4
        return FakeResponse(text=answer, usage=FakeUsage(input_tokens, output_tokens), model=self.model)

    def _build_answer(self, question: str, feature: str, docs: list[str]) -> str:
        lowered = question.lower()
        doc_blob = " ".join(docs).lower()
        has_monitoring = "metrics detect incidents" in doc_blob
        has_policy = "do not expose pii" in doc_blob
        has_alerts = "alerts should map to user impact" in doc_blob or "tail latency" in doc_blob
        if not docs:
            return (
                "I could not find a matching document. Ask about refund policy, monitoring, logging/PII, or alerts."
            )

        if "refund" in lowered:
            return "Refunds are available within 7 days and require proof of purchase."

        if "tail latency" in lowered:
            return "For tail latency, inspect slow traces, compare RAG and LLM spans, and check whether rag_slow is enabled."

        if "alert" in lowered:
            return "Alerts should map to user impact, define clear triggers, and include first checks plus mitigation steps."

        if has_monitoring and has_policy and any(token in lowered for token in ("policy", "monitoring", "logging")):
            return (
                "Monitoring uses metrics, traces, and logs together, and policy requires logs to exclude PII and keep only sanitized summaries."
            )

        if has_monitoring and any(token in lowered for token in ("metrics", "traces", "observability", "monitoring", "workflow", "debug")):
            return "Metrics detect incidents, traces localize them, and logs explain root cause."

        if has_policy and any(token in lowered for token in ("pii", "sensitive", "credit card", "email", "phone", "log", "logging", "policy")):
            return "PII and other sensitive data should not appear in logs. Log only sanitized summaries."

        if feature == "summary" and has_alerts:
            return "Alerts should map to user impact, define clear triggers, and include mitigation steps."

        if feature == "summary":
            return _summarize_docs(docs)
        return _summarize_docs(docs)


def _parse_prompt(prompt: str) -> tuple[str, str, list[str]]:
    feature = "qa"
    question = ""
    docs: list[str] = []
    for line in prompt.splitlines():
        if line.startswith("Feature="):
            feature = line.removeprefix("Feature=").strip() or "qa"
        elif line.startswith("Docs="):
            raw_docs = line.removeprefix("Docs=").strip()
            try:
                parsed = ast.literal_eval(raw_docs)
                if isinstance(parsed, list):
                    docs = [str(item) for item in parsed]
            except (SyntaxError, ValueError):
                docs = []
        elif line.startswith("Question="):
            question = line.removeprefix("Question=").strip()
    return question, feature, docs


def _summarize_docs(docs: list[str]) -> str:
    unique_docs: list[str] = []
    for doc in docs:
        if doc not in unique_docs:
            unique_docs.append(doc)
    if len(unique_docs) == 1:
        return unique_docs[0]
    return " ".join(unique_docs[:2])
