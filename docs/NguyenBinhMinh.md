# Báo cáo cá nhân — Nguyễn Bình Minh — 2A202600137

> Day 13 Observability Lab — Nhóm C401-B3
> Repo: https://github.com/VietTrQuoc/C401-B3-Lab13-Observability
> Vai trò: **Validation, load test, SLO/alerts, datasets và tài liệu nộp bài**

---

## 1. Phạm vi công việc

Nhiệm vụ chính là:

- Chốt bộ **validation & load test** để chạy smoke test và grading tự động.
- Đồng bộ **SLO / alert / schema** với behavior thật của app.
- Hoàn thiện **datasets** (sample queries + expected answers) phục vụ chatbot đã được Người 2 cải thiện.
- Chốt toàn bộ **documentation** để nhóm có thể demo và nộp bài.

Sau khi core pipeline đã ổn định, tôi còn nhận trách nhiệm **nâng cấp Langfuse tracing theo best-practice** (nested spans, generation type, flush on shutdown) để dashboard và grading evidence có chất lượng cao hơn.

---

## 2. Commit của cá nhân

| Commit | Mô tả | Scope |
|---|---|---|
| `bfcd1b0` | `chore(observability): finalize validation, configs, datasets and docs` | Toàn bộ task chính của Người 6 (11 files, +658/-159) |
| `e5023f0` | `feat(tracing): nested spans and generation type for Langfuse` | Áp dụng `langfuse/skills` instrumentation guide vào `app/agent.py`, `app/tracing.py`, `app/main.py` |
| `54920c8` | `report` | Tạo `docs/report.md` (báo cáo nhóm) |

---

## 3. Công việc chi tiết

### 3.1 `scripts/load_test.py`
- Viết lại load test để phục vụ cả smoke test và demo concurrency:
  - Hỗ trợ `--concurrency` (ThreadPoolExecutor) và `--repeat` để lặp lại input set.
  - Sinh `x-request-id` prefix (`demo-001-ab12cd`) để dễ tracking trong Langfuse và log.
  - Đọc `data/expected_answers.jsonl` → evaluate `must_include` / `must_not_include` cho từng response.
  - Summary cuối chạy in p50 / p95 / p99 + số answer expectation failures.
  - Exit code khác nhau cho HTTP failure (1) và answer quality failure (2) — giúp CI/grading phân biệt.

### 3.2 `scripts/validate_logs.py`
- Kiểm tra nhiều tầng để grading chấm tự động:
  - **Schema**: required fields, JSON well-formed.
  - **API enrichment**: mỗi log phải có `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env`.
  - **Response fields**: `response_sent` phải đầy đủ `latency_ms`, `tokens_in`, `tokens_out`, `cost_usd`.
  - **PII patterns**: regex scan email / phone VN / CCCD / credit card / passport.
  - **Correlation ID coverage**: tối thiểu `--min-correlation-ids` (mặc định 2) ID duy nhất → bảo đảm có traffic thực tế.

### 3.3 `config/slo.yaml`
Chốt 4 SLI khớp trực tiếp với `/metrics`:

| SLI | Nguồn | Target | Window |
|---|---|---:|---|
| `latency_p95` | `/metrics.latency_p95` | ≤ 2000 ms | 1h |
| `error_rate` | `/metrics.traffic.error_rate` | ≤ 0.05 | 1h |
| `total_cost_usd` | `/metrics.total_cost_usd` | ≤ 0.02 USD | 1h-demo-run |
| `quality_avg` | `/metrics.quality_avg` | ≥ 0.75 | 1h |

Mỗi SLI có `note` giải thích scenario liên quan (`rag_slow`, `tool_fail`, `cost_spike`).

### 3.4 `config/alert_rules.yaml`
3 alerts, mỗi alert map 1–1 tới scenario incident:

| Alert | Severity | Trigger | Scenario |
|---|---|---|---|
| `high_latency_p95` | P2 | `latency_p95 > 2500 for 5m` | `rag_slow` |
| `high_error_rate` | P1 | `error_rate > 0.05 for 5m` | `tool_fail` |
| `cost_budget_spike` | P2 | `avg_cost_usd > 0.0012 for 15m` | `cost_spike` |

Mỗi alert có link sang section tương ứng trong `docs/alerts.md`.

### 3.5 `config/logging_schema.json`
- Chuẩn hoá JSON Schema cho log records: required fields, properties, type constraints.
- Khớp với payload sau PII scrubbing để `validate_logs.py` không báo false positive.

### 3.6 Datasets
- **`data/sample_queries.jsonl`**: mix query thường (refund, monitoring, logging, alerts) + query chứa PII (email `student@vinuni.edu.vn`, phone `0987654321`, credit card `4111 1111 1111 1111`).
- **`data/expected_answers.jsonl`**: `must_include` + `must_not_include` tokens để `load_test.py` auto-verify chất lượng trả lời.

### 3.7 Documentation
- **`docs/alerts.md`**: 3 runbook chi tiết (symptom → first checks → expected evidence → mitigation).
- **`docs/dashboard-spec.md`**: spec 6 panels cho dashboard (latency / cost / token / quality / error / traffic-by-feature).
- **`docs/grading-evidence.md`**: checklist thu thập evidence cho grading.
- **`docs/blueprint-template.md`**: sửa tags để parseable cho auto-grading.

### 3.8 Nâng cấp Langfuse tracing (bonus — `e5023f0`)
Sau khi cài skill `github.com/langfuse/skills` và đọc `instrumentation.md`, tôi rà lại `app/tracing.py` và `app/agent.py` theo baseline của Langfuse:

| Trước | Sau |
|---|---|
| Trace phẳng (1 span duy nhất tên `run`) | Nested: `chat-response` → `rag-retrieval` (span) → `llm-generation` (generation) |
| `@observe()` capture toàn bộ args (bao gồm `user_id` thô) | `capture_input=False` + `update_current_trace(input={message, feature})` explicit |
| LLM call không có `as_type=generation`, không có `model` | `as_type="generation"`, `model="claude-sonnet-4-5"` → enable cost/model analytics trong UI |
| `usage_details` wrap trong metadata | Pass thẳng vào generation → token tracking đúng chuẩn |
| Không có `flush()` | `langfuse.flush()` trong FastAPI shutdown hook |
| Env vars không load khi chạy qua uvicorn | `load_dotenv()` ở đầu `main.py` → tracing_enabled=True từ đầu |
| Không score | `score_current_trace(name="quality", value=...)` → filter theo chất lượng trong Langfuse UI |

Kết quả: mỗi trace trên https://cloud.langfuse.com giờ có 2 nested observations (retrieval + generation), có model name, token usage, và quality score — đáp ứng đầy đủ 7 baseline requirements mà `langfuse/skills` instrumentation guide yêu cầu.

---

## 4. Điều kiện bàn giao — self-check

- [x] `scripts/load_test.py --concurrency 5` chạy 11/11 request thành công, p95 < 1s khi không có incident.
- [x] `scripts/validate_logs.py` không báo PII leak với bộ query mẫu.
- [x] `/metrics` trả đủ 6 metric key cho dashboard.
- [x] 3 alert map đúng tới 3 scenario incident.
- [x] Docs (`alerts.md`, `dashboard-spec.md`, `grading-evidence.md`, `blueprint-template.md`) hoàn chỉnh.
- [x] ≥ 10 traces trên Langfuse có nested spans + generation type đúng chuẩn.
- [x] Tất cả commit của tôi có author `minh041104` → verifiable qua `git log --author=minh041104`.

---

## 5. Học được điều gì

- **Instrumentation baseline**: Langfuse khuyến nghị 7 yêu cầu tối thiểu (model, tokens, descriptive name, span hierarchy, observation type, PII masking, explicit input). Việc follow skill hướng dẫn giúp dashboard thực sự hữu ích thay vì chỉ có trace phẳng.
- **SLO design**: đặt window và threshold dựa trên behavior thật (đo p95 bình thường ~150ms, đặt threshold 2000/2500ms để catch `rag_slow`). Không đặt target trên trời.
- **Validation layering**: schema check → enrichment check → PII check → coverage check. Mỗi tầng catch một loại bug khác nhau.
- **Load test như một grading harness**: exit code phân biệt HTTP-failure vs answer-quality-failure giúp CI tự động phân loại vấn đề.

---

## 6. Link evidence

- Commit history cá nhân: `git log --author=minh041104 --pretty=format:"%h %s"`
- Langfuse project: https://cloud.langfuse.com (traces với tên `chat-response`)
- Files chính đã chỉnh sửa: [config/slo.yaml](../config/slo.yaml) · [config/alert_rules.yaml](../config/alert_rules.yaml) · [scripts/validate_logs.py](../scripts/validate_logs.py) · [scripts/load_test.py](../scripts/load_test.py) · [app/tracing.py](../app/tracing.py) · [app/agent.py](../app/agent.py) · [docs/alerts.md](alerts.md) · [docs/dashboard-spec.md](dashboard-spec.md)
