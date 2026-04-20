from __future__ import annotations

import time

from .incidents import STATE

CORPUS = {
    "refund": ["Refunds are available within 7 days with proof of purchase."],
    "monitoring": ["Metrics detect incidents, traces localize them, and logs explain root cause."],
    "policy": ["Do not expose PII or other sensitive data in logs. Use sanitized summaries only."],
    "alerts": [
        "Alerts should map to user impact, define clear triggers, and include first checks plus mitigation steps.",
        "For tail latency, inspect slow traces, compare RAG and LLM spans, and check whether rag_slow is enabled.",
    ],
}

TOPIC_KEYWORDS = {
    "refund": {
        "refund": 3,
        "refunds": 3,
        "return": 2,
        "money back": 2,
        "proof of purchase": 3,
    },
    "monitoring": {
        "monitoring": 3,
        "observability": 3,
        "metrics": 3,
        "traces": 3,
        "trace": 2,
        "logs work together": 3,
        "workflow": 2,
        "root cause": 2,
        "debug": 1,
    },
    "policy": {
        "policy": 3,
        "pii": 3,
        "sensitive": 2,
        "privacy": 2,
        "credit card": 3,
        "card": 1,
        "email": 1,
        "phone": 1,
        "app logs": 2,
        "logging": 2,
        "logged": 2,
        "log": 1,
        "logs": 1,
    },
    "alerts": {
        "alert": 3,
        "alerts": 3,
        "tail latency": 4,
        "latency": 2,
        "slow": 1,
        "slo": 2,
        "incident": 1,
        "runbook": 2,
        "mitigation": 2,
    },
}


def retrieve(message: str) -> list[str]:
    if STATE["tool_fail"]:
        raise RuntimeError("Vector store timeout")
    if STATE["rag_slow"]:
        time.sleep(2.5)

    lowered = message.lower()
    ranked_topics = sorted(
        ((topic, _score_topic(lowered, topic)) for topic in TOPIC_KEYWORDS),
        key=lambda item: item[1],
        reverse=True,
    )

    matched_topics = [topic for topic, score in ranked_topics if score > 0]
    docs: list[str] = []
    for topic in matched_topics:
        for doc in CORPUS[topic]:
            if doc not in docs:
                docs.append(doc)
    return docs


def _score_topic(message: str, topic: str) -> int:
    score = 0
    for keyword, weight in TOPIC_KEYWORDS[topic].items():
        if keyword in message:
            score += weight
    return score
