from __future__ import annotations

import time
from dataclasses import dataclass

from . import metrics
from .mock_llm import FakeLLM
from .mock_rag import retrieve
from .pii import hash_user_id, summarize_text
from .tracing import langfuse_context, observe


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model
        self.llm = FakeLLM(model=model)

    @observe()
    def run(self, user_id: str, feature: str, session_id: str, message: str) -> AgentResult:
        started = time.perf_counter()
        docs = retrieve(message)
        prompt = f"Feature={feature}\nDocs={docs}\nQuestion={message}"
        response = self.llm.generate(prompt)
        quality_score = self._heuristic_quality(message, response.text, docs)
        latency_ms = int((time.perf_counter() - started) * 1000)
        cost_usd = self._estimate_cost(response.usage.input_tokens, response.usage.output_tokens)

        langfuse_context.update_current_trace(
            user_id=hash_user_id(user_id),
            session_id=session_id,
            tags=["lab", feature, self.model],
        )
        langfuse_context.update_current_observation(
            metadata={
                "doc_count": len(docs),
                "retrieval_hit": bool(docs),
                "used_fallback": not docs,
                "query_preview": summarize_text(message),
                "doc_preview": summarize_text(" ".join(docs), max_len=120) if docs else "",
                "answer_preview": summarize_text(response.text),
                "quality_score": quality_score,
            },
            usage_details={"input": response.usage.input_tokens, "output": response.usage.output_tokens},
        )

        metrics.record_request(
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            quality_score=quality_score,
        )

        return AgentResult(
            answer=response.text,
            latency_ms=latency_ms,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
        )

    def _estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        input_cost = (tokens_in / 1_000_000) * 3
        output_cost = (tokens_out / 1_000_000) * 15
        return round(input_cost + output_cost, 6)

    def _heuristic_quality(self, question: str, answer: str, docs: list[str]) -> float:
        normalized_question = question.lower()
        normalized_answer = answer.lower()

        if not docs:
            fallback_markers = ("could not find", "matching document", "ask about")
            score = 0.45 if all(marker in normalized_answer for marker in fallback_markers) else 0.2
            return round(score, 2)

        score = 0.55
        expected_terms = self._expected_terms(normalized_question, docs)
        hits = sum(1 for term in expected_terms if term in normalized_answer)
        if expected_terms:
            score += min(0.3, hits / len(expected_terms) * 0.3)
        if len(answer) <= 180:
            score += 0.1
        if any(marker in normalized_answer for marker in ("starter answer", "general fallback")):
            score -= 0.5
        if "[redacted" in normalized_answer:
            score -= 0.1
        return round(max(0.0, min(1.0, score)), 2)

    def _expected_terms(self, question: str, docs: list[str]) -> list[str]:
        doc_blob = " ".join(docs).lower()
        if "refund" in question or "7 days" in doc_blob:
            return ["7 days", "proof of purchase"]
        if any(token in question for token in ("metrics", "traces", "observability", "monitoring", "workflow")):
            return ["metrics", "traces", "logs"]
        if any(token in question for token in ("pii", "sensitive", "credit card", "email", "phone", "log", "logging")):
            return ["pii", "sensitive"]
        if "tail latency" in question:
            return ["traces", "rag_slow"]
        if any(token in question for token in ("alert", "latency", "incident")):
            return ["triggers", "mitigation"]
        return [term for term in ("metrics", "traces", "logs", "pii", "sensitive") if term in doc_blob]
