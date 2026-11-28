# Vietnamese voice responses

The backend owns audio playback (`VOICE_PLAYBACK_MODE=server`). Static
recordings belong under `assets/static/`; the manifest is
`assets/manifest.json`. Seven manifest clips are currently supplied:
`common.action_failed`, `common.action_success`,
`common.device_unavailable`, `common.ready`, `common.understood`,
`lights.turned_off`, and `lights.turned_on`. The other seven keys listed
below still need recordings; requests for those keys return a controlled
`unavailable` playback result. Do not add silent or generated placeholder
files as recordings.

## Remaining recording checklist

Record one clear, natural Vietnamese utterance for each remaining entry:
- `common/partial_success.wav` — “Một số thiết bị chưa thể thực hiện yêu cầu.”
- `fans/turned_on.wav` — “Đã bật quạt.”
- `fans/turned_off.wav` — “Đã tắt quạt.”
- `devices/all_turned_on.wav` — “Đã bật tất cả thiết bị.”
- `devices/all_turned_off.wav` — “Đã tắt tất cả thiết bị.”
- `sensors/unavailable.wav` — “Hiện tại chưa có dữ liệu cảm biến.”
- `sensors/stale.wav` — “Dữ liệu cảm biến đã cũ, vui lòng thử lại sau.”

Export each recording as mono, signed 16-bit PCM WAV at 16 kHz. Keep
clips short, consistently leveled, and free of long leading/trailing
silence. Preserve the stable response keys and relative paths in the
manifest. After recording, test every key using
`POST /api/voice/response/play/{response_key}` and verify
`audio_played=true`.

## Local Vietnamese TTS

The dynamic provider uses `pyttsx3` and the operating system's local
speech engine. It does not call a cloud service. It selects only a voice
whose installed metadata identifies Vietnamese (`vi`/`vi-VN`); an
English voice is never used as a fallback.

Install the Python adapter:

```bash
python -m pip install -r backend/requirements/tts.txt
```

On Raspberry Pi OS, install the local speech engine and inspect its
Vietnamese voices:

```bash
sudo apt update
sudo apt install -y espeak-ng libportaudio2 portaudio19-dev
espeak-ng --voices=vi
```

The presence of `espeak-ng` does not guarantee that a usable Vietnamese
voice is installed. Check the `tts_available` field at
`GET /api/voice/response/status`. If the selected operating-system
engine has no Vietnamese voice, install a compatible local voice for
that OS and set `VOICE_TTS_VOICE` to its exact voice name or ID. On
Windows, install a Vietnamese speech voice in Windows speech settings;
the current development machine only exposes English voices, so
Vietnamese TTS cannot be claimed as working there until one is installed.

Keep `MOCK_HARDWARE=true` during demo setup. Audio output and TTS are
optional; missing speakers, recordings, or voices must not prevent the
regular API from starting.
