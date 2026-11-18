# Đặc tả: Tích hợp giao diện nhà thông minh cho Web và App

**Ngày tạo**: 2026-11-17  
**Trạng thái**: Draft  
**Đầu vào**: Tích hợp giao diện web và app nhà thông minh hiện có vào dự án VietHome-AI; dùng chung Flutter cho Web và App.

## Phạm vi

- **Cách xác định phạm vi**: Đối chiếu README và giao diện Flutter hiện có với các route, service và thiết bị mock trong backend FastAPI.
- **Tổng số nhóm chức năng được nhận diện**: 6.
- **Nhóm chức năng trong phạm vi**: 6/6 — tổng quan, điều khiển thiết bị, điều khiển giọng nói, lịch sử thao tác, thống kê, và cài đặt kết nối.
- **Mục tiêu**: Đưa giao diện hiện có vào cấu trúc dự án chính, để người dùng có thể sử dụng các luồng chính trên trình duyệt và ứng dụng di động với hành vi nhất quán.
- **Định hướng đã thống nhất**: Dùng một giao diện Flutter cho Web và App, không xây dựng một giao diện web riêng biệt.
- **Ngoài phạm vi**: Triển khai STT/TTS, thu âm hoặc nhận diện lệnh thoại; thay đổi thiết kế nghiệp vụ nhà thông minh; triển khai phần cứng thật; xây dựng hệ thống tài khoản/người dùng; và phát hành ứng dụng lên cửa hàng.

### Giả định và phụ thuộc

- Các luồng giao diện đang có trong ứng dụng nguồn cần được giữ lại, gồm điều khiển thủ công, lịch sử, thống kê và cài đặt máy chủ. Khu vực giọng nói chỉ hiển thị thông báo chưa khả dụng; không ghi âm hoặc gửi lệnh thoại.
- Backend hiện tại là nguồn trạng thái và kết quả điều khiển chính. Giao diện không được hiển thị giá trị mẫu hoặc trạng thái lạc quan như dữ liệu thực đã được xác nhận.
- Backend hiện mới có API liệt kê và bật/tắt thiết bị; chưa có hợp đồng tương ứng cho trạng thái cảm biến, nhận diện giọng nói, hoặc đủ bốn thiết bị mà giao diện nguồn đang hiển thị. Các chức năng này phụ thuộc vào việc bổ sung hoặc thống nhất hợp đồng backend trước khi nghiệm thu.
- Lịch sử thao tác được giữ trong phiên sử dụng hiện tại; lưu trữ bền vững qua lần mở ứng dụng không thuộc phạm vi trừ khi được yêu cầu riêng.
- Trên trình duyệt, chức năng ghi âm phụ thuộc quyền microphone và khả năng hỗ trợ của thiết bị/trình duyệt. Nếu không khả dụng, các chức năng không cần ghi âm vẫn phải hoạt động và giao diện phải thông báo rõ.

## Kịch bản người dùng và kiểm thử

### Câu chuyện 1 — Theo dõi và điều khiển thiết bị (Ưu tiên: P1)

Là người dùng nhà thông minh, tôi muốn xem trạng thái kết nối, cảm biến và thiết bị trên một màn hình tổng quan, đồng thời gửi lệnh bật/tắt hoặc mở/đóng để quản lý ngôi nhà.

**Lý do ưu tiên**: Đây là giá trị cốt lõi của ứng dụng và là luồng cần hoạt động trên cả Web lẫn App.

**Kiểm thử độc lập**: Kết nối giao diện với backend kiểm thử, tải tổng quan, điều khiển một thiết bị, rồi xác nhận trạng thái sau khi backend phản hồi.

**Tình huống chấp nhận**:

1. **Với điều kiện** backend trả về trạng thái thiết bị và cảm biến, **khi** người dùng mở trang tổng quan, **thì** giao diện hiển thị trạng thái và số liệu tương ứng, đồng thời phân biệt rõ trạng thái kết nối.
2. **Với điều kiện** thiết bị có thể điều khiển, **khi** người dùng gửi lệnh bật/tắt hoặc mở/đóng, **thì** giao diện cập nhật theo kết quả được backend xác nhận.
3. **Với điều kiện** backend từ chối lệnh hoặc không phản hồi, **khi** thao tác thất bại, **thì** giao diện không giữ trạng thái thành công giả và thông báo lỗi có thể hiểu được.
4. **Với điều kiện** giao diện đang mở, **khi** có lần làm mới thủ công hoặc đồng bộ định kỳ, **thì** trạng thái hiển thị được cập nhật theo dữ liệu mới nhất nhận được.

### Câu chuyện 2 — Nhận biết trạng thái tính năng giọng nói (Ưu tiên: P3, chỉ placeholder)

Là người dùng, tôi muốn biết tính năng điều khiển giọng nói chưa được bật trong giai đoạn này, để không nhầm nút giao diện với một chức năng đang hoạt động.

**Lý do ưu tiên**: Giữ giao diện rõ ràng trong khi STT/TTS được hoãn sang giai đoạn sau.

**Kiểm thử độc lập**: Mở trang tổng quan và xác minh khu vực giọng nói được đánh dấu chưa khả dụng, không yêu cầu quyền microphone và không gửi yêu cầu nhận diện.

**Tình huống chấp nhận**:

1. **Với điều kiện** người dùng xem trang tổng quan, **khi** khu vực giọng nói được hiển thị, **thì** giao diện nêu rõ tính năng chưa khả dụng vì STT/TTS chưa triển khai.
2. **Với điều kiện** người dùng đang sử dụng Web hoặc App, **khi** trang được mở, **thì** ứng dụng không yêu cầu quyền microphone và không gửi dữ liệu âm thanh hoặc yêu cầu nhận diện.
3. **Với điều kiện** tính năng giọng nói chưa khả dụng, **khi** người dùng dùng các chức năng khác, **thì** các chức năng đó vẫn hoạt động bình thường.

### Câu chuyện 3 — Xem lịch sử và trạng thái thống kê (Ưu tiên: P2)

Là người dùng, tôi muốn xem các thao tác vừa thực hiện và trạng thái tổng hợp để hiểu hoạt động hiện tại của ngôi nhà.

**Lý do ưu tiên**: Hai màn hình này giúp người dùng kiểm tra lại thao tác và quan sát trạng thái mà không phải mở từng thiết bị.

**Kiểm thử độc lập**: Thực hiện thao tác điều khiển và lệnh giọng nói, sau đó mở lịch sử và thống kê để xác minh dữ liệu hiển thị nhất quán với tổng quan.

**Tình huống chấp nhận**:

1. **Với điều kiện** người dùng vừa thực hiện một thao tác thành công, **khi** mở lịch sử, **thì** thao tác được hiển thị với mô tả phù hợp trong phiên hiện tại.
2. **Với điều kiện** có dữ liệu thiết bị mới nhất, **khi** mở thống kê, **thì** số liệu tổng hợp phản ánh cùng trạng thái được hiển thị trên trang tổng quan.
3. **Với điều kiện** chưa có dữ liệu lịch sử hoặc cảm biến, **khi** mở các màn hình tương ứng, **thì** giao diện hiển thị trạng thái trống/chưa có dữ liệu thay vì dữ liệu giả.

### Câu chuyện 4 — Cấu hình kết nối backend (Ưu tiên: P1)

Là người dùng, tôi muốn cấu hình và lưu địa chỉ backend để giao diện Web hoặc App kết nối đúng với máy chủ nhà thông minh.

**Lý do ưu tiên**: Nếu không thể cấu hình đúng đích kết nối, các chức năng theo dõi và điều khiển không sử dụng được trong mạng triển khai.

**Kiểm thử độc lập**: Nhập địa chỉ backend hợp lệ, lưu, tải lại ứng dụng và xác minh địa chỉ được giữ; thử địa chỉ không hợp lệ và máy chủ không phản hồi.

**Tình huống chấp nhận**:

1. **Với điều kiện** địa chỉ máy chủ hợp lệ và máy chủ đang hoạt động, **khi** người dùng lưu cấu hình, **thì** ứng dụng kiểm tra kết nối và hiển thị kết quả.
2. **Với điều kiện** ứng dụng được mở lại, **khi** cấu hình đã lưu tồn tại, **thì** ứng dụng tiếp tục sử dụng địa chỉ đó.
3. **Với điều kiện** địa chỉ sai định dạng hoặc máy chủ không truy cập được, **khi** người dùng lưu, **thì** giao diện nêu rõ lỗi và không báo kết nối thành công.

### Trường hợp biên

- Backend trả về danh sách thiết bị rỗng, thiếu cảm biến, hoặc chứa thiết bị chưa được giao diện nhận biết.
- Backend mất kết nối trong lúc người dùng đang gửi lệnh hoặc ghi âm.
- Phản hồi từ backend sai định dạng, không đầy đủ, hoặc có mã lỗi.
- Người dùng chuyển tab, đóng trang hoặc rời ứng dụng trong lúc đang đồng bộ hay gửi lệnh.
- Người dùng không cấp quyền microphone, thu âm rỗng, hoặc tải âm thanh lên thất bại.
- Trình duyệt chạy từ nguồn không an toàn hoặc chặn quyền microphone; các luồng không phụ thuộc microphone vẫn phải khả dụng.
- Địa chỉ backend hợp lệ về định dạng nhưng không thể truy cập từ thiết bị đang sử dụng.

## Yêu cầu

### Yêu cầu chức năng

- **REQ-001**: Ứng dụng MUST cung cấp các màn hình tổng quan, lịch sử, thống kê và cài đặt kết nối trên cả Web và App.
- **REQ-002**: Giao diện MUST thích ứng với kích thước màn hình trình duyệt và thiết bị di động, không làm mất các chức năng chính khi đổi kích thước hoặc hướng hiển thị.
- **REQ-003**: Trang tổng quan MUST hiển thị trạng thái kết nối, thiết bị và số liệu cảm biến dựa trên dữ liệu backend; dữ liệu không có MUST được biểu thị là chưa có/không khả dụng.
- **REQ-004**: Người dùng MUST có thể gửi lệnh bật/tắt hoặc mở/đóng cho từng thiết bị được cấu hình và xem kết quả được backend xác nhận.
- **REQ-005**: Khi yêu cầu điều khiển thất bại hoặc không xác định được kết quả, giao diện MUST hiển thị lỗi và MUST NOT biểu thị thao tác là thành công.
- **REQ-006**: Ứng dụng MUST cập nhật trạng thái từ backend khi người dùng yêu cầu làm mới và trong quá trình sử dụng; chu kỳ đồng bộ mặc định là 5 giây khi trang tổng quan đang hoạt động.
- **REQ-007**: Ứng dụng MUST cho phép cấu hình, lưu và sử dụng địa chỉ backend; MUST xác thực định dạng địa chỉ và thông báo trạng thái kết nối.
- **REQ-008**: Trong giai đoạn hiện tại, ứng dụng MUST đánh dấu tính năng giọng nói là chưa khả dụng và MUST NOT thu âm, gửi âm thanh hoặc gọi chức năng nhận diện.
- **REQ-009**: Việc trì hoãn STT/TTS MUST NOT ngăn cản người dùng sử dụng các chức năng tổng quan, điều khiển thiết bị, lịch sử, thống kê và cài đặt.
- **REQ-010**: Lịch sử MUST ghi nhận các thao tác thành công được khởi tạo từ giao diện trong phiên hiện tại, bao gồm thao tác thủ công và lệnh thoại đã xử lý.
- **REQ-011**: Màn hình thống kê MUST phản ánh cùng dữ liệu thiết bị/cảm biến mới nhất với trang tổng quan và MUST hiển thị trạng thái rỗng khi chưa có dữ liệu.
- **REQ-012**: Giao diện và backend MUST sử dụng hợp đồng dữ liệu tương thích cho danh sách thiết bị, trạng thái, cảm biến, điều khiển thiết bị và nhận diện lệnh thoại trước khi các chức năng tương ứng được nghiệm thu.
- **REQ-013**: Ứng dụng MUST cung cấp thông báo lỗi dễ hiểu khi mất kết nối, backend từ chối yêu cầu, dữ liệu sai định dạng hoặc thao tác vượt quá thời gian chờ.

### Thực thể chính

- **Thiết bị**: Một thiết bị nhà thông minh có định danh, tên, vị trí/nhóm phòng và trạng thái hiện tại.
- **Số đo cảm biến**: Giá trị môi trường được backend cung cấp, gồm loại số đo, giá trị và thời điểm cập nhật nếu có.
- **Thao tác**: Một yêu cầu điều khiển thiết bị, gồm thiết bị đích, hành động, kết quả và thời điểm thực hiện.
- **Lệnh thoại**: Nội dung lời nói được gửi để nhận diện, văn bản nhận diện và kết quả xử lý.
- **Kết nối máy chủ**: Địa chỉ backend đã cấu hình và trạng thái kết nối hiện tại.

## Tiêu chí thành công

### Kết quả đo lường được

- **SC-001**: Người dùng có thể hoàn thành các luồng xem tổng quan, điều khiển thiết bị, xem lịch sử, xem thống kê và cấu hình kết nối trên cả Web lẫn App.
- **SC-002**: Với backend phản hồi thành công, trạng thái thiết bị mới nhất xuất hiện trên giao diện trong tối đa một chu kỳ đồng bộ (5 giây), không tính thời gian phản hồi của backend.
- **SC-003**: 100% thao tác điều khiển bị backend từ chối hoặc không nhận được xác nhận được hiển thị là thất bại/chưa xác định, không bị báo thành công.
- **SC-004**: Trên Web và App, tính năng giọng nói được ghi rõ là chưa khả dụng; không có quyền microphone nào được yêu cầu và các luồng không liên quan vẫn sử dụng được.
- **SC-005**: Khi không có dữ liệu cảm biến hoặc lịch sử, không màn hình nào hiển thị giá trị mẫu như dữ liệu thực.
- **SC-006**: Các thiết bị được công bố trên giao diện đều có thể được đồng bộ trạng thái và điều khiển qua backend tương ứng; thiết bị không được backend hỗ trợ không được hiển thị như có thể điều khiển.
