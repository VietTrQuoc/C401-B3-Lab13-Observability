# Báo cáo cá nhân - Bùi Quang Vinh
## 1. Thông tin cá nhân
- **Họ và tên**: Bùi Quang Vinh
- **Mã học viên**: 2A202600007
- **Vai trò trong nhóm**: Logic chatbot và chất lượng câu trả lời
- **Thứ tự thực hiện**: Làm thứ hai, sau khi Người 1 merge
- **Phạm vi file phụ trách chính**:
  - `app/agent.py`
  - `app/mock_llm.py`
  - `app/mock_rag.py`
- **Commit minh chứng chính**:
  - `6aded73` `feat(chatbot): improve retrieval and answer synthesis`

## 2. Nhiệm vụ được giao
Phần việc tôi phụ trách là hoàn thiện logic chatbot để starter app hoạt động như một chatbot hỏi đáp thông thường nhưng vẫn phù hợp với mục tiêu của bài lab observability. Chatbot phải:
- trả lời dựa trên tài liệu retrieve được
- có fallback rõ ràng nếu không tìm thấy tài liệu
- cho output ngắn gọn, ổn định, đúng ngữ cảnh
- không làm lộ PII qua answer preview
- không làm ảnh hưởng đến contract hiện có của agent

Các đầu việc chính:
1. Cải thiện `retrieve()` để bắt keyword tốt hơn cho các câu hỏi trong `data/sample_queries.jsonl` và `data/expected_answers.jsonl`.
2. Cải thiện `FakeLLM.generate()` để trả lời đúng ngữ cảnh `refund`, `policy`, `monitoring`, `alerts`.
3. Điều chỉnh `LabAgent.run()` và heuristic quality để phản ánh đúng chất lượng câu trả lời và metadata trace.
4. Giữ nguyên public interface của agent để không ảnh hưởng đến các file khác.

## 3. Đánh giá trạng thái ban đầu
Trước khi chỉnh sửa, tôi nhận thấy phần chatbot còn bốn vấn đề chính:
- **Retrieve chưa đủ tốt**: dễ bỏ sót câu hỏi diễn đạt khác mẫu hoặc match sai topic.
- **Câu trả lời còn chung chung**: chưa phân biệt rõ refund, monitoring, policy, alerts.
- **Quality heuristic còn yếu**: chỉ số `quality_avg` chưa có nhiều giá trị phân tích.
- **Có rủi ro lộ PII**: nếu answer hoặc preview không được kiểm soát, dữ liệu nhạy cảm có thể xuất hiện trong logs hoặc traces.

Những hạn chế này khiến chatbot tuy có thể phản hồi nhưng chưa đủ tốt để phục vụ validation, tracing, dashboard và demo incident.

## 4. Công việc đã thực hiện
### 4.1. `app/mock_rag.py` - cải thiện truy xuất tài liệu
Tôi chỉnh `retrieve()` theo hướng phân loại chủ đề bằng keyword có trọng số, thay vì chỉ so khớp đơn giản.

**Tổ chức lại topic và tài liệu**
- Tôi giữ `CORPUS` gọn nhưng rõ ràng theo 4 nhóm: `refund`, `monitoring`, `policy`, `alerts`.
- Việc phân chia này giúp câu hỏi được nối đúng với nhóm tài liệu nền tương ứng.

**Xây dựng bảng `TOPIC_KEYWORDS`**
- `refund`: `refund`, `return`, `money back`, `proof of purchase`
- `monitoring`: `metrics`, `traces`, `logs`, `observability`, `workflow`
- `policy`: `pii`, `sensitive`, `credit card`, `email`, `phone`, `logging`
- `alerts`: `alert`, `tail latency`, `incident`, `mitigation`, `runbook`

Mỗi từ khóa có trọng số khác nhau. Nhờ đó hệ thống có thể chấm điểm mức độ phù hợp của câu hỏi với từng topic, thay vì chỉ kiểm tra có từ khóa hay không.

**Xếp hạng topic thay vì match cứng**
- Tôi dùng `_score_topic()` để chấm điểm từng topic.
- Các topic có điểm dương sẽ được sắp xếp giảm dần và ghép docs theo thứ tự ưu tiên.
- Cách này xử lý tốt hơn các câu hỏi chỉ thuộc một topic, có nhiều ý cùng lúc, hoặc dùng cách diễn đạt khác nhau.

**Giữ fallback rõ ràng**
- Nếu không có topic phù hợp, `retrieve()` trả về danh sách rỗng.
- Tôi giữ hành vi này để lớp sinh câu trả lời biết chắc là không có tài liệu, từ đó fallback đúng thay vì đoán.

**Giữ nguyên tích hợp incident**
- `tool_fail` vẫn ném `RuntimeError("Vector store timeout")`
- `rag_slow` vẫn thêm delay 2.5 giây

Nhờ vậy, phần incident của repo không bị ảnh hưởng khi tôi cải thiện retrieval.

### 4.2. `app/mock_llm.py` - cải thiện sinh câu trả lời
Ở file này, tôi nâng `FakeLLM.generate()` từ mức placeholder lên thành lớp sinh câu trả lời deterministic, ngắn gọn và bám tài liệu.

**Giữ output ổn định**
- Vì đây là repo lab, tôi ưu tiên tính ổn định để dễ kiểm tra bằng `expected_answers.jsonl`, dễ so sánh giữa các lần chạy và dễ giải thích trong demo.

**Xử lý riêng theo từng nhóm câu hỏi**
- **Refund**: luôn nhắc `7 days` và `proof of purchase`
- **Tail latency**: nhắc `slow traces`, so sánh `RAG` và `LLM spans`, kiểm tra `rag_slow`
- **Alerts**: nhấn mạnh `user impact`, `clear triggers`, `mitigation`
- **Monitoring**: nhấn mạnh `metrics`, `traces`, `logs`
- **Policy / PII**: nhấn mạnh không đưa dữ liệu nhạy cảm vào logs và chỉ dùng `sanitized summaries`
- **Monitoring + policy**: nếu câu hỏi kết hợp hai mảng, câu trả lời cũng kết hợp đúng hai ý

**Fallback rõ ràng khi không có docs**
Nếu `docs` rỗng, chatbot trả lời:
`I could not find a matching document. Ask about refund policy, monitoring, logging/PII, or alerts.`

Fallback này rõ ràng, an toàn và không bịa thông tin ngoài tài liệu.

**Giữ token usage và cost behavior**
- Tôi vẫn giữ cách tính token usage theo độ dài prompt/answer để metrics và cost phản ánh đúng hành vi hệ thống.
- Khi `STATE["cost_spike"]` bật thì `output_tokens` vẫn nhân 4 như thiết kế incident ban đầu.

### 4.3. `app/agent.py` - cải thiện luồng agent và quality heuristic
Trong `app/agent.py`, tôi không đổi public interface của `LabAgent`, nhưng tôi điều chỉnh logic nội bộ để retrieve, generation và tracing gắn với nhau rõ hơn.

**Tổ chức lại luồng `run()`**
Luồng xử lý sau khi chỉnh sửa gồm:
1. Tạo `message_preview` đã sanitize
2. Cập nhật trace với `user_id`, `session_id`, `feature`, `input`
3. Retrieve docs bằng `_retrieve_with_span()`
4. Tạo prompt theo `Feature`, `Docs`, `Question`
5. Sinh câu trả lời bằng `_generate_with_span()`
6. Tính `quality_score`, `latency_ms`, `cost_usd`
7. Cập nhật trace output và metadata cuối cùng
8. Ghi metrics request

**Tách span retrieve và generation**
- `start_span("rag-retrieval")`
- `start_generation("llm-generation")`

Việc tách rõ hai span giúp trace dễ đọc hơn và thuận lợi cho demo các incident như `rag_slow` hoặc `cost_spike`.

**Bổ sung metadata cho trace**
Tôi cập nhật thêm các trường:
- `doc_count`
- `retrieval_hit`
- `used_fallback`
- `quality_score`
- `latency_ms`
- `cost_usd`

Ngoài ra còn có preview của docs, prompt và answer trong span tương ứng. Nhờ đó trace có giá trị phân tích tốt hơn.

**Điều chỉnh heuristic quality**
Tôi viết lại `_heuristic_quality()` để điểm chất lượng phản ánh nội dung thực hơn:
- nếu không có docs nhưng fallback rõ ràng thì score ở mức trung bình
- nếu có docs và answer chứa đúng key facts thì score tăng
- nếu answer quá chung chung hoặc chứa marker xấu như `starter answer`, `general fallback` thì score giảm
- nếu có `[REDACTED]` không phù hợp thì score giảm

Phần `_expected_terms()` được gắn theo từng topic:
- refund → `7 days`, `proof of purchase`
- monitoring → `metrics`, `traces`, `logs`
- policy → `pii`, `sensitive`
- tail latency → `traces`, `rag_slow`
- alerts → `triggers`, `mitigation`

Nhờ vậy, `quality_avg` trên dashboard phản ánh sát hơn chất lượng response.

### 4.4. Đảm bảo an toàn dữ liệu trong answer preview
Tôi giữ nguyên tắc:
- không lặp lại email, số điện thoại, số thẻ mà người dùng nhập
- với câu hỏi về policy, chỉ trả lời theo nguyên tắc chung
- answer preview luôn đi qua `summarize_text()`

Điều này giúp chatbot phù hợp với yêu cầu observability an toàn của bài lab.

### 4.5. Hỗ trợ thêm cho dashboard ban đầu
Ngoài phần phụ trách chính, tôi có hỗ trợ phần dashboard ban đầu để nhóm có giao diện demo sớm. Phần hỗ trợ này gồm:
- tạo UI dashboard theo chủ đề VinBot/VinFast
- nối dashboard với `/metrics`, `/health`, `/incidents`
- bố trí đủ 6 panel chính
- thêm incident toggles và nút tạo demo traffic

Đây là phần hỗ trợ thêm, không phải trọng tâm chính của tôi.

## 5. Khó khăn gặp phải và cách xử lý
Tôi gặp ba khó khăn chính:
- **Cân bằng giữa đơn giản và độ phủ**: retrieval quá đơn giản sẽ bỏ sót query, quá phức tạp thì không phù hợp với mock RAG. Tôi chọn keyword ranking vì đây là điểm cân bằng tốt.
- **Giữ output ổn định nhưng vẫn có ngữ cảnh**: tôi dùng output deterministic theo topic, thay vì một mẫu chung cho mọi câu hỏi.
- **Làm cho quality score có ý nghĩa**: tôi gắn quality với key facts theo từng chủ đề, thay vì chấm điểm chung chung.

Ngoài ra, tôi luôn tránh đổi public contract để không ảnh hưởng đến phần việc của các thành viên khác.

## 6. Kiểm chứng và mức độ đáp ứng yêu cầu
Tôi đối chiếu phần việc với điều kiện bàn giao như sau:

**Đáp ứng dataset mẫu**
Sau chỉnh sửa, chatbot xử lý được các nhóm câu hỏi trong:
- `data/sample_queries.jsonl`
- `data/expected_answers.jsonl`

Kết quả chính:
- refund có `7 days`, `proof of purchase`
- monitoring có `metrics`, `traces`, `logs`
- policy có `PII`, `sensitive`, `sanitized summaries`
- alerts có `user impact`, `clear triggers`, `mitigation`
- tail latency có `slow traces`, `RAG`, `LLM spans`
- không có docs thì fallback rõ ràng

**Đáp ứng checkpoint của nhóm**
Trong `docs/report.md`, checkpoint sau khi phần chatbot hoàn thành là:
- chatbot trả lời đúng refund / monitoring / policy / alerts
- không còn starter answer chung chung
- answer preview không lộ PII

Các mục này khớp trực tiếp với thay đổi tôi đã thực hiện.

**Không phá vỡ hệ thống hiện có**
Tôi giữ nguyên public interface của agent, nên:
- endpoint `/chat` vẫn hoạt động bình thường
- metrics vẫn ghi nhận đầy đủ
- tracing vẫn thu được span và metadata
- load test script không cần sửa

**Đáp ứng yêu cầu an toàn dữ liệu**
Các câu hỏi chứa email, số điện thoại, số thẻ vẫn được chatbot trả lời theo hướng chính sách an toàn, không echo dữ liệu nhạy cảm.

## 7. Kết quả và tác động đối với repo
Phần việc tôi làm có tác động trực tiếp đến nhiều lớp trong repo:
- **Đối với chatbot**: câu trả lời đúng trọng tâm, ổn định, có fallback rõ ràng hơn.
- **Đối với tracing**: trace có metadata meaningful hơn nhờ biết request có docs hay đang fallback.
- **Đối với metrics và dashboard**: `quality_avg` có ý nghĩa hơn, tokens và cost phản ánh sát hơn behavior thực.
- **Đối với demo incident**: chatbot đủ ổn định để team dễ liên hệ behavior ứng dụng với logs, traces, metrics.
- **Đối với validation**: đáp ứng được expectation trong dataset mẫu, giúp kiểm thử nội dung khả thi hơn.

## 8. Tự đánh giá cá nhân
Tôi đánh giá phần việc của mình đã đáp ứng đúng yêu cầu được giao và có đóng góp thực tế cho toàn bộ repo.

Những điểm tôi làm tốt:
- cải thiện retrieval theo hướng phù hợp với dataset mẫu
- làm cho `FakeLLM` trả lời có ngữ cảnh và ổn định hơn
- thiết kế fallback rõ ràng, không bịa thông tin
- làm cho quality score có ý nghĩa hơn trên dashboard
- giữ được an toàn dữ liệu và không phá vỡ interface hiện có

Nếu có thêm thời gian, tôi muốn bổ sung:
1. unit test riêng cho từng topic trong `retrieve()` và `_build_answer()`
2. thêm query nhiễu để kiểm tra độ bền của logic phân loại topic
3. mở rộng heuristic quality để phân biệt tốt hơn giữa answer đủ ý và answer chỉ đúng một phần

## 9. Kết luận
Phần việc tôi thực hiện đã giúp biến starter app thành một chatbot có thể dùng được trong bối cảnh bài lab observability. Chatbot giờ đây:
- retrieve tài liệu chính xác hơn
- trả lời đúng trọng tâm hơn
- có fallback rõ ràng khi không có dữ liệu
- sinh trace metadata và quality metric có ý nghĩa hơn
- không làm lộ PII qua answer preview

Tôi cho rằng đây là một phần việc nền tảng, vì chatbot là điểm bắt đầu của toàn bộ luồng observability trong repo. Khi chatbot trả lời đúng và ổn định, các lớp phía sau như logging, tracing, metrics và dashboard mới phát huy được giá trị.

