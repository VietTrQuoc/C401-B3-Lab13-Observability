from __future__ import annotations

import hashlib
import re

PII_PATTERNS: list[tuple[str, str]] = [
    ("email", r"[\w\.-]+@[\w\.-]+\.\w+"),
    ("credit_card_amex", r"\b3[47]\d{2}[- ]?\d{6}[- ]?\d{5}\b"),
    ("credit_card", r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
    ("cccd", r"\b\d{12}\b"),
    ("passport", r"\b[A-Z]{1,2}\d{6,9}\b"),
    ("phone_vn", r"(?<!\w)(?:\+?84|0)(?:[\s\.-]?\d){8,10}(?!\w)"),
    (
        "vietnamese_address",
        r"\b(?:số|s\.|ngõ|ngách|phố|đường|phường|xã|quận|huyện|thành phố|tỉnh|tp\.)\s+[\w\s,\.]+(?:\d{1,5})?\b",
    ),
]


def scrub_text(text: str) -> str:
    """Scrub PII from text using ordered passes to avoid overlap between patterns."""
    safe = text
    for _ in range(2):
        for name, pattern in PII_PATTERNS:
            safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe, flags=re.IGNORECASE)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    """Create a safe summary that doesn't leak PII in log previews."""
    safe = scrub_text(text).strip().replace("\n", " ")

    if not safe or safe.count("[REDACTED_") > 2:
        return "[CONTENT_REDACTED_FOR_PRIVACY]"

    if len(safe) > max_len:
        last_space = safe.rfind(" ", 0, max_len)
        if last_space > max_len - 20:
            safe = safe[:last_space]
        else:
            safe = safe[:max_len]
        safe += "..."

    return safe


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
