# VietHome-AI

Khung dự án nhà thông minh điều khiển bằng giọng nói, hướng tới triển khai trên Raspberry Pi.

## Cấu trúc

- `backend/`: API và logic điều khiển chính bằng FastAPI.
- `frontend/`: giao diện web/client.
- `models/`: nơi đặt model STT, NLU và TTS.
- `hardware/`: sơ đồ đấu nối và cấu hình thiết bị.
- `scripts/`: script cài đặt, cập nhật và chạy trên Raspberry Pi.
- `docs/specs/`: đặc tả tích hợp giao diện.

## Chạy backend local

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements\development.txt
uvicorn app.main:app --app-dir backend --reload
```

Sau đó mở `http://127.0.0.1:8000/docs`.

## Chạy giao diện Web

Yêu cầu Flutter SDK. Giữ backend đang chạy, mở terminal mới:

```powershell
cd frontend
flutter pub get
flutter run -d chrome --web-port 5173
```

Mở `http://localhost:5173`. Địa chỉ backend mặc định là `http://127.0.0.1:8000`; có thể đổi trong phần **Cài đặt** của giao diện.

## Kiểm thử

```powershell
pytest backend\tests
```
