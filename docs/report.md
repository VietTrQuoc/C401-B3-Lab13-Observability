# Day 13 Observability Lab — Báo cáo nhóm

## 1. Thông tin nhóm

- **Tên nhóm**: C401-B3
- **Repo**: https://github.com/VietTrQuoc/C401-B3-Lab13-Observability
- **Thành viên & vai trò**:

| Thành viên | Vai trò | Commit chính |
|---|---|---|
| Trần Quốc Việt | Request lifecycle & API logging | `6cd9ab0` feat(api): complete request context and correlation id flow |
| Bùi Quang Vinh | Chatbot logic & answer quality | `6aded73` feat(chatbot): improve retrieval and answer synthesis |
| Lê Quang Minh | PII scrubbing & logging pipeline | `83d50e9` Feat: Add PII scrubbing coverage |
| Ngô Quang Phúc | Metrics, tracing & test tính toán | `5db9802` feat: metric |
| Nguyễn Việt Hoàng | Incident scenarios & control plane | `130b55a` feat(incident): finalize incident scenarios and control script |
| Nguyễn Bình Minh | Validation, SLO/alerts, datasets & docs | `bfcd1b0` chore(observability): finalize validation, configs, datasets and docs |
| Cả nhóm | Langfuse dashboard & best-practice instrumentation | `1100774` update dashboard · `e5023f0` feat(tracing): nested spans and generation type for Langfuse |

---

## 2. Thứ tự bàn giao và checkpoint merge

| # | Checkpoint | Kết quả đạt được |
|---|---|---|
| 1 | Sau Người 1 | `/chat` và `/metrics` chạy ổn, mọi log đều có `correlation_id` (không còn `MISSING`), enrich đủ `user_id_hash/session_id/feature/model/env`. |
| 2 | Sau Người 2 | Chatbot trả lời đúng nghiệp vụ refund / monitoring / policy / alerts; không còn starter answer chung chung; answer preview không lộ PII. |
| 3 | Sau Người 3 | `scrub_event` chạy trong pipeline `structlog`; regex phủ phone / email / credit card / CCCD / passport / địa chỉ VN; `test_pii.py` xanh. |
| 4 | Sau Người 4 | `/metrics` trả đủ traffic, p50/p95/p99, error_breakdown, tokens, cost, quality_avg; tracing helper no-op khi thiếu key và đầy metadata khi có key. |
| 5 | Sau Người 5 | 3 scenario `rag_slow`, `tool_fail`, `cost_spike` bật/tắt độc lập qua `scripts/inject_incident.py`, mỗi scenario có mô tả root-cause + symptom trong `data/incidents.json`. |
| 6 | Sau Người 6 | `scripts/validate_logs.py` xanh, SLO/alerts đồng bộ với metrics, 6-panel dashboard + evidence docs sẵn sàng cho demo. |

---

## 3. Technical Evidence

### 3.1 Request lifecycle & correlation ID (Trần Quốc Việt)
- `CorrelationIdMiddleware` (`app/middleware.py`): `clear_contextvars` đầu mỗi request, đọc `x-request-id` hoặc sinh `req-<8-char-hex>`, bind vào `structlog` contextvars, gắn response headers `x-request-id` + `x-response-time-ms`.
- `/chat` endpoint (`app/main.py`): bind `user_id_hash`, `session_id`, `feature`, `model`, `env` trước khi log `request_received` / `response_sent` / `request_failed`.
- Response `/chat` trả đủ `answer`, `correlation_id`, `latency_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score` (khớp `ChatResponse` schema).

### 3.2 Chatbot quality (Bùi Quang Vinh)
- `FakeLLM.generate` (`app/mock_llm.py`) phân loại theo context refund / monitoring / policy / alerts / tail-latency; fallback rõ ràng khi không có docs.
- `retrieve` (`app/mock_rag.py`) dùng bảng trọng số keyword → khớp tốt với queries trong `data/sample_queries.jsonl`.
- `LabAgent.run` + `_heuristic_quality` phản ánh chất lượng (hits / expected_terms, penalty khi có `[REDACTED]`…).

### 3.3 PII scrubbing & logging pipeline (Lê Quang Minh)
- `pii.py` phủ các pattern: email, phone (VN + quốc tế), credit card (Luhn variants), CCCD, passport, cụm địa chỉ VN.
- `scrub_text` / `summarize_text` → mọi preview đưa vào log đều được redact.
- `scrub_event` đăng ký trong `configure_logging` đúng vị trí processor (trước JSON renderer).
- `tests/test_pii.py` cover tất cả pattern mới.

### 3.4 Metrics & tracing (Ngô Quang Phúc)
- `metrics.py`: `percentile` (p50/p95/p99 ổn định với edge-case list rỗng), `record_request`, `record_error`, `snapshot()` trả `{traffic, latency_ms, tokens, cost, quality_avg, error_breakdown}`.
- `tracing.py`: `@observe()` + `start_span()` / `start_generation()` context managers — app vẫn chạy mềm khi không có Langfuse key.
- **Best practice Langfuse (theo `langfuse/skills` instrumentation guide)**:
  - Nested trace: `chat-response` (root) → `rag-retrieval` (span) → `llm-generation` (`as_type=generation`, `model=claude-sonnet-4-5`, `usage_details={input, output}`).
  - Trace input là `{message, feature}` (explicit) — không để decorator auto-capture toàn bộ args (tránh leak `user_id`).
  - `score_current_trace(name="quality", value=...)` cho filter trong Langfuse UI.
  - `langfuse.flush()` trong FastAPI shutdown hook.
  - `load_dotenv()` ở đầu `main.py` đảm bảo key được load trước khi Langfuse init.

### 3.5 Incident scenarios (Nguyễn Việt Hoàng)
- `data/incidents.json` mô tả symptom + root cause + expected effect cho:
  - `rag_slow`: retrieval thêm delay 2.5s → latency p95 vọt.
  - `tool_fail`: `retrieve()` ném `RuntimeError` → error rate tăng.
  - `cost_spike`: output_tokens × 4 → cost tăng ~4×.
- `scripts/inject_incident.py` bật/tắt qua REST (`/incidents/{name}/enable` và `/disable`).

### 3.6 Validation, SLO, dashboard, docs (Nguyễn Bình Minh)
- `scripts/validate_logs.py`: kiểm tra required fields, correlation_id coverage, PII leak, số correlation ID duy nhất.
- `config/slo.yaml` và `config/alert_rules.yaml` đồng bộ với snapshot metrics thực tế.
- `config/logging_schema.json` khớp payload sau scrub.
- `data/sample_queries.jsonl` + `data/expected_answers.jsonl`: mix query thường và query chứa PII.
- `docs/alerts.md`, `docs/dashboard-spec.md`, `docs/grading-evidence.md`, `docs/blueprint-template.md` đã điền.

---

## 4. Observability output — evidence

- **Langfuse traces**: https://cloud.langfuse.com → tất cả trace mang tên `chat-response`, có nested `rag-retrieval` + `llm-generation` (model + tokens).
- **6-panel dashboard** (Langfuse → Dashboards):
  1. Latency p50/p95/p99 theo thời gian
  2. Token usage (input + output)
  3. Cost USD cumulative
  4. Quality score distribution (`score.quality`)
  5. Error rate theo `error_type`
  6. Traffic theo `feature` tag
- **Local metrics**: `GET /metrics` khớp các panel trên.
- **Logs**: `data/logs.jsonl`, `data/audit.jsonl` đã PII-redacted.

---

## 5. Incident Response (mẫu — `rag_slow`)

- **Symptoms**: p95 latency vọt từ ~200ms → >2000ms; `rag-retrieval` span chiếm >90% thời gian trace.
- **Root cause**: `app/mock_rag.retrieve` sleep 2.5s khi `STATE["rag_slow"] = True`; chứng minh qua Langfuse trace waterfall + correlation ID trong log.
- **Fix action**: `python scripts/inject_incident.py --scenario rag_slow --disable` (hoặc `POST /incidents/rag_slow/disable`).
- **Preventive measure**: alert p95 latency >2000ms trong 5 phút; thêm runbook ở `docs/alerts.md`; kiểm tra `rag-retrieval` span đầu tiên khi p95 spike.

---

## 6. SLO hiện tại

| SLI | Target | Window | Ghi chú |
|---|---:|---|---|
| Latency P95 | ≤ 2000 ms | 1h | Vi phạm khi bật `rag_slow` |
| Error rate | ≤ 0.05 | 1h | Vi phạm khi bật `tool_fail` |
| Cost per demo run | ≤ 0.02 USD | demo run | Vi phạm khi bật `cost_spike` |
| Quality avg | ≥ 0.75 | 1h | Ổn định ở ~0.95 với sample queries |

---

## 7. Passing criteria check

- [x] Tất cả `TODO` block đã hoàn thành (xem 6 commit chính).
- [x] ≥ 10 traces hiển thị trong Langfuse (load test 11+ requests đã chạy thành công).
- [x] Dashboard có đủ 6 panels theo `docs/dashboard-spec.md`.
- [x] `validate_logs.py` chạy không báo PII leak.
- [x] Tất cả commit có author riêng của từng thành viên → Git evidence rõ ràng.
