# VietHome AI --- AI & Voice Command Integration Specification

> **Document:** `docs/specs/AI_SPEC.md`\
> **Project:** VietHome AI / Voice-Assistant\
> **Status:** Implementation-ready specification\
> **Scope:** AI voice pipeline, Vietnamese command understanding, and
> integration with the existing FastAPI backend\
> **Target runtime:** Windows development environment and Raspberry Pi 4
> (Debian 12, Python 3.11, ARM64)\
> **Primary language:** Vietnamese\
> **Version:** 1.0

> **Language update (2026-11-28):** English is now the default language for STT, Wake Word recognition, and command examples/catalogue. Existing Vietnamese command aliases remain accepted for backward compatibility. The original Vietnamese examples below describe that legacy compatibility; use `STT_LANGUAGE=en` for current configuration.

------------------------------------------------------------------------

## 1. Mission and implementation rules

### 1.1 Mission

Implement the AI subsystem that allows a user to control registered
smart-home devices by voice:

1.  The system continuously listens to the microphone.
2.  It detects the configured Wake Word, initially **"hey berry"**
    (including configurable spoken variants).
3.  After detecting the Wake Word, it records the following user command
    until silence or timeout.
4.  Speech-to-Text (STT) converts the recording into English text by default.
5.  A command-processing pipeline normalizes the text, finds the closest
    supported command, resolves its intent and target device, and
    calculates a confidence/similarity score.
6.  If the command passes the configured acceptance rules, the AI layer
    calls the **existing backend `DeviceService`**.
7.  The backend's existing device abstraction/registry executes the
    action. The AI layer must never control GPIO or hardware directly.
8.  The result is exposed through the existing backend API so the
    already-built frontend can display status, transcript, and execution
    result.

### 1.2 Non-negotiable rules for agents

-   **Do not rebuild the backend or frontend.** They already exist.
-   Inspect the current repository before editing. Treat the checked-out
    source code as authoritative; this document describes the intended
    integration contract.
-   Preserve existing API routes, schemas, device abstractions,
    settings, tests, and behavior unless a change is necessary and is
    documented.
-   Reuse the current `DeviceService`, `DeviceRegistry`, and `Device`
    abstraction. Do not create a second hardware-control path.
-   AI code may produce an intent/action request, but only the backend
    device service may execute it.
-   Do not import GPIO libraries into the AI modules.
-   Do not load a Whisper model for every request. Load it once and
    reuse it.
-   Do not open the microphone once per HTTP request. A single
    background voice service owns the microphone.
-   Do not start multiple microphone listeners in the same application
    process.
-   Do not silently execute a command when its target device is unknown,
    disabled, or ambiguous.
-   Do not treat a fuzzy similarity score as proof that a command is
    safe. Negation and conflicting actions must be checked separately.
-   Keep the AI/STT dependencies optional and separated from the
    backend's lightweight base dependencies.
-   All important behavior must be testable without a microphone,
    Whisper model, Raspberry Pi, or physical hardware.

### 1.3 Repository context

The repository README identifies the project as a FastAPI backend,
Flutter frontend, hardware configuration, and Raspberry Pi deployment
scripts. The README documents:

-   Backend: `backend/`
-   Frontend: `frontend/`
-   Hardware configuration: `hardware/`
-   Scripts: `scripts/`
-   Documentation/specifications: `docs/specs/`

Existing backend architecture known to this project includes a device
service, registry, device interface, and mock device. Agents must
inspect the current implementation and use its real method signatures
rather than assuming signatures from this document.

Repository: <https://github.com/Crabbercat/Voice-Assistant>

------------------------------------------------------------------------

## 2. Scope

### 2.1 Included in this implementation

-   Microphone capture and buffering.
-   Wake Word detection.
-   Command audio recording with silence detection and maximum duration.
-   English STT using Faster-Whisper by default.
-   Text normalization, including Vietnamese diacritic removal for
    matching.
-   Command catalogue stored in JSON.
-   Fuzzy matching using RapidFuzz.
-   Intent, action, device type, and target resolution.
-   Confidence scoring and acceptance/rejection reasons.
-   Integration with the existing `DeviceService`.
-   FastAPI endpoints for voice status, lifecycle, command catalogue,
    text-only testing, and recent command history.
-   Application lifecycle management for the voice service.
-   Unit, API, integration, and Raspberry Pi smoke tests.
-   Configuration and setup documentation.

### 2.2 Explicitly out of scope for this phase

-   Rebuilding or redesigning the Flutter frontend.
-   Replacing the existing device service or hardware abstraction.
-   Direct GPIO control from AI code.
-   LLM-based reasoning or external AI APIs.
-   Text-to-Speech (TTS) responses.
-   User accounts, voice biometrics, speaker identification, and
    personalized voice profiles.
-   Training a custom acoustic model.
-   Guaranteed production-grade always-on Wake Word detection.
-   Remote Internet-based command execution.

These may be added later without changing the core
intent-to-device-service boundary.

------------------------------------------------------------------------

## 3. Target architecture

### 3.1 High-level pipeline

``` text
                         RASPBERRY PI / DEVELOPMENT PC
┌──────────────────────────────────────────────────────────────────┐
│                         Microphone                               │
└──────────────────────────────┬───────────────────────────────────┘
                               │ PCM audio
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    AudioCapture / AudioBuffer                     │
│             continuous stream, frame queue, silence              │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                       WakeWordDetector                            │
│                  initial implementation: Whisper                  │
└──────────────────────────────┬───────────────────────────────────┘
                         Wake Word found
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    CommandRecorder                                │
│             record until silence / maximum duration               │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    SpeechRecognizer                               │
│                  Faster-Whisper, language=vi                      │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    CommandProcessor                               │
│  normalize → detect negation/conflicts → fuzzy match → resolve     │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                 Structured VoiceCommand                           │
│          intent, action, device type, target, score                │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                     VoiceService                                  │
│      validate target and acceptance policy; call DeviceService    │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│              EXISTING BACKEND — DO NOT REPLACE                    │
│          DeviceService → DeviceRegistry → Device                   │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
                         Mock / Real Device
```

The frontend communicates with FastAPI only. It must not communicate
directly with the microphone or hardware.

### 3.2 Responsibilities by layer

  -----------------------------------------------------------------------
  Layer                   Responsibility          Must not do
  ----------------------- ----------------------- -----------------------
  Audio capture           Read microphone frames  STT, command matching,
                          and provide audio       device execution
                          buffers                 

  Wake Word detector      Decide whether the wake Execute a device action
                          phrase was spoken       

  Command recorder        Capture the command     Resolve intent
                          after Wake Word         

  Speech recognizer       Convert audio to text   Choose or execute a
                                                  device action

  Normalizer              Normalize text for      Delete negation or
                          comparison              action meaning

  Matcher                 Rank catalogue          Call backend or
                          candidates              hardware

  Intent resolver         Resolve                 Bypass acceptance
                          action/device/target    policy
                          and ambiguity           

  Command processor       Orchestrate             Access GPIO
                          text-processing stages  

  Voice service           Own lifecycle and       Duplicate device logic
                          coordinate              
                          pipeline/backend        
                          integration             

  Existing DeviceService  Execute the resolved    Depend on
                          device action           Whisper/RapidFuzz
  -----------------------------------------------------------------------

### 3.3 Suggested module layout

Agents may adapt this layout to the repository's existing naming
conventions, but must keep the responsibilities separate.

``` text
backend/app/
├── ai/
│   ├── __init__.py
│   ├── speech/
│   │   ├── __init__.py
│   │   ├── audio_capture.py
│   │   ├── command_recorder.py
│   │   ├── speech_recognizer.py
│   │   └── wake_word_detector.py
│   └── command/
│       ├── __init__.py
│       ├── normalizer.py
│       ├── matcher.py
│       ├── intent_resolver.py
│       └── command_processor.py
├── api/
│   ├── routes.py                 # existing; preserve
│   └── voice_routes.py           # new
├── schemas/
│   ├── device.py                 # existing; preserve
│   └── voice.py                  # new
├── services/
│   ├── device_service.py        # existing; reuse
│   └── voice_service.py         # new integration/orchestration
└── core/
    └── config.py                # existing; extend carefully

hardware/
└── configs/
    ├── devices.example.json     # existing; preserve
    └── commands.json            # new command catalogue

backend/tests/
├── test_voice_normalizer.py
├── test_voice_matcher.py
├── test_voice_intent_resolver.py
├── test_voice_processor.py
├── test_voice_api.py
└── test_voice_service.py
```

Do not move or rename existing modules just to match this diagram.

------------------------------------------------------------------------

## 4. Voice interaction and state machine

### 4.1 Expected user interaction

Example:

1.  User says: "Hey Berry".
2.  System detects the Wake Word and changes to `LISTENING_COMMAND`.
3.  User says: "Bật đèn phòng khách lên".
4.  System records the command until the configured silence interval is
    reached.
5.  STT returns: `Bật đèn phòng khách lên`.
6.  Command processor resolves `LIGHT_ON`, target `living_room`.
7.  Voice service validates that the target exists and is enabled.
8.  Voice service invokes the existing device service.
9.  API/history records the transcript, resolved command, score, and
    execution result.
10. Service returns to `WAITING_WAKE_WORD`.

### 4.2 States

  State                 Meaning
  --------------------- ------------------------------------------------------
  `STOPPED`             Voice service is not running
  `STARTING`            Loading model and opening microphone
  `WAITING_WAKE_WORD`   Listening for the Wake Word
  `LISTENING_COMMAND`   Recording the command after Wake Word
  `PROCESSING`          STT and command interpretation are running
  `EXECUTING`           Backend device action is running
  `ERROR`               Recoverable or fatal service error
  `STOPPING`            Gracefully stopping listener and releasing resources

State transitions:

``` text
STOPPED → STARTING → WAITING_WAKE_WORD
WAITING_WAKE_WORD → LISTENING_COMMAND       (Wake Word detected)
LISTENING_COMMAND → PROCESSING              (silence or max duration)
PROCESSING → EXECUTING                      (accepted command)
PROCESSING → WAITING_WAKE_WORD              (rejected / no speech)
EXECUTING → WAITING_WAKE_WORD               (success or execution failure)
Any active state → STOPPING → STOPPED
Recoverable runtime error → ERROR → WAITING_WAKE_WORD
Fatal initialization error → ERROR
```

### 4.3 Audio behavior

Initial defaults (all configurable):

  Setting                                                     Default
  -------------------------- ----------------------------------------
  Sample rate                                               16,000 Hz
  Channels                                                   1 (mono)
  Audio dtype                                      float32 internally
  Wake detection chunk                                   2--3 seconds
  Command silence duration                                1.2 seconds
  Maximum command duration                                 15 seconds
  Minimum command duration                                0.4 seconds
  RMS silence threshold          0.012 (must be tuned per microphone)
  Audio queue                  bounded; avoid unbounded memory growth

Requirements:

-   Prefer a continuous `sounddevice.InputStream` or equivalent
    callback/queue design over repeatedly opening/closing the
    microphone.
-   Use a bounded queue/ring buffer.
-   Do not lose audio that occurs immediately after the Wake Word. Keep
    a short pre-roll buffer or preserve the tail of the Wake Word audio
    so the first command syllable is not cut off.
-   Use overlapping windows or a rolling buffer for Wake Word detection.
    A Wake Word split exactly across two non-overlapping chunks must not
    be systematically missed.
-   Silence detection must use audio energy/RMS with a configurable
    threshold and minimum speech duration. Do not treat one quiet frame
    as the end of a sentence.
-   If the command exceeds maximum duration, stop recording and process
    the captured audio; report that it reached the maximum duration.
-   If no usable audio or no transcript is produced, record a
    rejected/no-speech result and return to wake listening.
-   Handle missing microphone, permission errors, unsupported sample
    rate, and stream termination without crashing the FastAPI process.
-   Release the microphone stream and model resources cleanly on service
    shutdown.

### 4.4 Wake Word implementation

For the first working version, reuse the same Faster-Whisper model to
transcribe short rolling audio windows and detect configured wake
phrases. This is a prototype trade-off, not the final ideal for a 24/7
embedded listener.

Initial phrase: `hey berry`.

Configurable variants may include:

-   `hey berry`
-   `hey barry`
-   `hey beri`
-   `hey very`
-   `hey be ri`

Implementation requirements:

-   Normalize the transcript before matching Wake Word variants.
-   Log detected transcript text and detection timestamp at debug/info
    level, but do not dump raw audio.
-   Avoid requiring the phrase to occupy the entire transcription. It
    may appear with surrounding words.
-   Avoid triggering from an empty transcript.
-   Add a short configurable cooldown after a Wake Word to prevent
    repeated triggers.
-   The wake detector must be replaceable later by a dedicated
    keyword-spotting model without changing the command-processing or
    backend integration interfaces.

**Important:** Whisper-based Wake Word detection can be CPU-intensive
and may produce false triggers. Keep this implementation modular and
measure CPU usage on the Raspberry Pi.

------------------------------------------------------------------------

## 5. Speech-to-Text

### 5.1 Library

Use:

-   `faster-whisper`
-   `sounddevice`
-   `numpy`
-   `scipy` only if resampling is required

Do not add a second large language model.

### 5.2 Model defaults

  -----------------------------------------------------------------------
  Setting                             Default
  ----------------------------------- -----------------------------------
  Model                               `tiny`

  Device                              `cpu`

  Compute type                        `int8`

  Language                            `vi`

  Beam size                           `1`

  VAD filter                          configurable; start with `false`
                                      for short test windows and evaluate

  Condition on previous text          `false` for independent command
                                      recordings
  -----------------------------------------------------------------------

Model name, device, compute type, and language must be configurable.

### 5.3 Model lifecycle

-   Load model once when the voice service starts (or lazily on first
    start).
-   Store the recognizer instance in the service.
-   Do not instantiate `WhisperModel` inside every transcription call.
-   Handle model-load failure explicitly and expose it in
    `/api/voice/status`.
-   Keep model files in a configurable cache/model directory. Do not
    commit large model files to Git.
-   Do not force model download on every application boot if the model
    is already cached.
-   On Raspberry Pi, benchmark the selected model before changing the
    default to a larger model.

### 5.4 Recognizer interface

Provide a small interface similar to:

``` python
class SpeechRecognizer:
    def load(self) -> None: ...
    def transcribe(self, audio: "numpy.ndarray") -> "TranscriptionResult": ...
    def unload(self) -> None: ...
```

The exact implementation may be synchronous internally. If called from
async FastAPI code, run CPU/blocking inference outside the event loop
(for example, a worker thread or executor).

`TranscriptionResult` must include at least:

-   `text: str`
-   `language: str | None`
-   `language_probability: float | None`
-   `duration_seconds: float | None`
-   `segments`: optional compact segment metadata

Do not expose the full raw audio through API responses.

------------------------------------------------------------------------

## 6. Command text processing

### 6.1 Processing order

The command processor must execute these stages in order:

1.  Validate transcript is not empty.
2.  Preserve the original transcript.
3.  Normalize text for comparison.
4.  Detect negation and conflicting intent indicators.
5.  Match against enabled command aliases.
6.  Resolve action, device type, and target.
7.  Calculate scores and acceptance decision.
8.  Return a structured result.
9.  Only the voice service may forward an accepted result to
    `DeviceService`.

### 6.2 Text normalization

Create a deterministic normalizer.

Required transformations:

-   Unicode normalize (`NFC` or a consistent canonical form).
-   Lowercase.
-   Trim leading/trailing whitespace.
-   Collapse repeated whitespace.
-   Remove punctuation that does not affect intent.
-   Remove Vietnamese diacritics for the matching representation.
-   Convert `đ` to `d`.
-   Keep the original transcript unchanged for logs and UI.

Examples:

  Original                       Normalized
  ------------------------------ -----------------------------
  `Bật đèn phòng khách!`         `bat den phong khach`
  `MỞ ĐÈN phòng ngủ`             `mo den phong ngu`
  `Tắt cái quạt giúp tôi nhé.`   `tat cai quat giup toi nhe`

Do not use the normalized form as the only record of what the user said.

### 6.3 Negation and safety markers

Negation is semantically important. Never remove or ignore these words
during command interpretation:

-   `không`
-   `đừng`
-   `chưa`
-   `khỏi`
-   `đừng có`
-   `không được`

Examples:

-   "Đừng bật đèn" must **not** resolve to `LIGHT_ON`.
-   "Không tắt quạt" must **not** resolve to `FAN_OFF`.
-   "Đừng tắt đèn" must not be interpreted as `LIGHT_OFF`.

For this first implementation, if a negation marker occurs in the same
command utterance and its scope cannot be reliably resolved, reject the
command with reason `NEGATION_DETECTED` rather than execute it.

This conservative rule is mandatory even though the overall product
prioritizes recall.

### 6.4 Optional filler-word handling

The system may identify filler words such as `giúp tôi`, `làm ơn`,
`nhé`, `với`, `đi`, `lên`, `xuống`, but:

-   Do not remove action words.
-   Do not remove device/room names.
-   Do not remove negation.
-   Do not remove `lên` or `xuống` if a device/action may depend on it.
-   Filler removal must not be required for a command to match.

------------------------------------------------------------------------

## 7. Command catalogue

### 7.1 Source of truth

Create:

`hardware/configs/commands.json`

The catalogue is configuration, not hard-coded matching logic. It must
be loaded and validated at startup. If the file is invalid, return a
clear configuration error; do not silently start with an empty
catalogue.

Initial catalogue example:

``` json
{
  "version": 1,
  "commands": [
    {
      "id": "light_on",
      "intent": "LIGHT_ON",
      "action": "turn_on",
      "device_type": "light",
      "enabled": true,
      "aliases": [
        "bat den",
        "mo den",
        "bat bong den",
        "mo bong den",
        "bat den len"
      ],
      "targets": ["living_room", "bedroom", "kitchen"]
    },
    {
      "id": "light_off",
      "intent": "LIGHT_OFF",
      "action": "turn_off",
      "device_type": "light",
      "enabled": true,
      "aliases": [
        "tat den",
        "ngat den",
        "tat bong den"
      ],
      "targets": ["living_room", "bedroom", "kitchen"]
    },
    {
      "id": "fan_on",
      "intent": "FAN_ON",
      "action": "turn_on",
      "device_type": "fan",
      "enabled": true,
      "aliases": [
        "bat quat",
        "mo quat",
        "bat quat gio"
      ],
      "targets": ["living_room", "bedroom"]
    },
    {
      "id": "fan_off",
      "intent": "FAN_OFF",
      "action": "turn_off",
      "device_type": "fan",
      "enabled": true,
      "aliases": [
        "tat quat",
        "ngat quat"
      ],
      "targets": ["living_room", "bedroom"]
    }
  ]
}
```

This is an illustrative initial catalogue. Agents must check the actual
device configuration and backend model before finalizing target IDs.

### 7.2 Catalogue validation

Validate at load time:

-   `version` is supported.
-   `commands` is a list.
-   Every command has unique `id`.
-   Every command has a non-empty `intent`, `action`, `device_type`, and
    alias list.
-   Aliases are normalized before comparison.
-   No alias is empty after normalization.
-   Duplicate aliases that map to conflicting intents/actions are
    rejected or reported as configuration errors.
-   `enabled` defaults to `true` only if omitted by a validated schema.
-   Targets must map to real device identifiers or an explicitly
    supported target resolver.
-   Disabled commands must never be matched for execution.

### 7.3 Target resolution

The command resolver must not assume that a room name equals a backend
device ID.

Use the existing device registry/configuration as the authoritative
source of available device IDs and types. Introduce a mapping layer only
if the existing device schema needs one.

For example:

-   Spoken target: `phong khach`
-   Resolved logical target: `living_room`
-   Backend device ID: obtained from the current device
    registry/configuration

If the user says "bật đèn" but there are multiple enabled lights and no
default target policy exists, return `TARGET_REQUIRED` or
`AMBIGUOUS_TARGET`. Do not randomly choose a device.

------------------------------------------------------------------------

## 8. Fuzzy matching and acceptance policy

### 8.1 Library

Use `rapidfuzz`.

Add it to the AI/voice optional dependency file, not to the minimal
backend base dependency list.

### 8.2 Intended behavior

The product wants to favor recall: it is better to recognize common
variations than to reject every slightly different sentence. However,
false execution of an opposite action (for example, turning a light off
when the user asked to turn it on) is not acceptable.

Therefore:

-   Similarity threshold starts at **80/100** and is configurable.
-   The threshold is a candidate-generation threshold, not the only
    execution rule.
-   Prefer token-aware comparison (such as `token_set_ratio` or
    `token_sort_ratio`) over raw substring matching.
-   Do not use `partial_ratio` alone; it can accept a short command
    embedded in a sentence with a different meaning.
-   Score aliases and select the best candidate, but preserve enough
    information to detect conflicting actions.
-   If the best two candidates are close and imply different actions or
    targets, return `AMBIGUOUS_COMMAND`.
-   Do not execute when negation or an opposing action is detected.
-   Track accepted, rejected, and incorrect matches during testing so
    the threshold can be tuned empirically.

### 8.3 Suggested scoring

Implement an explainable scoring function, initially:

-   `alias_score`: RapidFuzz similarity from 0 to 100.
-   `intent_consistency`: whether action words in transcript agree with
    candidate intent.
-   `device_consistency`: whether spoken device words agree with
    candidate device type.
-   `target_consistency`: whether spoken target agrees with the
    candidate target.

A candidate can be accepted only when:

1.  It is enabled.
2.  `alias_score >= COMMAND_SIMILARITY_THRESHOLD`.
3.  No negation is detected.
4.  No conflicting action indicator is detected.
5.  Device type is consistent.
6.  Target is resolved to exactly one valid device, or a documented safe
    default policy applies.
7.  There is no unresolved ambiguity with a competing candidate.

The overall score may be returned for diagnostics. Do not average away a
hard safety failure. A high alias score must never override a negation
or opposite-action conflict.

### 8.4 Example outcomes

  --------------------------------------------------------------------------
  Transcript                             Expected result
  -------------------------------------- -----------------------------------
  `Bật đèn phòng khách`                  Accept `LIGHT_ON`, `living_room`

  `Mở đèn phòng khách lên`               Accept `LIGHT_ON`, `living_room`

  `Bật cái đèn ở phòng khách giúp tôi`   Accept if alias/intent/target
                                         resolve

  `Tắt đèn phòng khách`                  Accept `LIGHT_OFF`, `living_room`

  `Đừng bật đèn phòng khách`             Reject `NEGATION_DETECTED`

  `Không tắt quạt`                       Reject `NEGATION_DETECTED`

  `Bật đèn phòng khách hay tắt đèn?`     Reject `AMBIGUOUS_COMMAND`

  `Bật đèn phòng khách` when no such     Reject `TARGET_NOT_FOUND`
  device exists                          

  `Bật đèn` when multiple lights exist   Reject `AMBIGUOUS_TARGET`
  and no default target                  

  Random speech unrelated to catalogue   Reject `NO_MATCH`
  --------------------------------------------------------------------------

### 8.5 Initial threshold

Set:

``` env
COMMAND_SIMILARITY_THRESHOLD=80
```

This value is a starting point for prototype testing, not a measured
accuracy claim. The team must test real recordings from the intended
microphone and adjust the threshold based on Recall, False Acceptance
Rate, and opposite-action error rate.

------------------------------------------------------------------------

## 9. Structured command contract

Create Pydantic schemas in `backend/app/schemas/voice.py`.

### 9.1 Resolved command

A resolved command should carry at least:

``` json
{
  "recognized_text": "Bật đèn phòng khách lên",
  "normalized_text": "bat den phong khach len",
  "command_id": "light_on",
  "intent": "LIGHT_ON",
  "action": "turn_on",
  "device_type": "light",
  "target": "living_room",
  "device_id": "resolved-from-existing-registry",
  "similarity_score": 93.5,
  "threshold": 80,
  "accepted": true,
  "reason": "MATCH_ACCEPTED"
}
```

`device_id` above is illustrative. The implementation must resolve it
from the actual backend registry/configuration.

### 9.2 Processing result fields

Required response fields:

-   `accepted: bool`
-   `reason: str`
-   `recognized_text: str`
-   `normalized_text: str`
-   `command_id: str | None`
-   `intent: str | None`
-   `action: str | None`
-   `device_type: str | None`
-   `target: str | None`
-   `device_id: str | None`
-   `similarity_score: float | None`
-   `threshold: float`
-   `alternatives: list` (optional, limited to a few diagnostic
    candidates)
-   `execution`: optional execution result

Keep transcript, processing decision, and execution result distinct. A
command may be understood but not executed.

### 9.3 Rejection reason enum

Use stable machine-readable values:

-   `NO_SPEECH`
-   `EMPTY_TRANSCRIPT`
-   `NO_MATCH`
-   `BELOW_THRESHOLD`
-   `NEGATION_DETECTED`
-   `CONFLICTING_ACTION`
-   `AMBIGUOUS_COMMAND`
-   `AMBIGUOUS_TARGET`
-   `TARGET_REQUIRED`
-   `TARGET_NOT_FOUND`
-   `DEVICE_DISABLED`
-   `CATALOGUE_ERROR`
-   `SERVICE_NOT_READY`
-   `EXECUTION_FAILED`
-   `AUDIO_TIMEOUT`
-   `AUDIO_DEVICE_ERROR`
-   `MODEL_LOAD_FAILED`

Human-readable Vietnamese messages may be returned separately for UI
display.

------------------------------------------------------------------------

## 10. Existing backend integration

### 10.1 Integration boundary

The AI layer must call the existing `DeviceService`.

Required flow:

``` text
VoiceService
    ├── AudioCapture
    ├── WakeWordDetector
    ├── CommandRecorder
    ├── SpeechRecognizer
    └── CommandProcessor
              │
              ▼
       Resolved VoiceCommand
              │
              ▼
     Existing DeviceService
              │
              ▼
     Existing DeviceRegistry
              │
              ▼
        Existing Device
```

Do not create a parallel `VoiceDeviceController`, direct GPIO
controller, or second registry.

### 10.2 Required agent inspection before implementation

Before writing integration code, inspect:

-   `backend/app/main.py`
-   `backend/app/api/routes.py`
-   `backend/app/services/device_service.py`
-   `backend/app/devices/base.py`
-   `backend/app/devices/registry.py`
-   `backend/app/devices/mock_device.py`
-   `backend/app/schemas/device.py`
-   `backend/app/core/config.py`
-   existing tests and device configuration

Document the actual `DeviceService` public methods and device command
schema in the implementation PR.

### 10.3 Adapter rule

If the existing DeviceService method signature does not directly match
the AI command contract, implement a small adapter inside `VoiceService`
or a dedicated mapper. Do not modify the device service's public
contract unless necessary.

The adapter must:

1.  Map `device_id` and `action` to the existing backend request format.
2.  Validate that the target exists.
3.  Call the existing service method.
4.  Convert the backend result to a voice execution result.
5.  Preserve and report backend errors.

### 10.4 Mock-first integration

The first end-to-end test must run with the existing mock hardware mode.

-   A successful voice command should call the mock device through the
    existing backend service.
-   Tests must assert the mock device received the expected action and
    target.
-   Do not require real GPIO to run CI or local unit tests.
-   Real hardware mode must be opt-in and use the existing hardware
    configuration.

### 10.5 No execution in text-only test mode by default

`POST /api/voice/process` is for testing transcript processing. It must
default to `execute=false`.

Only an explicit `execute=true` may request execution, and the backend
must still apply every validation rule. This prevents a frontend or test
tool from accidentally toggling hardware while testing fuzzy matching.

------------------------------------------------------------------------

## 11. Voice service lifecycle and concurrency

### 11.1 Lifecycle

Create one `VoiceService` instance and manage it through the FastAPI
application lifespan.

-   Initialize service dependencies once.
-   Do not load the model or open the microphone at module import time.
-   Support explicit start and stop.
-   On application shutdown, stop the listener, cancel/await background
    tasks, close the audio stream, and release resources.
-   `VOICE_AUTO_START` defaults to `false` so developers can start the
    service explicitly while testing.

### 11.2 Concurrency requirements

-   Only one voice listener may own the microphone at a time.
-   Repeated `start` requests must be idempotent or return a clear
    `already_running` result.
-   `stop` must be safe when the service is already stopped.
-   Use an async lock or equivalent guard around start/stop.
-   Do not block the FastAPI event loop with STT inference or blocking
    audio operations.
-   Keep a bounded command-history buffer; do not allow unbounded memory
    growth.
-   Avoid multiple Uvicorn workers for a process that owns a physical
    microphone. Document/run with one worker unless a separate dedicated
    audio process is designed.

### 11.3 Error recovery

Recoverable audio/transcription errors should be logged and reflected in
service status, then the listener may return to `WAITING_WAKE_WORD` if
safe. Fatal initialization errors must leave the service in `ERROR` and
expose a useful message without crashing unrelated backend APIs.

------------------------------------------------------------------------

## 12. FastAPI API contract

Use the existing API prefix and route conventions discovered in the
repository. The following paths are the intended voice routes; if the
project already has a conflicting prefix, preserve the existing
convention and document the final paths.

### 12.1 `GET /api/voice/status`

Returns current state and readiness.

Example:

``` json
{
  "enabled": true,
  "running": true,
  "state": "WAITING_WAKE_WORD",
  "model_loaded": true,
  "microphone_available": true,
  "last_error": null,
  "wake_word": "hey berry"
}
```

### 12.2 `POST /api/voice/start`

Starts the background listener.

Example success:

``` json
{
  "success": true,
  "state": "WAITING_WAKE_WORD",
  "message": "Voice listener started"
}
```

If already running, return a deterministic idempotent response or a
documented conflict response.

### 12.3 `POST /api/voice/stop`

Stops the listener and releases the microphone.

Example:

``` json
{
  "success": true,
  "state": "STOPPED",
  "message": "Voice listener stopped"
}
```

### 12.4 `GET /api/voice/commands`

Returns enabled command definitions suitable for the frontend/test UI.
Do not expose internal file paths or sensitive runtime details.

### 12.5 `POST /api/voice/process`

Processes supplied text without microphone or STT.

Request:

``` json
{
  "text": "Hãy bật đèn phòng khách lên",
  "execute": false
}
```

Response: structured processing result from Section 9.

Rules:

-   `text` is required and must have a reasonable maximum length (for
    example, 500 characters).
-   `execute` defaults to `false`.
-   If `execute=true`, route through the same `VoiceService` execution
    method as live voice.
-   Never duplicate command-matching logic in the API route.

### 12.6 `GET /api/voice/history`

Returns a bounded list of recent voice interactions, newest first.

Each item should include:

-   timestamp
-   original transcript
-   accepted/rejected
-   reason
-   resolved intent/action/target
-   similarity score
-   execution success/failure

Do not store raw audio in history by default.

### 12.7 HTTP error behavior

Use the project's existing FastAPI error conventions. At minimum
distinguish:

-   service not ready
-   invalid request
-   unavailable microphone
-   model load failure
-   command rejected
-   backend execution failure

A rejected command is a valid processing result and should not
automatically become an HTTP 500.

------------------------------------------------------------------------

## 13. Configuration

Extend the existing Pydantic Settings model in
`backend/app/core/config.py`. Do not create a second independent
settings system.

Suggested `.env` values:

``` env
# Voice feature
VOICE_ENABLED=true
VOICE_AUTO_START=false

# Audio
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_INPUT_DEVICE=
WAKE_CHUNK_SECONDS=3
COMMAND_SILENCE_DURATION=1.2
COMMAND_MAX_DURATION=15
COMMAND_MIN_DURATION=0.4
AUDIO_SILENCE_THRESHOLD=0.012

# Wake Word
WAKE_WORD_ENABLED=true
WAKE_WORDS=hey berry,hey barry,hey beri,hey very,hey be ri
WAKE_WORD_COOLDOWN_SECONDS=2

# STT
STT_MODEL=tiny
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
STT_LANGUAGE=en
STT_BEAM_SIZE=1
STT_VAD_FILTER=false
STT_MODEL_CACHE_DIR=models

# Command processing
COMMAND_SIMILARITY_THRESHOLD=80
COMMAND_CATALOG_PATH=hardware/configs/commands.json
VOICE_HISTORY_LIMIT=50
```

Requirements:

-   Keep defaults compatible with current project settings.
-   Validate ranges (sample rate positive, channel count supported,
    threshold between 0 and 100, durations positive).
-   Resolve relative paths from a stable project root, not the current
    shell working directory.
-   Document environment variables in `.env.example`.
-   Never commit `.env`, downloaded models, or captured user audio.

------------------------------------------------------------------------

## 14. Dependencies and platform strategy

### 14.1 Dependency separation

Keep current base backend dependencies lightweight.

Add an AI/voice requirements file, for example:

`backend/requirements/ai.txt`

Suggested contents:

``` text
faster-whisper
sounddevice
numpy
scipy
rapidfuzz
```

Pin compatible versions after testing. Avoid arbitrary upgrades to
existing FastAPI/Pydantic packages.

Update the development installation instructions to install both the
existing development requirements and `ai.txt` when voice development is
needed.

For Raspberry Pi, validate wheels and native runtime compatibility
before adding packages to `raspberry-pi.txt`. If dependencies differ by
platform, use a separate `ai-raspberry-pi.txt` or documented platform
markers. Do not make the non-AI backend fail to install because an
optional audio dependency is missing.

### 14.2 Windows development

-   Test microphone enumeration and recording on Windows.
-   If `sounddevice` cannot find a microphone, expose the device list
    and a clear configuration error.
-   Make input device selectable through `AUDIO_INPUT_DEVICE`.
-   Do not hard-code a Windows-only device index.

### 14.3 Raspberry Pi deployment

Target: Raspberry Pi 4, 4 GB RAM, Debian 12 Bookworm, ARM64, Python
3.11.

-   Start with `tiny`, CPU, `int8`.
-   Measure model load time, transcription latency, CPU, and memory.
-   Avoid loading multiple large models.
-   Ensure the model is cached locally after first download; provide a
    documented offline deployment procedure if the Pi has no Internet.
-   Check microphone permissions and ALSA/PulseAudio device
    availability.
-   Confirm audio capture works independently before debugging STT.
-   Keep the existing backend operational if AI dependencies are not
    installed or `VOICE_ENABLED=false`.

------------------------------------------------------------------------

## 15. Logging, observability, and privacy

Log structured events for:

-   voice service start/stop
-   model load success/failure
-   microphone open/close/error
-   Wake Word detection
-   command transcription
-   command accepted/rejected and reason
-   backend action result
-   recoverable/fatal errors

Logging rules:

-   Include timestamps and state transitions.
-   Include transcript text only at an appropriate log level; allow it
    to be disabled or redacted.
-   Do not log raw audio bytes.
-   Do not store recordings by default.
-   Do not log secrets or environment variable values.
-   Keep command history bounded.
-   Make debug logging optional because continuous transcript logging
    can produce large logs.

------------------------------------------------------------------------

## 16. Testing plan

All text-processing tests must run without a microphone, Whisper model,
or Raspberry Pi.

### 16.1 Unit tests --- normalizer

Test:

-   uppercase/lowercase
-   Vietnamese diacritics
-   `đ` normalization
-   punctuation
-   repeated whitespace
-   empty input
-   preservation/detection of negation markers

### 16.2 Unit tests --- matcher

Test:

-   exact alias
-   accentless input
-   small typo
-   word-order variation
-   filler words
-   score below threshold
-   disabled command
-   duplicate/conflicting aliases
-   close competing candidates

### 16.3 Unit tests --- intent/target resolver

Test:

-   on/off action
-   light/fan device type
-   living room/bedroom/kitchen target
-   missing target
-   unknown target
-   multiple possible devices
-   conflicting action words
-   negation scope uncertainty

### 16.4 Unit tests --- command processor

Test the examples in Section 8.4 and verify both the structured result
and rejection reason.

### 16.5 Integration tests --- existing backend

Using the existing mock device:

-   accepted `LIGHT_ON` calls the correct existing DeviceService method.
-   accepted `LIGHT_OFF` calls the correct method.
-   target maps to the correct existing device ID.
-   rejected command never calls DeviceService.
-   `execute=false` never calls DeviceService.
-   backend exception is returned as `EXECUTION_FAILED`.
-   no direct GPIO import/call exists in AI modules.

### 16.6 API tests

Test:

-   status while stopped
-   start
-   repeated start
-   stop
-   repeated stop
-   commands catalogue
-   process endpoint with execute false
-   process endpoint with execute true using mock device
-   history ordering and limit
-   service unavailable and model/microphone failure responses

### 16.7 Audio/STT manual tests

On Windows first:

1.  Enumerate input devices.
2.  Record a short WAV.
3.  Verify sample rate/channel count/duration.
4.  Run STT on the WAV.
5.  Test Wake Word with quiet and normal speech.
6.  Test command recording with silence.
7.  Test a Wake Word followed immediately by a command.
8.  Test background noise and different speaking distances.

Then repeat on Raspberry Pi.

### 16.8 Acceptance dataset

Create a small version-controlled text test dataset (not raw personal
recordings) with at least:

  Input                              Expected
  ---------------------------------- -------------------------------------
  Bật đèn phòng khách                LIGHT_ON / living_room
  Mở đèn phòng khách                 LIGHT_ON / living_room
  Bật cái đèn ở phòng khách lên      LIGHT_ON / living_room
  Làm ơn bật đèn phòng khách         LIGHT_ON / living_room
  Tắt đèn phòng khách                LIGHT_OFF / living_room
  Mở quạt phòng ngủ                  FAN_ON / bedroom
  Bật quạt phòng ngủ                 FAN_ON / bedroom
  Tắt quạt phòng ngủ                 FAN_OFF / bedroom
  Đừng bật đèn phòng khách           Reject / NEGATION_DETECTED
  Không tắt quạt phòng ngủ           Reject / NEGATION_DETECTED
  Bật đèn phòng khách hay tắt đèn?   Reject / AMBIGUOUS_COMMAND
  Mở cửa sổ                          Reject / NO_MATCH unless configured

### 16.9 Metrics

Measure:

-   **Recall:** correctly accepted supported commands / all supported
    command examples.
-   **False Acceptance Rate (FAR):** unsupported or unsafe utterances
    accepted / all unsupported or unsafe utterances.
-   **Opposite-action error rate:** utterances resolved to the opposite
    action / all evaluated utterances.
-   **Target accuracy:** correct target / accepted commands.
-   **STT latency:** audio end to transcript result.
-   **End-to-end latency:** end of command speech to backend result.
-   CPU and memory on Raspberry Pi.

Initial goals for the prototype:

-   Text matcher recall: at least 90% on the curated supported-command
    test set.
-   Opposite-action errors: 0 in the curated safety test set.
-   Negation cases: 100% rejected in the curated test set.
-   Target accuracy: 100% in the deterministic test set.
-   FAR should be measured and reported; do not claim a value without
    test results.

These are acceptance targets for the test set, not claims of real-world
accuracy.

------------------------------------------------------------------------

## 17. Frontend integration boundary

The frontend already exists. Do not rebuild it.

Backend agents must expose the API contract in Section 12 and ensure
OpenAPI documents it.

Frontend agents (only if explicitly assigned) may then connect existing
UI components to:

-   `GET /api/voice/status`
-   `POST /api/voice/start`
-   `POST /api/voice/stop`
-   `GET /api/voice/commands`
-   `GET /api/voice/history`

The UI should be able to display:

-   voice service state
-   microphone/model readiness
-   latest recognized transcript
-   accepted/rejected result and reason
-   resolved device/action
-   execution result
-   recent history

Do not make frontend logic responsible for fuzzy matching, Wake Word
detection, or device execution.

------------------------------------------------------------------------

## 18. Implementation work packages for agents

Agents should work in the following order. Keep changes in small
reviewable commits/PRs.

### Agent 1 --- Command processing core

**Files:** `backend/app/ai/command/*`, `backend/app/schemas/voice.py`,
`hardware/configs/commands.json`, unit tests.

Tasks:

1.  Implement normalizer.
2.  Implement catalogue loader and validation.
3.  Implement RapidFuzz matcher.
4.  Implement negation/conflict detection.
5.  Implement target and intent resolver.
6.  Implement command processor.
7.  Add deterministic unit tests.
8.  Do not integrate microphone or DeviceService in this work package.

**Definition of done:** Text input can be converted into a structured
accepted/rejected result with deterministic tests.

### Agent 2 --- Audio and STT

**Files:** `backend/app/ai/speech/*`, optional requirements, audio
tests/manual guide.

Tasks:

1.  Implement audio device discovery and continuous capture.
2.  Implement buffered/overlapping Wake Word detection.
3.  Implement command recording with silence and max-duration rules.
4.  Implement Faster-Whisper recognizer with one-time model loading.
5.  Add lifecycle cleanup and recoverable error handling.
6.  Add a WAV-based STT test path so tests do not require a live
    microphone.
7.  Verify Windows first; document Raspberry Pi-specific requirements.

**Definition of done:** Given a WAV or microphone input, the module can
detect Wake Word, record one command, and return a Vietnamese transcript
without interacting with devices.

### Agent 3 --- Backend integration and API

**Files:** `backend/app/services/voice_service.py`,
`backend/app/api/voice_routes.py`, existing `main.py`/router/settings
only where needed, API/integration tests.

Tasks:

1.  Inspect and document the actual DeviceService and device registry
    APIs.
2.  Build VoiceService around the command processor and speech pipeline.
3.  Add safe adapter from resolved command to existing DeviceService.
4.  Manage VoiceService in FastAPI lifespan.
5.  Add status/start/stop/commands/process/history endpoints.
6.  Make text-only processing non-executing by default.
7.  Add mock-device integration tests.
8.  Ensure existing routes and tests still pass.

**Definition of done:** A text command can be processed through the API
and, only when explicitly requested, execute through the existing mock
DeviceService.

### Agent 4 --- Integration QA / deployment

Tasks:

1.  Review the merged implementation against this spec.
2.  Run all existing backend tests.
3.  Run AI unit/API/integration tests.
4.  Test microphone and STT on Windows.
5.  Deploy to Raspberry Pi and measure latency/CPU/RAM.
6.  Verify start/stop and shutdown release the microphone.
7.  Update `.env.example`, README, and deployment instructions.
8.  Report known limitations and measured results.

**Definition of done:** Existing backend remains functional; AI can be
started, tested, and stopped; mock integration passes; Raspberry Pi
smoke test results are documented.

### Parallelization rules

-   Agent 1 can work independently of Agent 2.
-   Agent 3 should define schemas and integration interfaces early, then
    integrate Agent 1 and Agent 2 outputs.
-   Agent 4 should prepare test cases early but perform final
    verification after integration.
-   Do not allow multiple agents to independently edit the same central
    files (`main.py`, `config.py`, shared schemas) without coordination.
-   The integration lead owns final API compatibility and merges.

------------------------------------------------------------------------

## 19. Required deliverables

The implementation is complete only when all of the following exist:

-   [ ] `backend/app/ai/command/` implemented and unit-tested.
-   [ ] `hardware/configs/commands.json` created and validated.
-   [ ] `backend/app/ai/speech/` implemented.
-   [ ] Optional AI dependency file created and documented.
-   [ ] `backend/app/schemas/voice.py` created.
-   [ ] `backend/app/services/voice_service.py` integrated with the
    existing DeviceService.
-   [ ] `backend/app/api/voice_routes.py` registered with FastAPI.
-   [ ] Existing application lifecycle starts/stops VoiceService
    correctly.
-   [ ] `.env.example` includes voice/STT/command settings.
-   [ ] Text-only endpoint does not execute by default.
-   [ ] Mock hardware integration tests pass.
-   [ ] Existing backend tests continue to pass.
-   [ ] Windows microphone/STT test procedure documented.
-   [ ] Raspberry Pi smoke-test results and resource measurements
    documented.
-   [ ] README updated with install/start/stop/troubleshooting
    instructions.

------------------------------------------------------------------------

## 20. Final engineering decisions

1.  **STT:** Faster-Whisper `tiny`, CPU, `int8`, English by default.
2.  **Wake Word:** Initially Whisper-based rolling-window detection for
    a working prototype; keep it replaceable with a dedicated
    keyword-spotting model later.
3.  **Command understanding:** deterministic rules + RapidFuzz, no
    external LLM.
4.  **Normalization:** remove diacritics for matching, but preserve
    original transcript and negation semantics.
5.  **Matching threshold:** configurable, initial value 80/100.
6.  **Recall policy:** favor recognizing natural variations, but
    hard-reject negation, opposite-action conflicts, and unresolved
    targets.
7.  **Device execution:** only through the existing
    DeviceService/Registry/Device architecture.
8.  **Runtime:** one VoiceService and one microphone owner per backend
    process.
9.  **Testing:** text-processing and mock integration tests must run
    without hardware or model downloads.
10. **Frontend:** existing frontend remains; it consumes the new voice
    API rather than implementing AI logic.

**The first milestone is not "AI controls a real GPIO device." The first
milestone is: an English text command is correctly resolved,
validated, and executed through the existing mock DeviceService. After
that is stable, connect microphone/STT and finally test real Raspberry
Pi hardware.**
