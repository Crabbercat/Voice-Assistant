# VietHome AI - hướng dẫn demo toàn hệ thống

Tài liệu này hướng dẫn chạy frontend, backend, xử lý lệnh text, nhận dạng WAV và luồng microphone `Wake Word -> STT -> CommandProcessor -> DeviceService`. Các bước mặc định sử dụng `MockDevice`, không cần đấu thiết bị thật.

> **An toàn:** Giữ `MOCK_HARDWARE=true`. Voice listener mặc định không tự thực thi lệnh. Chỉ bật `VOICE_AUTO_EXECUTE=true` khi cần demo xử lý giọng nói end-to-end và vẫn giữ mock hardware; không dùng chế độ tự thực thi với GPIO thật.

## 1. Cài đặt backend

Từ thư mục gốc repository, tạo virtual environment và cài dependencies:

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements\development.txt
python -m pip install -r backend\requirements\ai.txt
python -m pip install -r backend\requirements\stt.txt
python -m pip install -r backend\requirements\voice.txt
python -m pip install -r backend\requirements\tts.txt
Copy-Item backend\.env.example backend\.env
```

### Raspberry Pi OS / Linux

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip libportaudio2 portaudio19-dev espeak-ng
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements/development.txt
python -m pip install -r backend/requirements/ai.txt
python -m pip install -r backend/requirements/stt.txt
python -m pip install -r backend/requirements/voice.txt
python -m pip install -r backend/requirements/tts.txt
cp backend/.env.example backend/.env
```

`stt.txt` cung cấp Faster-Whisper; `voice.txt` cung cấp thư viện microphone, resampling và phát WAV qua PortAudio; `tts.txt` cung cấp adapter TTS cục bộ. Nếu chỉ thử text command, chỉ cần `development.txt` và `ai.txt`. Model `tiny` tải về ở lần đầu gọi STT hoặc khởi động listener; model được nạp một lần và tái sử dụng cho các lần nhận dạng tiếp theo.

## 2. Cấu hình demo an toàn

Mở `backend/.env`, xác nhận các giá trị sau:

```dotenv
HOST=0.0.0.0
PORT=8000
MOCK_HARDWARE=true
STT_MODEL=tiny
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
STT_LANGUAGE=en
AUDIO_SAMPLE_RATE=16000
AUDIO_SILENCE_THRESHOLD=0.005
WAKE_WORDS=hey berry,hey barry,hey beri,hey very,hey be ri
VOICE_ENABLED=true
VOICE_AUTO_START=false
VOICE_AUTO_EXECUTE=false
VOICE_RESPONSE_ENABLED=true
VOICE_PLAYBACK_MODE=server
VOICE_TTS_ENABLED=true
VOICE_TTS_LANGUAGE=vi-VN
VOICE_SENSOR_MAX_AGE_SECONDS=15
```

`VOICE_ENABLED=true` cho phép gọi API mở microphone; listener không tự mở mic khi import backend. `VOICE_AUTO_START=false` yêu cầu khởi động listener tường minh qua API. Để dùng microphone ngoài thiết bị mặc định, đặt `AUDIO_INPUT_DEVICE` thành tên hoặc chỉ số input device có trong danh sách của `sounddevice`.

`VOICE_RESPONSE_ENABLED=true` bật phần phản hồi âm thanh. Backend Raspberry Pi phát âm thanh qua loa; frontend chỉ hiển thị lời phản hồi và trạng thái phát để tránh phát lặp. `VOICE_TTS_VOICE` để trống cho phép tự chọn voice tiếng Việt tương thích.

## 3. Khởi chạy backend và frontend

Tại thư mục gốc:

```powershell
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Kiểm tra `http://127.0.0.1:8000/health` và mở Swagger tại `http://127.0.0.1:8000/docs`.

Trong terminal PowerShell khác:

```powershell
Set-Location frontend
flutter pub get
flutter run -d chrome --web-port 5173
```

Mở dashboard, vào **Cài đặt** và cấu hình URL backend. Nếu frontend chạy trên máy khác, dùng IP LAN của máy chạy backend thay cho `127.0.0.1`. Giao diện hiện có hỗ trợ nhập text, xem kết quả phân tích và xác nhận trước khi thực thi; listener microphone được quản lý qua API bên dưới.

## 4. Demo text-to-device

Gửi lệnh tiếng Anh:

```powershell
$body = [System.Text.Encoding]::UTF8.GetBytes('{"text":"Turn on the living room light"}')
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/voice/process `
  -ContentType "application/json; charset=utf-8" `
  -Body $body | ConvertTo-Json -Depth 6
```

Kết quả preview mong đợi:

- `intent`: `LIGHT_ON`
- `device_id`: `light`
- `action`: `turn_on`
- `accepted`: `true`
- `execution_status`: `needs_confirmation`

Preview không thay đổi thiết bị. Sau khi xác nhận, gửi cùng lệnh với `execute=true`:

```powershell
$body = [System.Text.Encoding]::UTF8.GetBytes(
  '{"text":"Turn on the living room light","execute":true}'
)
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/voice/process `
  -ContentType "application/json; charset=utf-8" `
  -Body $body | ConvertTo-Json -Depth 6
```

Với mock hardware, kết quả thành công có `execution_status=succeeded` và `execution.success=true`. Kiểm tra trạng thái tại `GET /devices/`.

Các câu sau cần được xử lý an toàn:

| Câu thử | Kết quả mong đợi |
|---|---|
| `Turn off the bedroom fan` | Nhận diện `FAN_OFF` và đúng thiết bị |
| `Turn on the light` | Từ chối nếu có nhiều đèn, do không rõ vị trí |
| `Don't turn on the light` | Từ chối `NEGATION_DETECTED` |
| `Turn on the living room light or turn it off` | Từ chối lệnh mâu thuẫn/mơ hồ |
| `Turn on the kitchen light` | Từ chối nếu target không có trong registry |

## 5. Demo STT bằng tệp WAV (tùy chọn)

Gửi WAV mono có lời nói tiếng Anh, tối đa 10 MB:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/voice/transcribe `
  -ContentType "audio/wav" `
  -InFile .\command.wav | ConvertTo-Json -Depth 6
```

Response chứa transcript và kết quả preview từ bộ xử lý lệnh. Endpoint này **không thực thi** thiết bị. WAV sai định dạng trả 400, sai content type trả 415, quá 10 MB trả 413. Lỗi thiếu dependency hoặc không tải/nhận dạng được model trả lỗi dịch vụ 503.

## 6. Demo microphone: Wake Word đến DeviceService

### Kiểm tra microphone

Trên Raspberry Pi:

```bash
arecord -l
source .venv/bin/activate
python -c "import sounddevice as sd; print(sd.query_devices()); print('Default input:', sd.query_devices(kind='input'))"
```

Phải có ít nhất một thiết bị input. Cắm mic trước khi khởi động listener. Nếu có nhiều thiết bị, đặt `AUDIO_INPUT_DEVICE` trong `backend/.env` thành tên hoặc số index. Không cần tạo tệp ghi âm.

### Khởi động listener

Đảm bảo backend đã được khởi động lại sau khi sửa `.env`. Gửi các request sau:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/voice/status
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/voice/start
Invoke-RestMethod http://127.0.0.1:8000/api/voice/status
```

Lần đầu `start` có thể mất thời gian tải model `tiny`. Khi sẵn sàng, status có `running=true`, `state=WAITING_WAKE_WORD`, `microphone_available=true` và tên microphone. Nếu nhận 409, kiểm tra `VOICE_ENABLED=true`; nếu nhận 503, xem `last_error`, thiết bị input và log backend.

Nói rõ **“Hey Berry”**, chờ khoảng một nhịp, rồi nói **“Turn on the living room light”** bằng tiếng Anh. Im lặng khoảng 1–2 giây để kết thúc lệnh. Listener chuyển qua trạng thái nghe câu lệnh, nhận dạng, xác thực lệnh rồi ghi kết quả vào history:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/voice/history?limit=10" |
  ConvertTo-Json -Depth 6
```

Mặc định `VOICE_AUTO_EXECUTE=false`: lệnh hợp lệ chỉ có `execution_status=needs_confirmation`, không điều khiển thiết bị. Có thể sao chép transcript để preview/xác nhận qua luồng text ở mục 4.

Để demo trọn luồng giọng nói đến `DeviceService`, chỉ khi `MOCK_HARDWARE=true`, đặt tạm:

```dotenv
VOICE_AUTO_EXECUTE=true
```

Khởi động lại backend, gọi `/api/voice/start` nếu listener chưa chạy, rồi nói lại câu lệnh. Lệnh hợp lệ sẽ gọi `DeviceService` hiện có; lệnh phủ định, mơ hồ hoặc không tìm thấy thiết bị vẫn bị từ chối. Sau demo, nên đặt lại `VOICE_AUTO_EXECUTE=false`.

Dừng listener khi không dùng:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/voice/stop
```

Các endpoint microphone:

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/api/voice/status` | Trạng thái listener, model, microphone và lỗi cuối |
| `POST` | `/api/voice/start` | Nạp model và mở listener |
| `POST` | `/api/voice/stop` | Dừng listener, đóng microphone, giải phóng model |
| `GET` | `/api/voice/history?limit=20` | Xem tối đa 100 kết quả xử lý gần nhất |

## 7. Kiểm thử phản hồi giọng nói và TTS

Kiểm tra tình trạng provider và các static response key đã đăng ký:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/voice/response/status |
  ConvertTo-Json -Depth 5
```

Để phát thử một clip đã ghi âm:

```powershell
Invoke-RestMethod -Method Post `
  http://127.0.0.1:8000/api/voice/response/play/lights.turned_on |
  ConvertTo-Json -Depth 5
```

Các WAV thật phải được đặt đúng thư mục và đường dẫn khai báo trong `backend/app/ai/tts/assets/manifest.json`, ở dưới `backend/app/ai/tts/assets/static/`. Mỗi file cần là WAV mono, PCM signed 16-bit, 16 kHz. Repository chưa kèm các file ghi âm; khi thiếu file, API trả `audio_played=false` và `status=unavailable` có nêu nguyên nhân, không tạo audio giả. Có thể dùng endpoint status để xem thiết bị phát âm thanh có sẵn hay không.

Yêu cầu đọc dữ liệu cảm biến bằng TTS:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/voice/response/sensors/temperature
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/voice/response/sensors/humidity
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/voice/response/sensors/summary
```

Kết quả thành công cần có `response_mode=tts`, giá trị trong `data`, câu tiếng Việt trong `text`, và `audio_played=true`. Đọc `tts_available` tại endpoint status trước khi thử; hệ điều hành phải có voice tiếng Việt. Cài `backend/requirements/tts.txt` và trên Raspberry Pi cài `espeak-ng`; nếu không có voice Việt hoặc sensor chưa có dữ liệu mới, API trả trạng thái unavailable/stale thay vì dùng voice tiếng Anh hay dữ liệu cũ.

Dashboard hiện có nút **Nói nhiệt độ**, **Nói độ ẩm**, **Đọc cả hai**, **Bật tất cả** và **Tắt tất cả**. Các lệnh thiết bị đơn và bulk đều dùng `DeviceService` hiện tại; khi thao tác thất bại/partial, kết quả nêu rõ trạng thái thay vì thông báo thành công toàn phần.

## 8. Kiểm thử tự động

Từ thư mục gốc, chạy:

```powershell
python -m pytest backend\tests
```

Các test voice listener dùng capture, recognizer và DeviceService giả; không cần microphone, không tải model, không gọi GPIO. Hướng dẫn kiểm thử Raspberry Pi chi tiết và chẩn đoán microphone nằm tại [raspberry-pi-setup-testing.md](./raspberry-pi-setup-testing.md).

## 9. Giới hạn demo

- Voice listener chạy trong một process backend duy nhất; không chạy nhiều Uvicorn workers.
- Microphone được chọn theo `AUDIO_INPUT_DEVICE` hoặc input mặc định của hệ điều hành.
- Wake Word được nhận dạng bằng STT trên cửa sổ âm thanh, không phải mô hình wake-word chuyên dụng.
- Repository chưa cung cấp WAV ghi âm thật; static playback chỉ phát thành công sau khi thêm các clip đúng manifest. TTS động cần cài local voice tiếng Việt tương thích và thiết bị phát âm thanh trên backend.
- Frontend hiện chưa có nút start/stop microphone; dùng API hoặc Swagger để quản lý listener.
- Luồng giọng nói tự thực thi chỉ nên demo với mock hardware. Không bật `VOICE_AUTO_EXECUTE` khi dùng thiết bị GPIO thật.
- Chưa xác nhận thời gian tải, mức RAM và hiệu năng model trên Raspberry Pi cụ thể; lần đầu cần mạng để tải model.
