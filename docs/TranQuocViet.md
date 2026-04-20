# Báo cáo cá nhân - Trần Quốc Việt

## 1. Thông tin cá nhân

- **Họ và tên**: Trần Quốc Việt
- **Mã học viên**: 2A202600307
- **Vai trò trong nhóm**: Nền tảng request lifecycle và API logging
- **Thứ tự thực hiện**: Làm đầu tiên
- **Phạm vi file phụ trách**:
  - `app/middleware.py`
  - `app/main.py`
  - `app/schemas.py`
- **Commit evidence chính**:
  - `6cd9ab0` - `feat(api): complete request context and correlation id flow`

## 2. Nhiệm vụ được giao

Phần việc của tôi tập trung vào lớp nền của request lifecycle và structured API logging. Đây là lớp rất quan trọng vì toàn bộ logging, tracing, metrics và incident investigation của nhóm đều phụ thuộc vào việc mỗi request phải có ngữ cảnh xuyên suốt, ổn định và truy vết được.

Các đầu việc chính tôi được giao gồm:

1. Hoàn thành `CorrelationIdMiddleware` để mỗi request đều có `correlation_id`, không còn tình trạng log bị `correlation_id = MISSING`.
2. Hoàn thiện việc enrich log trong endpoint `/chat` để các sự kiện `request_received`, `response_sent`, `request_failed` luôn mang đủ context vận hành như `user_id_hash`, `session_id`, `feature`, `model`, `env`.
3. Rà soát các schema `ChatRequest`, `ChatResponse`, `LogRecord` để khớp đúng luồng request-response và logging schema của hệ thống.
4. Đảm bảo endpoint `/chat` vẫn trả đủ `answer`, `correlation_id`, `latency`, `token`, `cost`, `quality_score`, đồng thời `/metrics` tiếp tục hoạt động bình thường sau khi tích hợp context logging.

Điều kiện bàn giao đặt ra là API phải chạy ổn định, log phải đủ context để validate, và phần việc của tôi không được phá vỡ public contract cho các thành viên làm chatbot, metrics, validation và dashboard ở các bước sau.

## 3. Công việc tôi đã hoàn thành

### 3.1. Hoàn thiện `CorrelationIdMiddleware`

Tôi hoàn thành middleware trong `app/middleware.py` để xử lý request context ngay từ đầu vòng đời request.

Các bước tôi triển khai gồm:

- Gọi `clear_contextvars()` ở đầu mỗi request để xóa sạch context cũ.
- Đọc `x-request-id` từ request header nếu client đã gửi sẵn.
- Nếu request không có header này, tự sinh ID mới theo format `req-<8-char-hex>` bằng `uuid.uuid4().hex[:8]`.
- Bind `correlation_id` vào `structlog.contextvars` bằng `bind_contextvars(correlation_id=...)`.
- Gắn `correlation_id` vào `request.state` để handler phía sau có thể truy cập và trả về cho client.
- Đo thời gian xử lý request bằng `time.perf_counter()` để tính `x-response-time-ms`.
- Ghi lại hai response header quan trọng là `x-request-id` và `x-response-time-ms`.

Mục tiêu của middleware này là biến `correlation_id` thành định danh xuyên suốt của request. Khi client gọi `/chat`, mọi log phát sinh trong cùng request sẽ dùng chung một ID, từ đó có thể nối log, metrics và trace lại với nhau khi phân tích sự cố.

### 3.2. Ngăn rò rỉ context giữa các request

Một lỗi phổ biến trong ứng dụng async là request sau có thể vô tình dùng lại context của request trước nếu không xóa đúng cách. Tôi xử lý tận gốc vấn đề này bằng `clear_contextvars()` ngay trước khi bind context mới.

Điểm này quan trọng vì nếu không clear context:

- `correlation_id` có thể bị lẫn giữa nhiều request khác nhau.
- `session_id`, `feature`, `model`, `user_id_hash` có thể gắn sai sang request kế tiếp.
- Script validate log sẽ thấy dữ liệu enrichment không nhất quán.
- Việc điều tra incident sẽ mất giá trị vì log không còn phản ánh đúng một request thực tế.

Với cách làm hiện tại, mỗi request bắt đầu từ một context sạch, sau đó mới bind dữ liệu mới của request đó.

### 3.3. Enrich context logging trong endpoint `/chat`

Trong `app/main.py`, tôi hoàn thiện lớp context logging cho endpoint `/chat` bằng `bind_contextvars(...)` trước khi log sự kiện đầu tiên.

Các field tôi bind vào context gồm:

- `user_id_hash`: hash từ `body.user_id` qua `hash_user_id(...)`
- `session_id`: lấy từ request body
- `feature`: lấy từ request body
- `model`: lấy từ `agent.model`
- `env`: lấy từ biến môi trường `APP_ENV`, mặc định là `dev`

Nhờ vậy, mọi log phát sinh sau đó trong request đều mang đủ context vận hành mà không cần truyền lặp đi lặp lại từng field vào mỗi lệnh log.

Đây là phần quan trọng vì logging cho observability không chỉ cần “có log”, mà log phải có ngữ cảnh để trả lời được các câu hỏi vận hành như:

- Request nào của session nào đang lỗi?
- User nào đang gặp sự cố, nhưng vẫn không lộ `user_id` thật?
- Lỗi này xảy ra ở feature nào?
- Request đó chạy model nào?
- Lỗi xảy ra ở môi trường `dev`, `staging` hay `prod`?

### 3.4. Chuẩn hóa 3 sự kiện log chính của API

Tôi đảm bảo endpoint `/chat` có đủ ba nhóm log cốt lõi của request lifecycle:

1. `request_received`
2. `response_sent`
3. `request_failed`

Chi tiết từng log:

- `request_received`
  - `service="api"`
  - `payload.message_preview` lấy từ `summarize_text(body.message)`
  - Mục đích là ghi nhận request đến nhưng không làm lộ nội dung nhạy cảm

- `response_sent`
  - `service="api"`
  - Ghi `latency_ms`, `tokens_in`, `tokens_out`, `cost_usd`
  - `payload.answer_preview` cũng được đi qua `summarize_text(...)`
  - Mục đích là vừa theo dõi hiệu năng, vừa lưu dấu vết câu trả lời ở mức an toàn cho log

- `request_failed`
  - `service="api"`
  - Ghi `error_type`
  - `payload.detail` chứa thông tin lỗi
  - `payload.message_preview` được scrub để tránh rò rỉ PII từ input người dùng
  - Đồng thời gọi `record_error(error_type)` để metrics nắm được lỗi phát sinh

Thiết kế này tạo ra một vòng đời log rõ ràng: request vào, request thành công hoặc thất bại. Đây là nền tảng rất quan trọng để người làm metrics, validation và incident response có dữ liệu đầu vào chuẩn.

### 3.5. Giữ contract của response `/chat`

Tôi rà soát luồng trả response trong endpoint `/chat` để bảo đảm không vì thêm logging/context mà làm thay đổi contract API.

`ChatResponse` vẫn trả đầy đủ:

- `answer`
- `correlation_id`
- `latency_ms`
- `tokens_in`
- `tokens_out`
- `cost_usd`
- `quality_score`

Trong đó `correlation_id` được lấy từ `request.state.correlation_id`, tức là chính ID đã được middleware gắn vào request từ đầu. Việc trả ngược lại field này trong response có ý nghĩa rất thực tế: khi frontend hoặc tester nhận được response, họ có thể dùng ngay `correlation_id` để truy ngược log và trace tương ứng.

### 3.6. Rà soát `ChatRequest` để khớp luồng request-response

Trong `app/schemas.py`, tôi kiểm tra và giữ cho `ChatRequest` đúng với luồng sử dụng thực tế của `/chat`.

Schema gồm:

- `user_id: str`
- `session_id: str`
- `feature: str = "qa"`
- `message: str` với `min_length=1`

Thiết kế này bảo đảm:

- Request luôn có đủ định danh phục vụ enrichment log.
- `feature` có default hợp lý để app không vỡ khi client không truyền.
- `message` không được rỗng, tránh sinh request vô nghĩa gây nhiễu metrics và logging.

### 3.7. Rà soát `LogRecord` để khớp logging schema

Tôi kiểm tra `LogRecord` để bảo đảm các field cần cho JSON logging và validation đều có mặt.

Schema hiện bao gồm các nhóm field chính:

- Nhóm bắt buộc: `ts`, `level`, `service`, `event`, `correlation_id`
- Nhóm enrichment: `env`, `user_id_hash`, `session_id`, `feature`, `model`
- Nhóm hiệu năng và chi phí: `latency_ms`, `tokens_in`, `tokens_out`, `cost_usd`
- Nhóm lỗi: `error_type`
- Nhóm mở rộng: `tool_name`, `payload`

Việc giữ schema rõ ràng giúp các lớp phía sau như `validate_logs.py`, `logging_schema.json` và dashboard có một hợp đồng dữ liệu ổn định để bám vào.

### 3.8. Đảm bảo `/metrics` không bị ảnh hưởng

Phần việc của tôi chủ yếu nằm ở request lifecycle và API logging, nhưng tôi vẫn phải bảo đảm không phá luồng metrics của hệ thống.

Trong `request_failed`, tôi giữ lệnh `record_error(error_type)` để khi request lỗi thì metrics vẫn được cập nhật đúng. Endpoint `/metrics` tiếp tục lấy dữ liệu từ `snapshot()` mà không bị ảnh hưởng bởi việc thêm middleware và context logging.

Điều này quan trọng vì observability là hệ thống liên thông: log, trace và metrics phải hỗ trợ lẫn nhau thay vì xung đột với nhau.

## 4. Phân tích kỹ thuật sâu

### 4.1. Vì sao `correlation_id` là trục sống còn của observability

Trong một request `/chat`, rất nhiều thành phần cùng tham gia xử lý:

- Middleware
- API endpoint
- Agent
- Retrieval
- LLM generation
- Metrics recording
- Tracing

Nếu không có một khóa định danh chung, các log chỉ là những dòng rời rạc. `correlation_id` giải quyết đúng vấn đề đó: nó nối toàn bộ sự kiện thuộc cùng một request thành một chuỗi có thể truy vết.

Ví dụ khi người vận hành thấy client báo lỗi, họ có thể:

1. Lấy `correlation_id` từ response header hoặc response body
2. Tìm tất cả log mang cùng `correlation_id`
3. Xác định request đã vào lúc nào, chạy bao lâu, có lỗi gì, có enrichment nào đi kèm
4. Đối chiếu với metrics và trace liên quan

Không có `correlation_id`, việc điều tra thường phải dựa vào timestamp gần đúng hoặc message text, vừa chậm vừa dễ sai.

### 4.2. Vì sao dùng `contextvars` thay vì truyền tay từng field log

Một cách ngây thơ là truyền `correlation_id`, `session_id`, `feature`, `model`, `env` vào từng câu lệnh `log.info(...)`. Cách đó có ba vấn đề:

- Dễ quên truyền một field ở một số log
- Code bị lặp nhiều, khó bảo trì
- Khi bổ sung field mới phải sửa ở quá nhiều nơi

Tôi dùng `structlog.contextvars` vì nó cho phép bind ngữ cảnh một lần ở đầu request, sau đó tự merge vào mọi log phát sinh trong luồng xử lý. Nhờ vậy:

- Log đồng nhất hơn
- Code gọn hơn
- Ít rủi ro sai sót hơn

Đây là lựa chọn đúng với kiểu ứng dụng FastAPI xử lý nhiều request độc lập và cần structured logging xuyên suốt.

### 4.3. Vì sao phải hash `user_id` thay vì log trực tiếp

Trong bài lab này, observability phải cân bằng giữa hai mục tiêu:

- Có đủ dữ liệu để chẩn đoán
- Không làm lộ thông tin nhạy cảm

Nếu log trực tiếp `user_id`, dữ liệu log sẽ tiện tra cứu nhưng tiềm ẩn rủi ro lộ danh tính. Nếu không log gì về user, ta lại mất khả năng nhận biết request của cùng một người dùng. Tôi chọn phương án trung gian đúng hơn cho môi trường observability là hash `user_id` trước khi bind log context.

Lợi ích của cách làm này:

- Vẫn nhóm được request của cùng một người dùng
- Không lộ ID gốc
- Tương thích với các bước scrubbing PII ở pipeline logging

### 4.4. Vì sao cần `x-response-time-ms` ở response header

Metrics tổng hợp như `p50/p95/p99` rất hữu ích cho dashboard, nhưng khi debug một request đơn lẻ thì response header thời gian xử lý cho phản hồi trực tiếp hơn.

`x-response-time-ms` giúp:

- Frontend hoặc tester thấy ngay request hiện tại chậm hay nhanh
- So sánh cảm nhận thực tế với số liệu aggregate trên dashboard
- Hỗ trợ demo incident như `rag_slow` dễ hơn vì độ trễ hiện ngay trên response

Tôi ghi header này từ middleware để bảo đảm đo cả thời gian xử lý của endpoint, thay vì chỉ đo một đoạn logic con trong handler.

## 5. Kiểm thử và mức độ đáp ứng yêu cầu

Tôi đối chiếu phần việc của mình với các điều kiện bàn giao như sau:

1. `/chat` vẫn chạy và trả đủ contract response
2. `/metrics` không bị ảnh hưởng bởi việc thêm middleware và enriched logging
3. API log không còn `correlation_id = MISSING`
4. `request_received`, `response_sent`, `request_failed` có đủ context cần thiết
5. Response header có `x-request-id` và `x-response-time-ms`

Về mặt kiểm thử nghiệp vụ, phần việc của tôi được thiết kế để hỗ trợ trực tiếp cho các bước validate sau này của nhóm:

- `validate_logs.py` có thể kiểm tra được enrichment field
- dashboard có thể đối chiếu request với log
- incident response có thể bám theo `correlation_id`
- tracing và metrics có dữ liệu đầu vào sạch, ổn định hơn

Nếu cần kiểm chứng nhanh ở local, các bước phù hợp nhất là:

```powershell
uvicorn app.main:app --reload
```

Sau đó gọi `/chat` với hoặc không với header `x-request-id` để xác nhận:

- Response body có `correlation_id`
- Response header có `x-request-id`
- Response header có `x-response-time-ms`
- JSON logs có đủ `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env`

## 6. Bằng chứng đầu ra và mức độ đáp ứng yêu cầu

### 6.1. Đáp ứng điều kiện bàn giao

Phần việc tôi hoàn thành đáp ứng đúng các yêu cầu đã giao:

- Middleware sinh và lan truyền `correlation_id` ổn định cho từng request
- Log API có context đầy đủ, không còn tình trạng thiếu `correlation_id`
- `/chat` trả đủ `answer`, `correlation_id`, `latency`, `token`, `cost`, `quality_score`
- `/metrics` tiếp tục hoạt động bình thường
- Schema request, response và log record khớp với nhu cầu request lifecycle và JSON logging

### 6.2. Giá trị của phần việc tôi làm đối với toàn nhóm

Phần việc của tôi là lớp nền để các thành viên phía sau làm tiếp hiệu quả hơn:

1. Người làm chatbot có log context đủ để phân tích chất lượng câu trả lời
2. Người làm PII/logging pipeline có dữ liệu chuẩn để scrub và validate
3. Người làm metrics và tracing có thể nối số liệu và trace với request cụ thể
4. Người làm incident và control plane có thể chứng minh symptom, root cause theo từng request
5. Người làm validation và dashboard có một contract logging ổn định để kiểm tra và trình bày

Nói cách khác, phần của tôi không phải là chức năng “nổi bật” nhất ở giao diện, nhưng là phần móng giúp toàn bộ observability stack của nhóm hoạt động có hệ thống.

## 7. Tự đánh giá cá nhân

Tôi đánh giá phần việc của mình đạt yêu cầu tốt về cả kỹ thuật lẫn tính thực dụng:

- Tôi xử lý đúng gốc của bài toán request tracing bằng `correlation_id` thay vì vá ở từng log riêng lẻ.
- Tôi dùng `contextvars` để giảm lặp, tăng tính nhất quán cho logging.
- Tôi giữ cân bằng giữa khả năng quan sát và an toàn dữ liệu bằng `user_id_hash` cùng cơ chế summarize/scrub.
- Tôi bảo đảm việc bổ sung observability không làm vỡ contract API đang có.

Qua phần việc này, tôi rút ra một điểm quan trọng: observability tốt không chỉ là thêm log cho đủ số lượng, mà là thiết kế request lifecycle sao cho mọi tín hiệu đều có cùng ngữ cảnh và truy ngược được đến cùng một request thực tế.

## 8. Đoạn ngắn để dán vào `blueprint-template.md`

### [MEMBER_C_NAME]
- [TASKS_COMPLETED]: Hoàn thiện `app/middleware.py`, `app/main.py`, `app/schemas.py` cho nền tảng request lifecycle và API logging. Cài đặt `CorrelationIdMiddleware` với `clear_contextvars`, đọc `x-request-id` hoặc tự sinh `req-<8-char-hex>`, bind `correlation_id` vào `structlog contextvars`, gắn `x-request-id` và `x-response-time-ms` vào response headers. Enrich log trong `/chat` với `user_id_hash`, `session_id`, `feature`, `model`, `env` để các log `request_received`, `response_sent`, `request_failed` có đủ context. Rà soát `ChatRequest`, `ChatResponse`, `LogRecord` để giữ đúng contract request-response và logging schema. Đảm bảo `/chat` vẫn trả đủ `answer`, `correlation_id`, `latency_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, đồng thời `/metrics` tiếp tục hoạt động.
- [EVIDENCE_LINK]: `6cd9ab0` (`feat(api): complete request context and correlation id flow`).