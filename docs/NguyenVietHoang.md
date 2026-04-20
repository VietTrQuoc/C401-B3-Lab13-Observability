# Báo cáo cá nhân - Nguyễn Việt Hoàng

## 1. Thông tin cá nhân

- **Họ và tên**: Nguyễn Việt Hoàng
- **Mã học viên**: 2A202600455
- **Vai trò trong nhóm**: Scenario incident và control plane
- **Thứ tự thực hiện**: Làm thứ năm, sau khi Người 2 và Người 4 merge
- **Phạm vi file phụ trách**:
  - `app/incidents.py`
  - `scripts/inject_incident.py`
  - `data/incidents.json`
- **Commit evidence chính**:
  - `feat(incident): finalize incident scenarios and control script`

## 2. Nhiệm vụ được giao

Phần việc của tôi tập trung vào việc chuẩn hóa danh sách incident scenarios và xây dựng control plane để bật/tắt từng scenario độc lập, phục vụ cho việc demo và thực hành incident investigation của nhóm. Đây là phần quan trọng vì nó tạo ra các tình huống thực tế để nhóm có thể thực hành observability (log, trace, metrics) trong việc chẩn đoán nguyên nhân gốc rễ của sự cố.

Các đầu việc chính tôi được giao gồm:

1. Chuẩn hóa danh sách 3 scenario: `rag_slow`, `tool_fail`, `cost_spike` để phục vụ demo.
2. Bảo đảm API enable/disable incident từ script `inject_incident.py` để sử dụng được ngay cho demo.
3. Nếu cần, bổ sung metadata scenario trong `data/incidents.json` để dễ đối chiếu root cause, symptom, expected effect.
4. Kiểm tra để scenario tác động đúng vào agent/RAG/LLM hiện có mà không cần sửa file của người khác.

Điều kiện bàn giao đặt ra là phải có thể bật/tắt từng incident độc lập và demo team có mô tả rõ symptom và root cause cho từng scenario.

## 3. Công việc tôi đã hoàn thành

### 3.1. Chuẩn hóa danh sách scenario và nâng cấp metadata

Tôi đã nâng cấp file `data/incidents.json` để mỗi incident có đầy đủ metadata cần thiết cho việc demo và incident investigation:

- **`rag_slow`**:
  - `name`: "RAG Slowdown"
  - `description`: "Retrieval latency spike. Students should find slow RAG span in trace."
  - `symptom`: "High response latency (2-3s per request) with most of the time spent in the RAG retrieval span"
  - `root_cause`: "rag_slow incident flag is enabled in the system, introducing an artificial 2.5 second delay in RAG retrieval"
  - `expected_effect`: "p95 latency SLO violation, slow chat responses, visible in /metrics and traces"
  - `detection_hints`: Danh sách các gợi ý phát hiện (check metrics tail latency, xem span duration trong traces, kiểm tra /health endpoint)

- **`tool_fail`**:
  - `name`: "Vector Store Failure"
  - `description`: "Vector store or tool error. Students should identify error_type from logs."
  - `symptom`: "500 Internal Server Error responses from /chat endpoint with error type 'RuntimeError'"
  - `root_cause`: "tool_fail incident flag is enabled, causing the RAG retrieval function to throw 'Vector store timeout' exception"
  - `expected_effect`: "High error rate visible in /metrics, failed requests in logs with error_type"

- **`cost_spike`**:
  - `name`: "Cost Spike"
  - `description`: "Token usage spike. Students should explain higher output token cost."
  - `symptom`: "Unusually high token usage and cost per request, with output tokens 4x higher than normal"
  - `root_cause`: "cost_spike incident flag is enabled, multiplying output token count by 4, increasing cost"
  - `expected_effect`: "High token count and cost visible in /metrics and logs"

Metadata này giúp cho việc demo có một tài liệu tham khảo rõ ràng về từng incident, dễ phân biệt giữa symptom (triệu chứng) và root cause (nguyên nhân gốc rễ).

### 3.2. Đảm bảo API enable/disable incident hoạt động đúng

Tôi đã kiểm tra và xác nhận rằng toàn bộ luồng control plane đã sẵn sàng sử dụng:

- **`app/incidents.py`**: Quản lý trạng thái `STATE` và cung cấp ba hàm chính `enable(name)`, `disable(name)`, và `status()`.
- **`app/main.py`**: Định nghĩa hai endpoint `/incidents/{name}/enable` và `/incidents/{name}/disable` để bật/tắt incident thông qua HTTP request.
- **`scripts/inject_incident.py`**: CLI script để tương tác với hai endpoint trên, hỗ trợ tham số `--scenario` để chọn incident và `--disable` để tắt incident thay vì bật.

Việc thiết kế này cho phép người dùng dễ dàng bật/tắt từng incident độc lập mà không cần restart server, rất tiện lợi cho quá trình demo.

### 3.3. Kiểm tra scenario tác động đúng vào agent/RAG/LLM

Tôi đã kiểm tra và xác nhận rằng các incident đã được tích hợp đúng vào các module tương ứng mà không cần sửa file của người khác:

- **`rag_slow`**: Được xử lý trong `app/mock_rag.py` - khi flag `rag_slow` được bật, hàm `retrieve()` sẽ sleep 2.5 giây trước khi trả kết quả, tạo ra độ trễ nhân tạo trong việc truy xuất tài liệu.
- **`tool_fail`**: Được xử lý trong `app/mock_rag.py` - khi flag `tool_fail` được bật, hàm `retrieve()` sẽ ném ngoại lệ "Vector store timeout", mô phỏng trường hợp vector store gặp sự cố.
- **`cost_spike`**: Được xử lý trong `app/mock_llm.py` - khi flag `cost_spike` được bật, số lượng output tokens sẽ được nhân lên 4 lần, làm tăng chi phí sử dụng LLM một cách bất thường.

Việc tích hợp này đảm bảo rằng khi một incident được bật, nó sẽ tác động đúng vào luồng xử lý của hệ thống, tạo ra các symptom thực tế cho việc thực hành incident investigation.

### 3.4. Tạo file kiểm thử toàn bộ luồng incident

Để đảm bảo rằng toàn bộ luồng incident hoạt động đúng, tôi đã tạo file `verify_incidents.py` để kiểm tra:

1. Incidents được enable/disable đúng
2. `tool_fail` ném đúng exception "RuntimeError - Vector store timeout"
3. `cost_spike` nhân token output lên đúng 4 lần
4. `incidents.json` có đầy đủ metadata cần thiết

File kiểm thử này giúp đảm bảo rằng phần việc của tôi hoạt động ổn định trước khi merge vào nhánh chính.

## 4. Phân tích kỹ thuật sâu

### 4.1. Vì sao cần chuẩn hóa metadata cho mỗi incident

Trong một bài lab về observability và incident response, việc chuẩn hóa metadata cho mỗi incident là rất quan trọng vì:

- Nó tạo ra một ngôn ngữ chung cho nhóm khi thảo luận về các scenario.
- Nó giúp phân biệt rõ ràng giữa symptom (triệu chứng người dùng nhìn thấy) và root cause (nguyên nhân gốc rễ của vấn đề).
- Nó cung cấp gợi ý về cách phát hiện incident (detection hints), giúp người thực hành biết phải kiểm tra metrics, logs hay traces nào.

Nếu không có metadata chuẩn, mỗi người có thể hiểu và mô tả incident theo cách riêng, dẫn đến khó khăn trong việc phối hợp demo và incident investigation.

### 4.2. Vì sao cần bật/tắt incident độc lập

Việc thiết kế control plane để bật/tắt từng incident độc lập mang lại nhiều lợi ích:

- Người dùng có thể tập trung vào một incident mỗi lần, dễ dàng quan sát và phân tích symptom.
- Không cần restart server khi thay đổi incident, tiết kiệm thời gian cho việc demo.
- Có thể tạo ra các tình huống phức tạp hơn bằng cách bật nhiều incident cùng một lúc (nếu cần).

Thiết kế này phù hợp với mục tiêu của bài lab là thực hành incident investigation trong môi trường có kiểm soát.

### 4.3. Vì sao không cần sửa file của người khác

Tôi đã kiểm tra và xác nhận rằng các incident đã được tích hợp sẵn vào `mock_rag.py` và `mock_llm.py` bởi các thành viên trước. Việc không cần sửa file của người khác là một ưu điểm lớn vì:

- Nó tránh được xung đột code khi merge.
- Nó đảm bảo rằng phần việc của tôi không làm vỡ luồng xử lý hiện có của hệ thống.
- Nó tuân theo nguyên tắc "không làm thay đổi public contract" cho các file thuộc phạm vi của người khác.

Thay vì sửa file của người khác, tôi chỉ tập trung vào việc chuẩn hóa metadata và đảm bảo control plane hoạt động đúng.

## 5. Kiểm thử và mức độ đáp ứng yêu cầu

Tôi đã kiểm tra phần việc của mình với các điều kiện bàn giao như sau:

1. ✅ Có thể bật/tắt từng incident độc lập (thông qua script `inject_incident.py` hoặc trực tiếp gọi endpoints).
2. ✅ Demo team có mô tả rõ symptom và root cause cho từng scenario trong `data/incidents.json`.
3. ✅ Scenario tác động đúng vào agent/RAG/LLM hiện có mà không cần sửa file của người khác.
4. ✅ Tất cả kiểm thử trong file `verify_incidents.py` đều pass.

Về mặt kiểm thử nghiệp vụ, phần việc của tôi được thiết kế để hỗ trợ trực tiếp cho các bước demo và incident investigation sau này của nhóm:

- Người thực hành có thể bật `rag_slow` để thực hành phân tích tail latency bằng metrics và traces.
- Người thực hành có thể bật `tool_fail` để thực hành tìm error_type trong logs.
- Người thực hành có thể bật `cost_spike` để thực hành phân tích tăng chi phí bằng metrics.

Nếu cần kiểm chứng nhanh ở local, các bước phù hợp nhất là chạy file `verify_incidents.py`:

```powershell
python verify_incidents.py
```

Sau đó, bạn có thể khởi động server và thử bật/tắt incident bằng script `inject_incident.py`:

```powershell
# Bật rag_slow
python scripts/inject_incident.py --scenario rag_slow

# Tắt rag_slow
python scripts/inject_incident.py --scenario rag_slow --disable
```

## 6. Bằng chứng đầu ra và mức độ đáp ứng yêu cầu

### 6.1. Đáp ứng điều kiện bàn giao

Phần việc tôi hoàn thành đáp ứng đúng các yêu cầu đã giao:

- ✅ Chuẩn hóa 3 scenario: `rag_slow`, `tool_fail`, `cost_spike` với đầy đủ metadata.
- ✅ API enable/disable incident từ script `inject_incident.py` hoạt động đúng.
- ✅ `data/incidents.json` có đầy đủ metadata để dễ đối chiếu root cause, symptom, expected effect.
- ✅ Scenario tác động đúng vào agent/RAG/LLM hiện có mà không cần sửa file của người khác.
- ✅ Có thể bật/tắt từng incident độc lập.
- ✅ Demo team có mô tả rõ symptom và root cause cho từng scenario.

### 6.2. Giá trị của phần việc tôi làm đối với toàn nhóm

Phần việc của tôi là lớp nền để các thành viên phía sau thực hành và demo hiệu quả hơn:

1. Người thực hành có các scenario thực tế để thực hành incident investigation.
2. Người làm validation và dashboard có dữ liệu thực tế để kiểm tra và trình bày.
3. Người làm tracing có các span thực tế để phân tích.
4. Toàn bộ nhóm có một tài liệu tham khảo rõ ràng về từng incident trong `data/incidents.json`.

Nói cách khác, phần của tôi tạo ra các "bài toán" thực tế cho nhóm thực hành giải quyết bằng các kỹ năng observability đã học.

## 7. Tự đánh giá cá nhân

Tôi đánh giá phần việc của mình đạt yêu cầu tốt về cả kỹ thuật lẫn tính thực dụng:

- Tôi đã chuẩn hóa metadata cho mỗi incident rõ ràng, phân biệt được symptom và root cause.
- Tôi đã đảm bảo control plane hoạt động đúng, cho phép bật/tắt incident độc lập.
- Tôi đã kiểm tra và xác nhận rằng các incident tác động đúng vào luồng xử lý hiện có.
- Tôi đã tạo file kiểm thử để đảm bảo phần việc của mình hoạt động ổn định.

Qua phần việc này, tôi rút ra một điểm quan trọng: việc chuẩn hóa và tài liệu hóa các scenario incident là rất quan trọng cho việc thực hành và demo observability, vì nó tạo ra một môi trường có kiểm soát và dễ dàng lặp lại.

## 8. Đoạn ngắn để dán vào `blueprint-template.md`

### Nguyễn Việt Hoàng (Member E - Incidents &amp; Control Plane)

- **[TASKS_COMPLETED]**: Chuẩn hóa 3 scenario (`rag_slow`, `tool_fail`, `cost_spike`) với đầy đủ metadata (symptom, root_cause, expected_effect, detection_hints) trong `data/incidents.json`. Đảm bảo API enable/disable incident từ script `inject_incident.py` hoạt động đúng. Kiểm tra scenario tác động đúng vào agent/RAG/LLM hiện có mà không cần sửa file của người khác.
- **[EVIDENCE_LINK]**: `feat(incident): finalize incident scenarios and control script`
