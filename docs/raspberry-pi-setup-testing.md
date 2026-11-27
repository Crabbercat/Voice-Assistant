# Cài đặt VietHome AI đầy đủ trên Raspberry Pi và kiểm thử chức năng

Hướng dẫn này triển khai FastAPI trên Raspberry Pi OS 64-bit / Debian 12, Python 3.11, cùng mạng LAN với thiết bị mở giao diện Flutter Web. Các bước kiểm thử mặc định dùng `MockDevice`, không cần đấu phần cứng.

> **Cảnh báo phần cứng:** repository hiện chưa có sơ đồ đấu dây hoàn chỉnh trong `hardware/wiring/README.md`. Không đổi `MOCK_HARDWARE=false` và không nối thiết bị thật trước khi người triển khai xác minh sơ đồ, nguồn cấp, mức điện áp và chân GPIO thực tế. GPIO của Pi là 3.3 V; không cấp nguồn tải (motor/servo) trực tiếp từ chân GPIO.

## 1. Kiến trúc demo

- Raspberry Pi chạy FastAPI và là máy chủ API.
- Trình duyệt trên máy tính/điện thoại trong cùng mạng LAN mở Flutter Web.
- Lệnh text được chuẩn hóa, nhận diện bằng RapidFuzz và xác thực trước khi hiển thị kết quả.
- Chỉ sau khi người dùng xác nhận, backend mới gọi `DeviceService` và registry hiện có.
- `MOCK_HARDWARE=true` là chế độ mặc định, không tác động GPIO.
- Endpoint STT nhận tệp WAV. Có script kiểm thử microphone/Wake Word độc lập; script này không phải microphone listener của backend và không điều khiển thiết bị.

## 2. Chuẩn bị Raspberry Pi

Khuyến nghị Raspberry Pi 4 (RAM 4 GB trở lên), Raspberry Pi OS 64-bit, kết nối mạng ổn định và nguồn điện phù hợp.

### Cập nhật hệ điều hành và cài công cụ

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y git python3 python3-venv python3-pip python3-dev build-essential
```

Khởi động lại nếu hệ điều hành yêu cầu:

```bash
sudo reboot
```

Sau khi đăng nhập lại, xác nhận hệ điều hành và Python:

```bash
uname -m
python3 --version
```

Kết quả phần cứng thường là `aarch64`; Python 3.11 được khuyến nghị cho cấu hình hiện tại.

## 3. Lấy mã nguồn và cài backend

Thay `<URL_REPOSITORY>` bằng địa chỉ clone repository:

```bash
git clone <URL_REPOSITORY> VietHome-AI
cd VietHome-AI
```

Tạo virtual environment và cài bộ backend, test và RapidFuzz:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements/development.txt
python -m pip install -r backend/requirements/ai.txt
```

Nếu chỉ muốn chạy demo text-to-device, các bước này là đủ. Không cần cài Faster-Whisper hoặc microphone.

### Cài STT tùy chọn

```bash
python -m pip install -r backend/requirements/stt.txt
```

Model `tiny` được tải vào `models/whisper` khi gọi STT lần đầu, sau đó được giữ trong cache và model instance được tái sử dụng trong process backend. Lần đầu cần Internet và có thể mất thời gian; nên thử trước trên Pi và theo dõi dung lượng trống/RAM.

STT qua API nhận tệp WAV mono/âm thanh do Faster-Whisper giải mã tại `POST /api/voice/transcribe`, giới hạn 10 MB. API trả transcript cùng preview lệnh, không tự thực thi. Kiểm thử microphone trực tiếp được mô tả ở mục 10; backend không tự mở microphone hoặc chạy Wake Word.

## 4. Cấu hình demo an toàn

Tạo file môi trường:

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Giữ các giá trị phù hợp cho lần chạy đầu:

```dotenv
HOST=0.0.0.0
PORT=8000
MOCK_HARDWARE=true
COMMAND_SIMILARITY_THRESHOLD=80
STT_MODEL=tiny
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
STT_LANGUAGE=en
STT_BEAM_SIZE=1
STT_MODEL_CACHE_DIR=models/whisper
```

`MOCK_HARDWARE=true` phải được giữ trong quá trình kiểm tra API/UI ban đầu. Chỉ mở quyền truy cập cổng 8000 trong mạng tin cậy; không forward cổng này trực tiếp ra Internet.
Nếu đã có `backend/.env` từ lần cài trước, hãy đổi `STT_LANGUAGE=vi` thành `STT_LANGUAGE=en`; file `.env` hiện có sẽ được ưu tiên hơn `.env.example`.

## 5. Chạy backend

Từ thư mục gốc repository, với virtual environment đã kích hoạt:

```bash
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Chạy một Uvicorn worker duy nhất. Không dùng nhiều worker cho một instance thiết bị; registry và trạng thái mock nằm trong bộ nhớ của process.

Tìm địa chỉ LAN của Pi:

```bash
hostname -I
```

Từ chính Pi, kiểm tra:

```bash
curl -fsS http://127.0.0.1:8000/health/
curl -fsS http://127.0.0.1:8000/devices/
curl -fsS http://127.0.0.1:8000/dashboard/
curl -fsS http://127.0.0.1:8000/api/voice/commands
```

Mở Swagger UI trên Pi hoặc thiết bị cùng mạng tại:

```text
http://IP_RASPBERRY_PI:8000/docs
```

Thay `IP_RASPBERRY_PI` bằng địa chỉ LAN thực tế, ví dụ `192.168.1.25`.

## 6. Kiểm thử tự động backend trên Pi

Mở terminal thứ hai, vào thư mục repository và kích hoạt cùng virtual environment:

```bash
cd VietHome-AI
source .venv/bin/activate
python -m pytest backend/tests
```

Các bài test dùng thiết bị mock và không cần microphone, model STT hay phần cứng. Kết quả mong đợi là toàn bộ test pass.

## 7. Kiểm thử lệnh text qua API

### Preview không thực thi

Lệnh sau chỉ phân tích câu, tuyệt đối không đổi trạng thái thiết bị:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/voice/process \
  -H 'Content-Type: application/json' \
  --data-raw '{"text":"Turn on the living room light"}'
```

Kiểm tra phản hồi có:

- `accepted: true`
- `intent: "LIGHT_ON"`
- `action: "turn_on"`
- `device_id: "light"`
- `execution_status: "needs_confirmation"`

Gọi lại danh sách thiết bị để xác minh `light.is_on` chưa đổi:

```bash
curl -sS http://127.0.0.1:8000/devices/
```

### Xác nhận mới thực thi

Chỉ gửi yêu cầu này sau khi người dùng đã xác nhận preview:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/voice/process \
  -H 'Content-Type: application/json' \
  --data-raw '{"text":"Turn on the living room light","execute":true}'
```

Kết quả mong đợi: `execution_status: "succeeded"` và `execution.success: true`. Gọi `GET /devices/` để xác nhận trạng thái mock của `light` đã bật. Tắt lại thiết bị sau bài thử:

```bash
curl -sS -X POST http://127.0.0.1:8000/devices/light/state \
  -H 'Content-Type: application/json' \
  --data-raw '{"is_on":false}'
```

### Ma trận validation

Chạy mỗi câu với `execute:true`. Lệnh bị từ chối không được thực thi:

| Câu lệnh                                       | Kết quả dự kiến               |
| ------------------------------------------------ | --------------------------------- |
| `Turn off the bedroom fan`                     | `FAN_OFF`, `device_id: "fan"` |
| `Turn on the light`                            | `AMBIGUOUS_TARGET`              |
| `Don't turn on the light`                      | `NEGATION_DETECTED`             |
| `Turn on the living room light or turn it off` | `AMBIGUOUS_COMMAND`             |
| `Turn on the kitchen light`                    | `TARGET_NOT_FOUND`              |

Ví dụ kiểm tra phủ định:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/voice/process \
  -H 'Content-Type: application/json' \
  --data-raw '{"text":"Do not turn on the light","execute":true}'
```

Sau các lệnh bị từ chối, kiểm tra lại `/devices/` để chắc trạng thái thiết bị không bị thay đổi.

## 8. Chạy và kiểm thử Flutter Web

Có thể chạy Flutter Web trên máy phát triển thay vì cài Flutter SDK lên Pi. Cài Flutter SDK trên máy đó, rồi trong terminal:

```bash
cd frontend
flutter pub get
flutter run -d chrome --web-port 5173
```

Mở `http://localhost:5173`. Trong mục **Cài đặt**, nhập URL backend:

```text
http://IP_RASPBERRY_PI:8000
```

Không nhập `localhost` hoặc `127.0.0.1` làm địa chỉ backend khi trình duyệt chạy ở máy khác; các địa chỉ đó sẽ trỏ về chính máy khách.

Kiểm tra trên dashboard:

1. Trạng thái server hiển thị Online và danh sách bốn thiết bị tải được.
2. Công tắc có thể bật/tắt thiết bị mock; trạng thái được làm mới từ backend.
3. Nhập `Turn on the living room light`, nhấn **Phân tích lệnh**.
4. Kiểm tra intent/thiết bị/độ khớp xuất hiện nhưng thiết bị chưa đổi trạng thái.
5. Nhấn **Xác nhận thực thi**, xác nhận tiếp trong hộp thoại; thiết bị mới đổi trạng thái.
6. Thử `Turn on the light` và `Don't turn on the light`; giao diện hiển thị lý do từ chối, thiết bị không đổi trạng thái.

Nếu giao diện được mở từ một origin web khác, trình duyệt có thể chặn request do CORS. Backend hiện chỉ cho phép `http://localhost:5173` và `http://127.0.0.1:5173`. Khi đó chạy frontend ở một trong các origin được phép hoặc chủ động cập nhật danh sách CORS để thêm đúng origin tin cậy; không mở CORS cho mọi origin khi backend điều khiển thiết bị.

## 9. Kiểm thử STT bằng WAV qua API (tùy chọn)

Từ một máy đã cài `backend/requirements/stt.txt`, gửi một WAV có lời nói tiếng Anh, kích thước tối đa 10 MB:

```bash
curl -sS -X POST http://IP_RASPBERRY_PI:8000/api/voice/transcribe \
  -H 'Content-Type: audio/wav' \
  --data-binary @command.wav
```

Phản hồi cần có `recognized_text`, ngôn ngữ và `command`. STT chỉ sinh preview; nó không thực thi thiết bị. Kiểm tra transcript trước, sau đó dùng luồng xác nhận text-to-device nếu đó là lệnh hỗ trợ.

Để chẩn đoán STT:

- WAV không hợp lệ hoặc sai `Content-Type` trả lỗi 400/415.
- Tệp lớn hơn 10 MB trả lỗi 413.
- Thiếu Faster-Whisper trả lỗi dịch vụ chưa sẵn sàng; cài `stt.txt`.
- Lỗi model/tải xuống trả lỗi 503; kiểm tra kết nối Internet, cache `models/whisper` và log backend.
- Đánh giá transcript bằng nhiều câu tiếng Anh trong môi trường yên tĩnh. Không xem một WAV thử nghiệm là đo chính xác độ chính xác thực tế.

## 10. Kiểm thử microphone trực tiếp (script độc lập)

Phần này mở microphone trên Raspberry Pi để thử Wake Word và STT mà không cần tạo file ghi âm. Script chỉ in kết quả nhận dạng ra terminal; nó **không gửi lệnh tới API, không gọi `DeviceService` và không điều khiển thiết bị**. Giữ `MOCK_HARDWARE=true`.

### Kiểm tra thiết bị thu âm

Trước tiên cắm microphone USB hoặc USB sound card có đầu vào microphone, rồi kiểm tra ALSA:

```bash
arecord -l
```

Phải có ít nhất một thiết bị capture. Nếu danh sách trống, Pi chưa nhận thiết bị thu âm: thử cổng USB khác, kiểm tra microphone/sound card hoặc dùng một microphone tương thích. Cài Python package sẽ không tạo ra thiết bị capture nếu phần cứng chưa được nhận diện.

### Cài thư viện và xác nhận microphone

Trong thư mục gốc repository, cài PortAudio và các package Python vào virtual environment:

```bash
sudo apt update
sudo apt install -y libportaudio2 portaudio19-dev
source .venv/bin/activate
python -m pip install sounddevice scipy numpy
```

Cài Faster-Whisper nếu chưa cài STT:

```bash
python -m pip install -r backend/requirements/stt.txt
```

Liệt kê microphone mặc định mà `sounddevice` nhìn thấy:

```bash
python -c "import sounddevice as sd; print(sd.query_devices()); print('Default input:', sd.query_devices(kind='input'))"
```

Nếu lệnh báo không có input device, quay lại kiểm tra `arecord -l`, quyền truy cập thiết bị và kết nối microphone trước khi chạy nhận dạng.

### Chạy thử Wake Word và câu lệnh

Từ thư mục gốc repository, khi virtual environment đã kích hoạt:

```bash
python backend/app/ai/speech/wake_word_test.py
```

Lần đầu Faster-Whisper có thể tải model `base` vào `models/whisper`; cần kết nối Internet và đủ dung lượng trống. Sau khi hiện tên microphone và dòng `Waiting for 'Hey Berry'`, nói rõ **“Hey Berry”** bằng tiếng Anh. Khi script nhận wake word, giữ im lặng khoảng một giây để microphone đo nhiễu nền. Chỉ nói câu lệnh tiếng Anh, ví dụ **“Turn on the living room light”**, sau khi hiện `[COMMAND] Say an English command...`; rồi im lặng khoảng 1–2 giây để kết thúc câu. Nhấn `Ctrl+C` để dừng.

Kiểm tra kết quả trong terminal:

1. `[AUDIO] Microphone` hiển thị đúng thiết bị và sample rate.
2. Các dòng `[RECOGNIZED]` hiển thị RMS và transcript. RMS gần 0 hoặc transcript rỗng thường là microphone bị mute, gain quá thấp, sai input device hoặc không có tiếng nói trong lúc lấy mẫu.
3. `[WAKE WORD] Hey Berry detected!` xác nhận wake phrase được nhận dạng.
4. Sau hiệu chỉnh, `[AUDIO]` in nhiễu nền và ngưỡng RMS. `[LEVEL]` cho biết tín hiệu các đoạn chờ; `[RECORDING] Voice detected` xác nhận đã bắt đầu thu câu lệnh.
5. Phần `RESULT` hiển thị câu lệnh đã nhận dạng và thời gian xử lý.

Script giữ âm thanh từng đoạn trong bộ nhớ để nhận dạng, không ghi WAV ra đĩa. Đây chỉ là bài kiểm tra microphone/STT độc lập; kết quả không thực thi lệnh trên thiết bị. Muốn thử thực thi, nhập câu lệnh vào luồng preview/xác nhận của frontend hoặc API như mục 7.

## 11. Cấu hình phần cứng thật — chỉ sau khi đối chiếu dây

Registry hiện tại có các thiết bị cố định trong code, không đọc `hardware/configs/devices.example.json` để tự cấu hình GPIO. Những chân hiện được dùng khi `MOCK_HARDWARE=false`:

| Thiết bị                              | ID API        |            GPIO theo code |
| --------------------------------------- | ------------- | ------------------------: |
| Đèn phòng khách                     | `light`     |                    BCM 18 |
| Đèn ngủ                              | `light_bed` |                    BCM 22 |
| Quạt L298N                             | `fan`       | BCM 23, 24 và PWM BCM 25 |
| Servo cửa                              | `door`      |                    BCM 27 |
| DHT11 (nếu driver cảm biến có sẵn) | —            |                     BCM 4 |

Các số trên là BCM GPIO numbers suy ra từ mã nguồn, không phải xác nhận sơ đồ dây. Tài liệu đấu nối trong repository hiện chưa mô tả kết nối thực tế. Trước khi bật GPIO:

1. Đối chiếu từng dây với sơ đồ mạch đã được người triển khai xác minh; kiểm tra nguồn/ground chung và driver phù hợp cho motor/servo.
2. Cài và kiểm tra GPIO stack tương thích với phiên bản Raspberry Pi OS; `gpiozero` được import bởi driver quạt/đèn/cửa, còn `backend/requirements/raspberry-pi.txt` hiện chỉ khai báo `RPi.GPIO`. File requirements Pi hiện chưa bao gồm đầy đủ GPIO driver đang dùng; không coi việc cài file đó là xác nhận GPIO hoạt động.
3. Kiểm tra thiết bị không chuyển động ngoài ý muốn khi cấp nguồn; giữ mock bật cho đến khi sẵn sàng và có người giám sát.
4. Chỉ khi đã kiểm chứng phần cứng mới đặt `MOCK_HARDWARE=false`, khởi động lại backend và thử từng thiết bị ở trạng thái không tải/nguy cơ thấp.
5. Dừng backend bằng `Ctrl+C` nếu thấy chuyển động sai hoặc lỗi GPIO; không lặp lệnh điều khiển khi trạng thái vật lý chưa rõ.

Khi mock đang bật, `GET /devices/` và nút bấm chứng minh đường API/service hoạt động, nhưng không chứng minh dây, driver hay thiết bị vật lý hoạt động.

## 12. Chạy backend tự khởi động bằng systemd (tùy chọn)

Đầu tiên xác minh chạy backend thủ công thành công. Sau đó tạo unit:

```bash
sudo nano /etc/systemd/system/viethome-ai.service
```

Nội dung mẫu (thay `pi` nếu tài khoản khác):

```ini
[Unit]
Description=VietHome AI FastAPI backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/VietHome-AI
EnvironmentFile=/home/pi/VietHome-AI/backend/.env
ExecStart=/home/pi/VietHome-AI/.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Tải cấu hình và kiểm tra:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now viethome-ai
sudo systemctl status viethome-ai --no-pager
sudo journalctl -u viethome-ai -n 100 --no-pager
```

Không cấu hình nhiều Uvicorn workers. Nếu chuyển sang GPIO thật, trước tiên dừng service, xác minh tài khoản service có quyền truy cập GPIO theo cách an toàn cho OS và kiểm tra đầy đủ từng mạch.

## 13. Giới hạn hiện tại cần biết

- Backend chưa có microphone listener nền hoặc Wake Word; script ở mục 10 chỉ dùng để kiểm thử trực tiếp và không tích hợp DeviceService.
- Endpoint STT nhận WAV upload; script microphone độc lập không gửi transcript đến API.
- Model STT tải lần đầu cần mạng; chưa kiểm thử benchmark CPU/RAM/thời gian trên Raspberry Pi.
- Driver cảm biến DHT11 được import tùy điều kiện và không có trong bộ requirements cơ bản; nhiệt độ/độ ẩm có thể hiển thị `—`.
- Cấu hình thiết bị ví dụ có thể không khớp registry và chân GPIO trong code; registry trong source hiện tại mới là hành vi thực tế.
- Không có sơ đồ wiring hoàn chỉnh được xác nhận trong repository; chỉ dùng hardware mode sau khi tự xác minh mạch.
