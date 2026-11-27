# Hướng dẫn kiểm thử VietHome AI

Hướng dẫn này chạy backend với thiết bị giả lập, kiểm tra API điều khiển, Flutter Web và luồng AI text-to-device. Không cần Raspberry Pi hay phần cứng.

## 1. Chuẩn bị môi trường

Từ thư mục gốc repository, dùng PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements\development.txt
pip install -r backend\requirements\ai.txt
Copy-Item backend\.env.example backend\.env
```

Giữ `MOCK_HARDWARE=true` trong `backend\.env`. Muốn thử nhận dạng âm thanh WAV, cài thêm dependencies tùy chọn:

```powershell
pip install -r backend\requirements\stt.txt
```

Faster-Whisper tải model `tiny` vào `models/whisper` khi gọi STT lần đầu; model được cache và tái sử dụng trong process. Không cần cài STT để kiểm thử text command.

## 2. Kiểm thử tự động

Từ thư mục gốc:

```powershell
python -m pytest backend\tests
```

Kiểm thử giao diện:

```powershell
Set-Location frontend
flutter pub get
flutter analyze
flutter test
```

`flutter analyze` có thể báo các diagnostic `info` về import `flutter/material.dart`/`flutter/cupertino.dart` trong code UI hiện có; xem các dòng `error`/`warning` riêng để xác định lỗi chặn build.

## 3. Khởi chạy backend

Tại thư mục gốc, kích hoạt `.venv` rồi chạy:

```powershell
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Mở `http://127.0.0.1:8000/docs` để xem API. Swagger cho phép thử `GET /devices/`, `GET /api/voice/commands` và `POST /api/voice/process`.

## 4. Kiểm thử lệnh text và xác nhận an toàn

### Xem trước lệnh

Lệnh preview mặc định không điều khiển thiết bị:

```powershell
$previewBody = [System.Text.Encoding]::UTF8.GetBytes('{"text":"Bật đèn phòng khách"}')
$preview = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/voice/process `
  -ContentType "application/json; charset=utf-8" `
  -Body $previewBody
$preview | ConvertTo-Json -Depth 5
```

Kết quả mong đợi:

- `intent`: `LIGHT_ON`
- `device_id`: `light`
- `action`: `turn_on`
- `accepted`: `true`
- `execution_status`: `needs_confirmation`

Xác minh trạng thái thiết bị chưa đổi:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/devices/
```

### Xác nhận thực thi

Chỉ gửi `execute=true` sau khi người dùng đã xem preview và xác nhận:

```powershell
$executeBody = [System.Text.Encoding]::UTF8.GetBytes('{"text":"Bật đèn phòng khách","execute":true}')
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/voice/process `
  -ContentType "application/json; charset=utf-8" `
  -Body $executeBody |
  ConvertTo-Json -Depth 5
```

Kết quả mong đợi: `execution_status=succeeded`, `execution.success=true`; trạng thái `light` trong `GET /devices/` là `is_on=true`.

### Các trường hợp validation

Thử từng nội dung sau với `"execute":true`; các lệnh bị từ chối không được đổi trạng thái thiết bị:

| Câu lệnh | Kết quả mong đợi |
|---|---|
| `Turn off the bedroom fan` | `FAN_OFF`, device `fan` |
| `Turn on the light` | `AMBIGUOUS_TARGET` |
| `Don't turn on the light` | `NEGATION_DETECTED` |
| `Turn on the living room light or turn it off` | `AMBIGUOUS_COMMAND` |
| `Turn on the kitchen light` | `TARGET_NOT_FOUND` |

`execute` mặc định là `false`. Lệnh phủ định, mơ hồ hoặc không tìm được thiết bị phải luôn bị từ chối.

## 5. Kiểm thử STT WAV (tùy chọn)

Sau khi cài `backend\requirements\stt.txt`, gửi WAV có lời nói tiếng Anh (tối đa 10 MB):

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/voice/transcribe `
  -ContentType "audio/wav" `
  -InFile .\command.wav |
  ConvertTo-Json -Depth 6
```

Endpoint trả về transcript và bản preview của text command. STT không tự thực thi lệnh; cần gửi kết quả qua luồng preview/xác nhận. Kiểm thử tự động dùng model giả để không tải model, không cần microphone và không tác động thiết bị.

### Kiểm tra Wake Word từ file âm thanh

Script `wake_word_test.py` mặc định nghe microphone. Để kiểm tra file offline (không mở microphone, không thực thi thiết bị), từ thư mục gốc repository chạy:

```powershell
python backend\app\ai\speech\wake_word_test.py --file "recordings\turn light on .wav"
```

Script in transcript và `Detected`/`Not detected` cho các biến thể đang khai báo trong `WAKE_WORDS`. Faster-Whisper giải mã file và tự xử lý sample rate; model `tiny` cần tải ở lần đầu và được cache trong `models/whisper`. File cần chứa cụm wake word được cấu hình (mặc định `hey berry` và các biến thể). Chế độ này nhận dạng toàn bộ file thành một lần, khác với vòng nghe microphone xử lý từng cửa sổ ba giây.

## 6. Chạy và kiểm thử Flutter Web

Giữ backend đang chạy, mở terminal PowerShell khác:

```powershell
Set-Location frontend
flutter pub get
flutter run -d chrome --web-port 5173
```

Mở `http://localhost:5173`, vào **Cài đặt** và đặt backend URL là `http://127.0.0.1:8000` nếu chưa kết nối. Trên màn hình dashboard:

1. Nhập `Turn on the living room light`, nhấn **Phân tích lệnh**.
2. Xác minh intent, action, thiết bị và độ khớp xuất hiện; trạng thái thiết bị chưa thay đổi.
3. Nhấn **Xác nhận thực thi**, rồi **Thực thi** trong hộp thoại.
4. Xác minh giao diện cập nhật trạng thái đèn.
5. Thử `Turn on the light`, `Don't turn on the light` và bảo đảm giao diện hiện lý do từ chối, không thực thi.

Trên thiết bị khác trong LAN, thay `127.0.0.1` bằng IP máy chạy backend. Không mở backend ra Internet công cộng.
