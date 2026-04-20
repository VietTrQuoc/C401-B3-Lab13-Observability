from __future__ import annotations

import hashlib
import re

PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone_vn": r"(?:\+84|0)[ \.-]?\d{3}[ \.-]?\d{3}[ \.-]?\d{3,4}", # Matches 090 123 4567, 090.123.4567, etc.
    "cccd": r"\b\d{12}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    # Thêm các pattern mới
    "passport": r"\b[A-Z]{1,2}\d{6,9}\b",  # Passport Việt Nam và quốc tế
    "vietnamese_address": r"\b(?:số|s\.|ngõ|ngách|phố|đường|phường|xã|quận|huyện|thành phố|tỉnh|tp\.)\s+[\w\s,\.]+(?:\d{1,5})?\b",  # Địa chỉ Việt Nam
    "phone_vn_mobile": r"\b(?:0|84|\+84)?\s*(?:9[0-9]|8[1-9]|3[2-9]|7[0|6-9]|5[6-9])\d{7}\b",  # Số điện thoại di động VN
    "credit_card_amex": r"\b3[47]\d{2}[- ]?\d{6}[- ]?\d{5}\b",  # American Express
}


def scrub_text(text: str) -> str:
    """Scrub PII from text using multiple passes to ensure thorough cleaning."""
    safe = text
    # Multiple passes to catch nested or overlapping patterns
    for _ in range(2):  # 2 passes should be sufficient for most cases
        for name, pattern in PII_PATTERNS.items():
            safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe, flags=re.IGNORECASE)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    """Create a safe summary that doesn't leak PII in log previews."""
    # First scrub the text to remove PII
    safe = scrub_text(text).strip().replace("\n", " ")
    
    # If after scrubbing there's nothing meaningful left, return a safe placeholder
    if not safe or safe.strip() == "" or safe.count("[REDACTED_") > 2:
        return "[CONTENT_REDACTED_FOR_PRIVACY]"
    
    # Truncate to max_len while ensuring we don't cut off in middle of a redacted section
    if len(safe) > max_len:
        # Find the last space before max_len to avoid cutting words
        last_space = safe.rfind(" ", 0, max_len)
        if last_space > max_len - 20:  # If space is close to end, use it
            safe = safe[:last_space]
        else:
            safe = safe[:max_len]
        safe += "..."
    
    return safe


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]