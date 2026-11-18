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

## Kiểm thử

```powershell
pytest backend\tests
```
