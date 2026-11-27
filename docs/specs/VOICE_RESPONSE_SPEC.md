# VietHome AI -- Voice Response & TTS Integration Specification

**Document:** `VOICE_RESPONSE_SPEC.md`\
**Project:** VietHome AI -- Voice Assistant for Smart Home\
**Purpose:** Implement the remaining voice-response functionality and
integrate it with the existing backend and frontend.\
**Priority:** MVP first, then reliability and deployment.

------------------------------------------------------------------------

## 1. Objective

Implement a voice response system for the existing VietHome AI
application.

The system must: 1. Play pre-recorded static audio for known, fixed
responses. 2. Use TTS only for dynamic values, initially temperature and
humidity readings. 3. Connect voice responses to the existing
device-control and sensor workflows. 4. Integrate with the existing
backend and frontend without rebuilding either. 5. Work on the
development computer and Raspberry Pi, subject to the available audio
output device and configured Vietnamese TTS voice.

**Out of scope:** NLP, LLMs, intent classification, fuzzy matching,
semantic command understanding, and training a speech model. Do not add
these features.

This specification concerns the response/output side. Preserve the
existing command input and command execution implementation. Do not
replace it with a new command parser. If a required command or sensor
API does not exist, inspect the current implementation and add the
smallest compatible extension.

## 2. Required demo scenarios

The MVP is complete when these scenarios work end-to-end:

  -----------------------------------------------------------------------
  Scenario                Backend action/data     Spoken response
  ----------------------- ----------------------- -----------------------
  User turns on a light   Existing device-control Play the matching
                          flow succeeds           static confirmation

  User turns off a light  Existing device-control Play the matching
                          flow succeeds           static confirmation

  User turns on a fan     Existing device-control Play the matching
                          flow succeeds           static confirmation

  User turns off a fan    Existing device-control Play the matching
                          flow succeeds           static confirmation

  User turns on all       Existing bulk-control   Play static all-on
  devices                 flow succeeds           confirmation

  User turns off all      Existing bulk-control   Play static all-off
  devices                 flow succeeds           confirmation

  Device action fails     Backend returns a       Play a static failure
                          failure result          response

  User requests current   Read the latest         TTS speaks the numeric
  temperature             available sensor value  value and unit

  User requests current   Read the latest         TTS speaks the numeric
  humidity                available sensor value  value and unit

  User requests both      Read the latest         TTS speaks both values
  readings                available temperature   
                          and humidity            

  Sensor data is          Sensor service reports  Play a static
  unavailable/stale       no valid current value  sensor-unavailable
                                                  response
  -----------------------------------------------------------------------

The exact command recognition and device selection remain the
responsibility of the existing command-handling implementation. This
module receives a structured result/event; it must not interpret
free-form language.

## 3. Architecture and integration rules

### 3.1 Required flow

**Device command response**

``` text
Existing Frontend / Existing Command Input
        |
        v
Existing Backend Command/API Layer
        |
        v
Existing DeviceService
        |
        v
Existing DeviceRegistry / Device
        |
        v
Structured operation result
        |
        v
VoiceResponseService
        |
        +---- Static response key ----> StaticAudioPlayer
        |                                  |
        |                                  v
        |                         Pre-recorded WAV file
        |
        +---- Dynamic text ----------> TTSService
                                           |
                                           v
                                     Audio output
```

**Sensor response**

``` text
Existing Frontend / Existing Sensor API
        |
        v
Existing Backend Sensor Service / Existing sensor data source
        |
        v
Latest valid temperature and humidity
        |
        v
VoiceResponseService
        |
        v
Vietnamese response text with numeric values
        |
        v
TTSService
        |
        v
Audio output
```

### 3.2 Non-negotiable rules

-   Reuse the current FastAPI application, routers, configuration,
    device service, device registry, sensor service, and frontend.
-   Do not create a second backend, device controller, sensor polling
    loop, or competing source of truth.
-   Do not directly manipulate GPIO from the TTS/audio module.
-   A spoken success confirmation may only be selected after the backend
    confirms that the operation succeeded.
-   For partial bulk-operation failures, do not announce that every
    device was successfully controlled. Use a partial-failure response
    and include the result details in the API response.
-   Do not fabricate sensor readings. Speak only values returned by the
    existing sensor data source.
-   Do not speak `null`, `NaN`, infinity, invalid values, or stale
    values as if they were current.
-   Static audio and dynamic TTS must use the same response
    orchestration layer.
-   Do not block FastAPI's event loop with long synchronous playback or
    TTS work. Use an appropriate worker/thread or async adapter.
-   Ensure only one response playback is active at a time unless the
    existing application explicitly supports mixing.
-   Avoid duplicate playback when one command passes through multiple
    backend/frontend events. Use a request/event ID or idempotency
    mechanism.
-   Keep audio hardware optional: API and tests must still work when no
    speaker is attached.

## 4. Static audio asset location

Use this exact directory inside the existing repository:

``` text
backend/
└── app/
    └── ai/
        └── tts/
            ├── __init__.py
            ├── service.py
            ├── schemas.py
            ├── providers/
            │   ├── __init__.py
            │   ├── static_audio.py
            │   └── dynamic_tts.py
            ├── assets/
            │   ├── static/
            │   │   ├── common/
            │   │   ├── lights/
            │   │   ├── fans/
            │   │   ├── devices/
            │   │   └── sensors/
            │   ├── cache/
            │   └── manifest.json
            └── README.md
```

**All pre-recorded response files must be stored under:**

`backend/app/ai/tts/assets/static/`

Do not scatter audio files in `frontend/`, the repository root, or
arbitrary folders.

The `cache/` directory is only for generated temporary/dynamic audio if
the chosen TTS provider needs it. It is not the location for manually
recorded fixed responses. Add generated cache files to `.gitignore`
unless there is a deliberate reason to version them.

### 4.1 Required static recording inventory

Create a manifest that maps stable response keys to relative file paths.
Use these suggested keys; adjust wording to match the actual product
voice, but do not change the keys without updating all references.

  ---------------------------------------------------------------------------------------
  Response key                  Suggested file path               Suggested Vietnamese
                                                                  recording
  ----------------------------- --------------------------------- -----------------------
  `common.ready`                `common/ready.wav`                "VietHome đã sẵn sàng."

  `common.understood`           `common/understood.wav`           "Tôi đã nhận được yêu
                                                                  cầu."

  `common.action_success`       `common/action_success.wav`       "Đã thực hiện yêu cầu."

  `common.action_failed`        `common/action_failed.wav`        "Xin lỗi, tôi chưa thể
                                                                  thực hiện yêu cầu."

  `common.device_unavailable`   `common/device_unavailable.wav`   "Thiết bị hiện không
                                                                  khả dụng."

  `common.partial_success`      `common/partial_success.wav`      "Một số thiết bị chưa
                                                                  thể thực hiện yêu cầu."

  `lights.turned_on`            `lights/turned_on.wav`            "Đã bật đèn."

  `lights.turned_off`           `lights/turned_off.wav`           "Đã tắt đèn."

  `fans.turned_on`              `fans/turned_on.wav`              "Đã bật quạt."

  `fans.turned_off`             `fans/turned_off.wav`             "Đã tắt quạt."

  `devices.all_turned_on`       `devices/all_turned_on.wav`       "Đã bật tất cả thiết
                                                                  bị."

  `devices.all_turned_off`      `devices/all_turned_off.wav`      "Đã tắt tất cả thiết
                                                                  bị."

  `sensors.unavailable`         `sensors/unavailable.wav`         "Hiện tại chưa có dữ
                                                                  liệu cảm biến."

  `sensors.stale`               `sensors/stale.wav`               "Dữ liệu cảm biến đã
                                                                  cũ, vui lòng thử lại
                                                                  sau."
  ---------------------------------------------------------------------------------------

For a device-specific confirmation, support an optional device display
name. Example: play `lights.turned_on` then optionally speak the
room/device name through TTS, or use a separate recorded clip only if
the existing product has a small fixed set of rooms. Do not create an
unbounded set of recordings for arbitrary device names.

### 4.2 Audio format

Use a consistent format for static files: - WAV container. - PCM signed
16-bit. - Mono. - 16 kHz sample rate as the default. - No
leading/trailing silence longer than necessary. - Normalize loudness
consistently; avoid clipping. - Keep recordings short and clear, in
natural Vietnamese. - Use UTF-8 for manifest and metadata.

The audio player must validate file existence and format at startup or
on first use. A missing file must not crash the backend. Log a clear
warning and return a controlled fallback/error result.

### 4.3 Manifest format

Implement `manifest.json` similar to:

``` json
{
  "version": 1,
  "default_locale": "vi-VN",
  "responses": {
    "common.ready": {
      "path": "common/ready.wav",
      "type": "static",
      "description": "Thông báo hệ thống sẵn sàng"
    },
    "lights.turned_on": {
      "path": "lights/turned_on.wav",
      "type": "static",
      "description": "Xác nhận đã bật đèn"
    },
    "sensors.unavailable": {
      "path": "sensors/unavailable.wav",
      "type": "static",
      "description": "Không có dữ liệu cảm biến"
    }
  }
}
```

Paths in the manifest must be relative to `assets/static/`. Resolve them
safely and reject path traversal (`..`, absolute paths, or paths
escaping the static directory). Validate that every registered static
key maps to an existing file. The repository may initially contain a
recording checklist and placeholder-free manifest entries, but do not
pretend audio files exist when they have not been supplied.

## 5. Static audio versus dynamic TTS policy

Use this decision:

  Content                             Method
  ----------------------------------- ------------------------------
  "Đã bật đèn"                        Static WAV
  "Đã tắt đèn"                        Static WAV
  "Đã bật quạt"                       Static WAV
  "Đã tắt quạt"                       Static WAV
  "Đã bật tất cả thiết bị"            Static WAV
  "Đã tắt tất cả thiết bị"            Static WAV
  Generic success/failure             Static WAV
  Current temperature value           Dynamic TTS
  Current humidity value              Dynamic TTS
  Temperature and humidity together   Dynamic TTS
  Arbitrary device/room name          Dynamic TTS only if required

Do not synthesize fixed phrases on every request. Do not pre-record
sensor values because they change.

For a combined response, prefer one natural TTS utterance, for
example: - "Nhiệt độ hiện tại là 28 độ C." - "Độ ẩm hiện tại là 75 phần
trăm." - "Nhiệt độ hiện tại là 28 độ C, độ ẩm là 75 phần trăm."

If a static prefix is needed, keep the orchestration simple and avoid
awkward pauses or overlapping audio.

## 6. Dynamic TTS requirements

### 6.1 Provider design

Create a small provider interface so the application can use a local TTS
engine without coupling business logic to one library.

The implementation must: - Support Vietnamese text (`vi-VN`) if the
selected installed voice supports it. - Be configurable through
environment variables. - Prefer a local/offline provider for Raspberry
Pi deployment. - Never silently call a cloud API or send sensor data
externally. - Report a clear error if no suitable Vietnamese voice is
installed/configured. - Avoid reinitializing the engine for every
utterance where the provider supports reuse. - Support speaking numeric
values and units naturally. - Allow tests to inject a fake TTS provider.

Do not assume that a Windows voice is also installed on Raspberry Pi.
Verify voice availability on each platform and document
installation/configuration. If the current environment lacks a
Vietnamese voice, implement the provider adapter and a clear setup
instruction rather than claiming Vietnamese speech works.

### 6.2 Numeric formatting

Create a dedicated formatter for sensor values before passing them to
TTS: - Temperature: speak the value followed by "độ C". - Humidity:
speak the value followed by "phần trăm". - Round only for presentation;
retain the original sensor value in the API response. - Avoid reading
excessive decimal places. - Handle negative temperatures if the sensor
range allows them. - Reject invalid values and out-of-range values
according to the existing sensor schema. - Do not convert missing values
to zero.

Examples: - `28` → "Nhiệt độ hiện tại là 28 độ C." - `28.6` → "Nhiệt độ
hiện tại là 28 phẩy 6 độ C." - `75` → "Độ ẩm hiện tại là 75 phần trăm."

Use Vietnamese number formatting appropriate for speech. Do not rely on
locale-dependent formatting that may vary between Windows and Linux.

### 6.3 Sensor data freshness

Use the existing sensor service/API/data source. Do not add a second
sensor polling mechanism.

If the current sensor data includes a timestamp: - Apply a configurable
maximum age. - If the reading is older than the allowed age, return a
stale-data result and play `sensors.stale`. - If the timestamp is
missing, follow the existing sensor contract and document the behavior;
do not invent a timestamp.

If the sensor service reports an unavailable/error state, play
`sensors.unavailable` and return a structured error.

## 7. Backend service contract

Implement a cohesive service, for example `VoiceResponseService`,
responsible for: 1. Choosing static response keys. 2. Formatting dynamic
sensor speech. 3. Calling static audio or TTS providers. 4. Managing
playback serialization. 5. Returning a structured result to the
API/frontend. 6. Recording logs and playback errors.

Keep device control and sensor retrieval in their existing services.
`VoiceResponseService` must orchestrate responses, not own hardware
business logic.

### 7.1 Response selection

Use structured backend outcomes rather than parsing natural-language
strings.

Examples: - Successful light ON → `lights.turned_on` - Successful light
OFF → `lights.turned_off` - Successful fan ON → `fans.turned_on` -
Successful fan OFF → `fans.turned_off` - Successful all-device ON →
`devices.all_turned_on` - Successful all-device OFF →
`devices.all_turned_off` - Failed operation → `common.action_failed` or
`common.device_unavailable` - Partial bulk result →
`common.partial_success`

Only select the success clip after the existing service returns a
successful result.

If the backend has multiple device types beyond lights and fans, map
them using the existing device metadata. Do not assume every device is a
light or fan.

### 7.2 Suggested schemas

Use the project's existing Pydantic conventions. A response result
should expose fields equivalent to:

``` json
{
  "request_id": "uuid",
  "status": "played",
  "response_mode": "static",
  "response_key": "lights.turned_on",
  "text": "Đã bật đèn.",
  "audio_played": true,
  "audio_path": "lights/turned_on.wav",
  "error": null
}
```

For dynamic sensor TTS:

``` json
{
  "request_id": "uuid",
  "status": "played",
  "response_mode": "tts",
  "response_key": "sensors.temperature_humidity",
  "text": "Nhiệt độ hiện tại là 28 độ C, độ ẩm là 75 phần trăm.",
  "audio_played": true,
  "audio_path": null,
  "error": null,
  "data": {
    "temperature": 28.0,
    "humidity": 75.0
  }
}
```

Do not expose absolute server filesystem paths to the frontend.
`audio_path` above is a relative asset identifier for diagnostics only;
if the frontend needs to play audio, provide a safe API URL or a stable
response key.

### 7.3 API integration

Inspect existing routes first and extend them without breaking current
contracts. Add only the missing endpoints. Suggested API capabilities:

-   Play/test a registered static response by key (restricted to known
    manifest keys).
-   Speak a supplied dynamic text only if required by the existing
    frontend; validate length and locale.
-   Request current temperature speech.
-   Request current humidity speech.
-   Request combined temperature/humidity speech.
-   Query voice-response/TTS availability and current playback status.
-   Stop playback if the selected audio backend supports it.

Potential route naming (adapt to existing route conventions): -
`GET /api/voice/response/status` -
`POST /api/voice/response/play/{response_key}` -
`POST /api/voice/response/sensors/temperature` -
`POST /api/voice/response/sensors/humidity` -
`POST /api/voice/response/sensors/summary`

Do not add duplicate endpoints if equivalent routes already exist.
Protect the static-play endpoint against arbitrary file paths: accept
response keys, never client-supplied filesystem paths.

## 8. Playback ownership and frontend behavior

First inspect where the speaker is physically connected and how the
current application is deployed.

Support one clearly configured playback owner: - **Server mode:**
backend on Raspberry Pi plays through the Pi's speaker/audio output. The
frontend receives status/text but must not play the same response
again. - **Client mode:** backend returns a safe audio URL/stream or
generated audio payload and the frontend plays it. Do not also play on
the server.

Use a setting such as `VOICE_PLAYBACK_MODE=server|client`. Choose the
mode that matches the current project architecture; do not enable both
for one response.

If the current frontend already has a voice response/audio component,
reuse it. Otherwise add the smallest UI integration: - Show the response
text/status. - Show whether audio is available/playing/failed. - Provide
a manual replay control if useful. - Avoid building a new dashboard or
redesigning unrelated screens.

If server mode is selected, do not expose internal audio asset paths as
public filesystem URLs.

## 9. Configuration

Add settings to the existing Pydantic Settings class and `.env.example`,
using names consistent with the project. Suggested settings:

``` env
VOICE_RESPONSE_ENABLED=true
VOICE_PLAYBACK_MODE=server
VOICE_STATIC_AUDIO_DIR=backend/app/ai/tts/assets/static
VOICE_AUDIO_SAMPLE_RATE=16000
VOICE_AUDIO_CHANNELS=1
VOICE_AUDIO_FORMAT=wav
VOICE_TTS_ENABLED=true
VOICE_TTS_PROVIDER=local
VOICE_TTS_LANGUAGE=vi-VN
VOICE_TTS_VOICE=
VOICE_TTS_RATE=1.0
VOICE_SENSOR_MAX_AGE_SECONDS=120
VOICE_AUDIO_QUEUE_ENABLED=true
```

Do not duplicate existing audio settings. If `AUDIO_SAMPLE_RATE` or
other equivalent setting already exists, reuse it or migrate carefully
with backward compatibility.

Resolve asset paths robustly relative to the backend package/repository,
not the process's current working directory. Validate configuration at
startup and report missing optional audio devices without preventing
non-audio APIs from starting.

## 10. Suggested implementation sequence

Implement in this order to obtain a working demo quickly:

### Phase 1 -- Static audio playback

-   Create the specified folder structure.
-   Add `manifest.json`.
-   Implement static audio provider and safe key lookup.
-   Add a fake/no-op player for tests.
-   Add one playback test.
-   Add a recording checklist in `backend/app/ai/tts/README.md`.
-   If actual recordings are not yet supplied, report that the player is
    implemented but real playback requires the WAV files. Do not create
    fake audio and call it a recording.

### Phase 2 -- Dynamic TTS

-   Implement provider interface and local provider adapter.
-   Verify Vietnamese voice availability on the development OS.
-   Implement numeric speech formatter.
-   Add fake provider tests.
-   Verify temperature and humidity utterances.

### Phase 3 -- Backend integration

-   Connect operation results from the existing DeviceService flow to
    response selection.
-   Connect current sensor readings from the existing sensor service to
    dynamic TTS.
-   Add only necessary API endpoints.
-   Ensure no duplicate device/sensor business logic.

### Phase 4 -- Frontend integration

-   Reuse the existing UI and API client.
-   Display response text and playback status.
-   Add replay or sensor-speech controls only where useful.
-   Prevent duplicate audio playback.

### Phase 5 -- Raspberry Pi validation

-   Document speaker/audio output setup.
-   Install/configure the chosen local Vietnamese TTS voice.
-   Validate static WAV playback.
-   Validate dynamic sensor speech.
-   Verify graceful operation when no speaker or TTS voice is available.

## 11. Testing requirements

At minimum, add tests for:

### Static audio

-   Known response key resolves to the correct file.
-   Unknown key is rejected.
-   Missing WAV returns a controlled error.
-   Path traversal is rejected.
-   Concurrent requests do not overlap playback.
-   Duplicate request IDs do not play twice if idempotency is
    implemented.

### Device response mapping

-   Successful light ON selects `lights.turned_on`.
-   Successful light OFF selects `lights.turned_off`.
-   Successful fan ON selects `fans.turned_on`.
-   Successful fan OFF selects `fans.turned_off`.
-   Successful bulk ON/OFF selects the correct all-device response.
-   Failed operations never select success clips.
-   Partial bulk failures select a partial-failure response.

### Dynamic sensor TTS

-   Temperature is spoken with degrees Celsius.
-   Humidity is spoken with percent.
-   Combined response contains both readings.
-   Decimal values are formatted naturally.
-   Missing, invalid, or stale readings do not get spoken as current
    values.
-   Sensor service exceptions produce a controlled response.

### Integration

-   Existing device APIs still pass their tests.
-   Existing sensor APIs still pass their tests.
-   Voice response can be disabled through configuration.
-   Tests run without physical microphone, speaker, GPIO, or Raspberry
    Pi.
-   Mock providers are used for CI.

## 12. Logging and privacy

-   Log response key, response mode, request ID, playback status, and
    errors.
-   Do not log secrets.
-   Do not store sensor audio or arbitrary user speech.
-   Do not record microphone input as part of this task.
-   Avoid logging full dynamic speech text if it could later contain
    sensitive information; sensor values may be logged according to
    existing project policy.
-   Keep generated audio cache bounded and clean up temporary files.

## 13. Definition of Done

The implementation is accepted only when:

-   [ ] The exact static audio directory exists.
-   [ ] `manifest.json` maps all required response keys.
-   [ ] Static audio playback works with real WAV files when supplied.
-   [ ] Missing audio files fail gracefully.
-   [ ] Successful light/fan/all-device actions trigger the correct
    confirmation.
-   [ ] Failed and partial actions never announce false success.
-   [ ] Temperature is fetched from the existing sensor source and
    spoken by TTS.
-   [ ] Humidity is fetched from the existing sensor source and spoken
    by TTS.
-   [ ] Combined temperature/humidity response works.
-   [ ] The frontend shows the response result and does not cause
    duplicate playback.
-   [ ] Existing backend/frontend behavior remains intact.
-   [ ] Tests pass on the development machine using mocks.
-   [ ] Raspberry Pi setup and audio configuration are documented.
-   [ ] No NLP, fuzzy matching, LLM, or unnecessary STT component was
    added.

## 14. Agent execution instructions

You are working in an existing repository, not creating a new project.

1.  Read this specification and inspect the repository before changing
    code.
2.  Inspect the actual backend routes, `DeviceService`,
    `DeviceRegistry`, sensor implementation, frontend API client, and
    current deployment scripts.
3.  Identify the real source of temperature/humidity and the real result
    types returned by device operations.
4.  Produce a concise file-change plan, then implement the MVP in the
    sequence in Section 10. Do not stop after producing a plan.
5.  Adapt names and paths to the actual codebase while preserving the
    exact static asset location specified in Section 4.
6.  Do not invent sensor APIs, device IDs, hardware capabilities, or
    existing frontend components.
7.  Do not replace working modules or rewrite unrelated files.
8.  Run relevant tests after each phase and fix regressions.
9.  If real WAV recordings or a Vietnamese voice model are not present,
    implement the integration, add the exact recording/model setup
    instructions, and clearly report what external asset is still
    required.
10. At completion, report changed files, commands to run, test results,
    how to add recordings, and how to verify the demo on Windows and
    Raspberry Pi.

**Start now. Prioritize a working static-response + dynamic sensor-TTS
demo over optional refinements.**
