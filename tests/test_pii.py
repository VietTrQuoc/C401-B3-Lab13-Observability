# tests/test_pii.py
from app.pii import scrub_text, summarize_text, hash_user_id


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_phone_vn() -> None:
    # Test các định dạng phone VN khác nhau
    test_cases = [
        "Số điện thoại 0901234567",
        "Gọi +84 901 234 567",
        "Liên hệ 0 901-234-567",
        "Hotline 84.901.234.567"
    ]
    
    for phone_text in test_cases:
        out = scrub_text(phone_text)
        assert "901234567" not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    out = scrub_text("CCCD: 001234567890")
    assert "001234567890" not in out
    assert "REDACTED_CCCD" in out


def test_scrub_credit_card() -> None:
    # Test credit card thường
    out = scrub_text("Credit card: 4111 1111 1111 1111")
    assert "4111111111111111" not in out
    assert "REDACTED_CREDIT_CARD" in out
    
    # Test American Express
    out = scrub_text("Amex: 3782 822463 10005")
    assert "378282246310005" not in out
    assert "REDACTED_CREDIT_CARD_AMEX" in out


def test_scrub_passport() -> None:
    out = scrub_text("Passport: B12345678")
    assert "B12345678" not in out
    assert "REDACTED_PASSPORT" in out


def test_scrub_vietnamese_address() -> None:
    out = scrub_text("Địa chỉ: Số 123, ngõ 456, phường Cầu Diễn, quận Nam Từ Liêm, Hà Nội")
    assert "Cầu Diễn" not in out
    assert "Nam Từ Liêm" not in out
    assert "REDACTED_VIETNAMESE_ADDRESS" in out


def test_multiple_pii() -> None:
    text = "Liên hệ: user@example.com, phone 0901234567, CCCD 001234567890"
    out = scrub_text(text)
    assert "REDACTED_EMAIL" in out
    assert "REDACTED_PHONE_VN" in out
    assert "REDACTED_CCCD" in out
    # Không còn dữ liệu gốc
    assert "user@" not in out
    assert "0901234567" not in out
    assert "001234567890" not in out


def test_summarize_text_no_pii_leak() -> None:
    # Test summarize không lộ PII
    text = "Email của tôi là user@example.com và số điện thoại 0901234567, cảm ơn bạn!"
    summary = summarize_text(text, max_len=50)
    assert "user@" not in summary
    assert "0901234567" not in summary
    assert "REDACTED" in summary


def test_summarize_text_with_heavy_pii() -> None:
    # Test trường hợp có quá nhiều PII
    text = "Contact: user@example.com, phone 0901234567, CCCD 001234567890, card 4111111111111111"
    summary = summarize_text(text, max_len=30)
    # Nếu quá nhiều PII bị redact, nên trả về placeholder an toàn
    assert summary == "[CONTENT_REDACTED_FOR_PRIVACY]" or "REDACTED" in summary


def test_hash_user_id() -> None:
    # Test hash consistent
    hash1 = hash_user_id("user123")
    hash2 = hash_user_id("user123")
    assert hash1 == hash2
    assert len(hash1) == 12
    # Test different users có hash khác nhau
    hash3 = hash_user_id("user456")
    assert hash1 != hash3