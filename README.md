# VietHome-AI

Khung dự án nhà thông minh điều khiển bằng giọng nói, hướng tới triển khai trên Raspberry Pi.

## Cấu trúc

- `backend/`: API và logic điều khiển chính bằng FastAPI.
- `frontend/`: giao diện web/client.
- `models/`: nơi đặt model STT, NLU và TTS.
- `hardware/`: sơ đồ đấu nối và cấu hình thiết bị.
- `scripts/`: script cài đặt, cập nhật và chạy trên Raspberry Pi.
- `docs/specs/`: đặc tả tích hợp giao diện.

## Chạy backend và truy cập từ thiết bị khác

### 1. Cài đặt môi trường

Mở PowerShell tại thư mục gốc dự án:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements\development.txt
```

Để chạy thử bộ xử lý câu lệnh AI (RapidFuzz, không cần microphone/model STT):

```powershell
pip install -r backend\requirements\ai.txt
```

Để bật endpoint nhận dạng WAV bằng Faster-Whisper (model `tiny` được tải và cache khi gọi lần đầu):

```powershell
pip install -r backend\requirements\stt.txt
```

### 2. Tạo file cấu hình từ mẫu

Backend đọc cấu hình từ `backend\.env`. Tạo file này từ mẫu:

```powershell
Copy-Item backend\.env.example backend\.env
```

Mở `backend\.env` và kiểm tra các giá trị sau:

```dotenv
HOST=0.0.0.0
PORT=8000
```

`0.0.0.0` cho phép backend nhận kết nối qua các giao diện mạng của máy tính. Không dùng `0.0.0.0` làm địa chỉ để truy cập; thiết bị khác phải dùng IP LAN của máy chạy backend.

### 3. Khởi chạy backend

Từ thư mục gốc dự án, chạy:

```powershell
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

Trên chính máy đó có thể mở `http://127.0.0.1:8000/docs`.

### 4. Truy cập từ thiết bị khác

Đảm bảo hai thiết bị đang cùng mạng Wi-Fi/LAN. Trên máy chạy backend, tìm địa chỉ IPv4 bằng:

```powershell
ipconfig
```

Chọn địa chỉ IPv4 của kết nối Wi-Fi hoặc Ethernet, ví dụ `192.168.1.25`. Trên thiết bị khác, mở:

```text
http://192.168.1.25:8000/docs
```

Thay địa chỉ ví dụ bằng IPv4 thực tế. Nếu Windows Firewall hỏi, cho phép Python/Uvicorn trên mạng Private; nếu cần, mở kết nối TCP đến cổng `8000`. Không nên mở cổng này ra Internet công cộng.

## Chạy giao diện Web

Yêu cầu Flutter SDK. Giữ backend đang chạy, mở terminal mới:

```powershell
cd frontend
flutter pub get
flutter run -d chrome --web-port 5173
```

Mở `http://localhost:5173`. Trong phần **Cài đặt** của giao diện, nhập địa chỉ backend theo IP LAN, ví dụ `http://192.168.1.25:8000`, nếu giao diện cần gọi backend qua mạng.

Lưu ý: backend hiện chỉ cho phép CORS từ `localhost:5173` và `127.0.0.1:5173`. Vì vậy, nếu mở giao diện Flutter trực tiếp từ một thiết bị khác bằng địa chỉ IP LAN của máy chạy giao diện, cần bổ sung origin đó vào cấu hình CORS trong `backend/app/main.py`.

## Chạy backend trên Raspberry Pi

Hướng dẫn này dùng Raspberry Pi OS 64-bit. Raspberry Pi và thiết bị truy cập cần kết nối cùng mạng Wi-Fi/LAN.

Để cài đặt đầy đủ, kiểm thử API/UI, thử STT và xem các cảnh báo trước khi bật GPIO thật, làm theo [hướng dẫn setup và kiểm thử Raspberry Pi](docs/raspberry-pi-setup-testing.md).

### 1. Cài công cụ cần thiết

Mở Terminal trên Raspberry Pi:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

### 2. Tải dự án và cài dependencies

Thay `<URL-repository>` bằng địa chỉ Git repository của dự án:

```bash
git clone <URL-repository> VietHome-AI
cd VietHome-AI

python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements/development.txt
```

### 3. Tạo cấu hình backend

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Đảm bảo file `backend/.env` có các giá trị sau:

```dotenv
HOST=0.0.0.0
PORT=8000
```

Trong `nano`, nhấn `Ctrl+O`, `Enter` để lưu rồi nhấn `Ctrl+X` để thoát.

### 4. Khởi chạy backend

Từ thư mục gốc dự án, khi môi trường ảo đang được kích hoạt, chạy:

```bash
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Giữ Terminal mở để backend tiếp tục chạy. Nhấn `Ctrl+C` để dừng backend.

### 5. Truy cập từ thiết bị khác

Tìm địa chỉ IP của Raspberry Pi:

```bash
hostname -I
```

Từ điện thoại hoặc máy tính cùng mạng, mở địa chỉ dưới đây và thay `IP_RASPBERRY_PI` bằng IP vừa tìm được:

```text
http://IP_RASPBERRY_PI:8000/docs
```

Ví dụ: `http://192.168.1.25:8000/docs`. Trong ứng dụng Flutter, nhập `http://IP_RASPBERRY_PI:8000` ở phần **Cài đặt**. Không dùng `localhost` hoặc `127.0.0.1` trên thiết bị khác, vì các địa chỉ đó trỏ về chính thiết bị đang sử dụng.

Chỉ cho phép truy cập backend trong mạng tin cậy; không mở cổng `8000` trực tiếp ra Internet công cộng.

## Kiểm thử

Xem [hướng dẫn kiểm thử frontend và backend](docs/testing-guide.md) để chạy suite tự động và thử demo text-to-device.

```powershell
pytest backend\tests
```

### English voice-command demo

The backend uses `MockDevice` by default (`MOCK_HARDWARE=true`). Install the AI dependencies above, restart the backend, then preview an English command:

```powershell
$previewBody = [System.Text.Encoding]::UTF8.GetBytes('{"text":"Turn on the living room light"}')
$preview = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/voice/process `
  -ContentType "application/json; charset=utf-8" `
  -Body $previewBody
$preview
```

The preview returns the intent, device, confidence, and `execution_status=needs_confirmation`; it does not control a device. Only send the command again with `execute=true` after user confirmation:

```powershell
$executeBody = [System.Text.Encoding]::UTF8.GetBytes('{"text":"Turn on the living room light","execute":true}')
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/voice/process `
  -ContentType "application/json; charset=utf-8" `
  -Body $executeBody
```

`Turn on the light` is rejected because multiple lights are available; `Don't turn on the light` is rejected due to negation. English is the default STT language and command vocabulary; Vietnamese command aliases remain available for backward compatibility. The current command catalogue is returned by `GET /api/voice/commands`. After installing `stt.txt`, send an English WAV using `Content-Type: audio/wav` to `POST /api/voice/transcribe`; the endpoint returns a transcript and preview without executing it. The `tiny` model is downloaded on first STT use and reused in the process. Wake Word listening is not integrated into the backend service.
