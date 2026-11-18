# VietHome-AI frontend

Giao diện Flutter dùng chung cho Web và ứng dụng di động. STT/TTS và ghi âm chưa được bật trong giai đoạn này.

## Chạy giao diện Web

Mở hai terminal tại thư mục gốc của repository:

```powershell
# Terminal 1: API
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements\development.txt
uvicorn app.main:app --app-dir backend --reload
```

```powershell
# Terminal 2: Flutter Web
cd frontend
flutter pub get
flutter run -d chrome --web-port 5173
```

Mở `http://localhost:5173`. Backend mặc định chạy tại `http://127.0.0.1:8000`; có thể đổi địa chỉ trong **Cài đặt**. Swagger UI nằm tại `http://127.0.0.1:8000/docs`.

Backend hiện trả về thiết bị mock. Chưa có cảm biến thật nên nhiệt độ và độ ẩm được hiển thị là chưa có dữ liệu. Trên điện thoại thật, hãy nhập địa chỉ LAN của máy tính chạy backend thay cho `127.0.0.1`.

## Kiểm tra

```powershell
flutter analyze
flutter test
flutter build web
```

