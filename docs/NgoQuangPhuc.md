# Báo cáo cá nhân - Ngô Quang Phúc

## 1. Thông tin cá nhân

- **Họ và tên**: Ngô Quang Phúc
- **Mã học viên**: 2A202600477
- **Vai trò trong nhóm**: Metrics, tracing và kiểm thử logic tính toán
- **Thứ tự thực hiện**: Làm thứ tư, sau khi phần của Người 2 đã được merge
- **Phạm vi file phụ trách**:
  - `app/metrics.py`
  - `app/tracing.py`
  - `tests/test_metrics.py`
- **Commit evidence chính**:
  - `5db9802` - `feat : metric`
  - `e5023f0` - `feat(tracing): nested spans and generation type for Langfuse`

## 2. Nhiệm vụ được giao

Phần việc của tôi tập trung vào hai lớp quan trọng của observability:

1. Chuẩn hóa lớp metrics để hệ thống xuất ra số liệu ổn định, dễ đọc, phục vụ dashboard và SLO.
2. Hoàn thiện tracing helper để ứng dụng vẫn chạy an toàn khi không cấu hình Langfuse, nhưng khi có key thì trace vẫn đầy đủ context để phân tích.
3. Mở rộng test cho logic tính toán, đặc biệt là các edge case như mảng rỗng, dữ liệu âm, lỗi trống hoặc percentile vượt ngưỡng.

Kết quả cần đạt là endpoint `/metrics` phải trả được đủ các trường:
`traffic`, `p50`, `p95`, `p99`, `error_breakdown`, `token`, `cost`, `quality_avg`, đồng thời các test trong `tests/test_metrics.py` phải chạy pass.

## 3. Công việc tôi đã hoàn thành

### 3.1. Chuẩn hóa `record_request`

Tôi chuẩn hóa toàn bộ dữ liệu đầu vào trước khi ghi metrics:

- `latency_ms`, `tokens_in`, `tokens_out` được ép về số nguyên không âm.
- `cost_usd` được ép về số thực không âm và làm tròn để tránh nhiễu số thập phân.
- `quality_score` được chặn trong khoảng hợp lệ, tránh làm sai trung bình chất lượng.

Mục tiêu của bước này là đảm bảo snapshot không bị méo bởi dữ liệu xấu như giá trị âm, chuỗi rỗng hoặc kiểu dữ liệu sai. Đây là phần quan trọng vì dashboard và SLO chỉ có ý nghĩa khi dữ liệu nguồn đã được làm sạch.

### 3.2. Chuẩn hóa `record_error`

Tôi xử lý tên lỗi theo hướng ổn định:

- Chuỗi lỗi được `strip()` để loại bỏ khoảng trắng đầu cuối.
- Nếu lỗi rỗng hoặc `None` thì chuẩn hóa thành `unknown_error`.
- Dữ liệu lỗi được gom bằng `Counter`, sau đó trả về dưới dạng `error_breakdown`.

Thiết kế này giúp dashboard không xuất hiện các key lỗi lộn xộn như `" TimeoutError "` và `"TimeoutError"` thành hai nhóm khác nhau.

### 3.3. Hoàn thiện `percentile`

Tôi xây dựng hàm `percentile(values, p)` theo hướng:

- Trả `0.0` nếu danh sách rỗng.
- Sắp xếp dữ liệu trước khi tính.
- Chặn `p` trong khoảng `0..100` để tránh giá trị ngoài biên.
- Dùng nội suy tuyến tính giữa hai phần tử gần nhất thay vì lấy cứng theo một chỉ số nguyên.

Lý do chọn nội suy tuyến tính là để kết quả `p50/p95/p99` mượt và ổn định hơn khi số lượng mẫu còn ít. Với hệ observability demo hoặc lab, số request trong từng đợt load test thường không lớn; nếu chỉ dùng cách lấy phần tử gần nhất thì P95 có thể nhảy gắt giữa các lần đo, làm dashboard khó đọc.

Ví dụ với độ trễ `[100, 200, 400]`:

- `p95` được tính với công thức:
  - `rank = (n - 1) * 0.95 = 2 * 0.95 = 1.9`
  - Chỉ số dưới là `1`, chỉ số trên là `2`
  - Nội suy: `200 + (400 - 200) * 0.9 = 380`

Nhờ vậy `p95 = 380.0`, phản ánh đúng xu hướng tail latency thay vì nhảy thẳng lên `400`. Đây cũng là lý do test của tôi kiểm tra chính xác giá trị `380.0` và `396.0` cho `p95/p99`.

### 3.4. Hoàn thiện `snapshot`

Tôi thiết kế `snapshot()` để vừa phục vụ API `/metrics`, vừa phục vụ đủ 6 panel trong `docs/dashboard-spec.md`.

Các nhóm dữ liệu chính gồm:

- `traffic`: `requests_total`, `errors_total`, `success_total`, `error_rate`
- `p50`, `p95`, `p99`
- `latency_p50`, `latency_p95`, `latency_p99`
- `error_breakdown`
- `token`: `input_total`, `output_total`, `total`
- `tokens_in_total`, `tokens_out_total`
- `cost`: `avg_usd`, `total_usd`
- `avg_cost_usd`, `total_cost_usd`
- `quality_avg`

Tôi giữ cả hai dạng tên trường:

- Dạng nhóm, ví dụ `traffic`, `token`, `cost`
- Dạng flat, ví dụ `latency_p95`, `avg_cost_usd`, `tokens_in_total`

Lý do là vì dashboard spec đang tham chiếu cả kiểu truy cập nhóm và kiểu truy cập phẳng. Việc trả song song hai dạng giúp frontend/dashboard lấy dữ liệu dễ hơn, đồng thời không phải viết thêm logic chuyển đổi.

### 3.5. Đảm bảo snapshot ổn định với dữ liệu rỗng

Một điểm dễ bị bỏ sót là hệ thống observability thường phải hoạt động ngay cả khi chưa có request nào. Tôi đã xử lý các trường hợp rỗng như sau:

- Percentile trả `0.0`
- Cost trung bình trả `0.0`
- Quality trung bình trả `0.0`
- Error rate trả `0.0`
- `error_breakdown` trả `{}` thay vì `None`

Nhờ vậy `/metrics` luôn có shape ổn định, frontend không bị vỡ khi load dashboard lần đầu.

### 3.6. Hoàn thiện tracing helper theo cơ chế fail-soft

Trong `app/tracing.py`, tôi triển khai helper theo hướng "có tracing thì dùng, không có thì không làm ứng dụng lỗi".

Các quyết định chính:

- Nếu thiếu `LANGFUSE_PUBLIC_KEY` hoặc `LANGFUSE_SECRET_KEY` thì `tracing_enabled()` trả `False`.
- Nếu import SDK Langfuse lỗi, các helper vẫn hoạt động ở chế độ no-op.
- `observe()` sẽ trả về identity decorator khi tracing không khả dụng.
- `start_span()` và `start_generation()` sẽ `yield None` nếu không tạo được client hoặc observation.
- Các lệnh như `flush()`, `score_current_trace()` và `update_current_trace()` đều bọc `try/except` để không làm hỏng luồng request chính.

Điểm quan trọng ở đây là observability phải hỗ trợ ứng dụng, không được làm ứng dụng chết theo. Nếu một hệ tracing bị cấu hình sai mà khiến API không chạy được thì đó là thiết kế không tốt.

### 3.7. Bổ sung đầy đủ trace metadata khi có Langfuse

Phần helper của tôi được sử dụng cùng luồng trace trong `app/agent.py`, giúp trace có đủ context phân tích:

- Tên trace: `chat-response`
- `user_id` đã hash
- `session_id`
- `tags`: `lab`, `feature`, `model`
- `input`: message preview và feature
- `metadata`: `latency_ms`, `cost_usd`, `quality_score`, `doc_count`, `retrieval_hit`, `used_fallback`
- Nested spans:
  - `rag-retrieval`
  - `llm-generation`

Thiết kế này giúp trace không chỉ có timing mà còn có ngữ nghĩa vận hành. Khi có sự cố, người xem trace có thể xác định nhanh request nào chậm, có hit RAG hay không, có dùng fallback hay không và chất lượng đầu ra đang ở mức nào.

## 4. Phân tích kỹ thuật sâu

### 4.1. Tôi hiểu gì về P95 và vì sao nó quan trọng hơn average

Trong hệ thống thực tế, dùng trung bình độ trễ là chưa đủ vì một số request rất chậm có thể bị che khuất bởi nhiều request nhanh. P95 là percentile bậc 95, nghĩa là 95% request có độ trễ nhỏ hơn hoặc bằng mức này, còn 5% request chậm hơn.

Trong bài lab observability, P95 quan trọng vì:

- Nó phản ánh tail latency, là phần người dùng thường cảm nhận rõ nhất.
- Khi bật incident `rag_slow`, chính P95/P99 là chỉ số tăng rõ ràng đầu tiên.
- Dashboard spec cũng dùng P95 làm SLI chính cho latency.

Ví dụ:

- Nếu 19 request có latency khoảng `100ms`, nhưng 1 request mất `3000ms`, average vẫn có thể trông "ổn".
- Nhưng P95 sẽ bị kéo lên mạnh, cho thấy rõ hệ thống đang có vấn đề ở nhóm request chậm.

Vì vậy, trong bài làm của tôi, `snapshot()` luôn xuất `p50`, `p95`, `p99` thay vì chỉ có average latency.

### 4.2. Tại sao tracing helper phải "mềm"

Observability là lớp hỗ trợ chẩn đoán, không phải logic nghiệp vụ cốt lõi. Do đó:

- Nếu Langfuse chưa cấu hình trong máy giảng viên hoặc máy demo, app vẫn phải chạy bình thường.
- Nếu SDK lỗi trong lúc tạo trace, request vẫn phải trả response.
- Nếu flush thất bại ở shutdown, ứng dụng vẫn phải tắt an toàn.

Tôi áp dụng nguyên tắc này bằng no-op decorator và context manager trả `None`. Cách làm này giúp code ở lớp trên vẫn viết rất sạch:

- Có thể dùng `@observe(...)` trực tiếp
- Có thể dùng `with start_span(...) as span:`
- Khi tracing tắt, code không cần `if/else` rải rác khắp nơi

Đây là một thiết kế tốt vì vừa giảm rủi ro runtime, vừa giữ cho mã nguồn dễ bảo trì.

### 4.3. Tại sao `error_breakdown` cần normalize

Nếu không normalize tên lỗi, dashboard rất dễ bị sai lệch vì cùng một loại lỗi có thể bị ghi ra nhiều key khác nhau do khoảng trắng hoặc dữ liệu trống. Khi đó:

- Bảng breakdown khó đọc
- Alert theo `error_type` bị loãng
- Việc so sánh trước/sau incident không còn chính xác

Việc chuẩn hóa `"", None -> unknown_error` và loại bỏ khoảng trắng là bước nhỏ nhưng có ý nghĩa lớn về chất lượng dữ liệu quan sát được.

## 5. Kiểm thử tôi đã bổ sung

Tôi mở rộng `tests/test_metrics.py` theo đúng các trường hợp quan trọng:

1. `test_percentile_basic`
   - Kiểm tra `p50`, `p95`
   - Kiểm tra list rỗng
   - Kiểm tra `p > 100`

2. `test_snapshot_empty`
   - Xác nhận toàn bộ shape `/metrics` ổn định khi chưa có dữ liệu

3. `test_snapshot_with_data`
   - Kiểm tra traffic, error rate, token, cost, quality, `p50/p95/p99`
   - Kiểm tra dữ liệu âm và điểm chất lượng vượt biên được chuẩn hóa đúng

4. `test_error_breakdown_normalizes_names`
   - Xác nhận lỗi được gom đúng nhóm
   - Xác nhận lỗi rỗng thành `unknown_error`

Kết quả kiểm thử:

```powershell
python -m pytest tests\test_metrics.py
```

Kết quả thực tế: `4 passed in 0.04s`

## 6. Bằng chứng đầu ra và mức độ đáp ứng yêu cầu

### 6.1. Đáp ứng điều kiện bàn giao

Tôi đã hoàn thành đầy đủ các điều kiện được giao:

- `/metrics` trả đủ `traffic`, `p50/p95/p99`, `error_breakdown`, `token`, `cost`, `quality_avg`
- Test metrics trong phạm vi file được giao chạy pass
- Tracing helper hoạt động fail-soft khi không có key
- Khi có key, trace chứa đủ metadata phục vụ phân tích context

### 6.2. Đáp ứng 6 panel trong dashboard spec

Phần metrics tôi làm phục vụ trực tiếp cho 6 panel:

1. Latency trend: `latency_p50`, `latency_p95`, `latency_p99`
2. Traffic summary: `traffic.requests_total`, `traffic.success_total`
3. Error rate and breakdown: `traffic.error_rate`, `error_breakdown`
4. Cost: `avg_cost_usd`, `total_cost_usd`
5. Tokens: `tokens_in_total`, `tokens_out_total`, `token.total`
6. Quality proxy: `quality_avg`

Nói cách khác, snapshot không chỉ đúng về mặt tính toán mà còn đúng về mặt khả dụng cho dashboard và vận hành.

## 7. Tự đánh giá cá nhân

Tôi đánh giá phần việc của mình đạt yêu cầu cả về kỹ thuật lẫn tính thực dụng:

- Không chỉ viết hàm tính toán, tôi còn chú ý đến độ ổn định dữ liệu đầu ra.
- Tôi chủ động xử lý edge case để dashboard không vỡ khi dữ liệu rỗng hoặc xấu.
- Tôi hiểu rõ ý nghĩa vận hành của `P95`, `error_breakdown`, `quality_avg`, không chỉ dừng ở mức "code cho chạy".
- Tôi bổ sung test để chứng minh logic metrics hoạt động đúng và có thể bàn giao an toàn cho người làm dashboard/SLO.

Qua phần việc này, tôi học được rằng observability tốt không chỉ là "có log, có trace, có metrics", mà là dữ liệu phải sạch, ổn định, có ngữ cảnh và dùng được cho chẩn đoán thực tế.

## 8. Đoạn ngắn để dán vào `blueprint-template.md`

### [MEMBER_D_NAME]
- [TASKS_COMPLETED]: Hoàn thiện `app/metrics.py`, `app/tracing.py`, `tests/test_metrics.py`. Chuẩn hóa `record_request`, `record_error`, `percentile`, `snapshot` để `/metrics` trả đủ `traffic`, `p50/p95/p99`, `error_breakdown`, `token`, `cost`, `quality_avg` phục vụ 6 panel dashboard. Triển khai tracing helper theo cơ chế fail-soft: app vẫn chạy khi thiếu `LANGFUSE` key, nhưng khi có key thì trace có đủ `user_id`, `session_id`, `tags`, `input`, `metadata`, nested spans và `quality score`. Bổ sung test cho percentile, snapshot rỗng, snapshot có dữ liệu và normalize `error_breakdown`.
- [EVIDENCE_LINK]: `5db9802` (`feat : metric`), `e5023f0` (`feat(tracing): nested spans and generation type for Langfuse`), kiểm thử `python -m pytest tests\\test_metrics.py` -> `4 passed`.
