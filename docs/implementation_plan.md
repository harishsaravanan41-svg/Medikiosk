# MediKiosk Voice/Text AI System Implementation Plan

This plan outlines the architecture and implementation of the **MediKiosk Voice/Text AI System** with the dual-output workflow (**Text display + TTS audio playback**), live voice waveform visualizer, and local JSON persistence.

## Architecture & Workflow Overview

```
                         PATIENT
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
        ⌨️ TEXT INPUT                 🎤 VOICE INPUT
              │                           │
              │                           ▼
              │                    ┌──────────────┐
              │                    │     STT      │
              │                    │ Speech→Text  │
              │                    │   Whisper    │
              │                    └──────┬───────┘
              │                           │
              └──────────────┬────────────┘
                             │
                             ▼
                   ┌──────────────────┐
                   │   CONVERSATION   │
                   │     HISTORY      │
                   └────────┬─────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │    LOCAL QWEN    │
                   │ Qwen 2.5 1.5B    │
                   └────────┬─────────┘
                            │
                     AI generates
                       response
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
       ┌─────────────────┐      ┌─────────────────┐
       │   TEXT OUTPUT   │      │       TTS       │
       │                 │      │  Text → Speech  │
       │ Display in UI   │      │      Piper      │
       └─────────────────┘      └────────┬────────┘
                                         │
                                         ▼
                                    🔊 PATIENT
```

---

## Key Features & Components

1. **Dual-Input Pipeline:**
   - **Voice Input:** Browser captures patient audio (Web Audio API / MediaRecorder), sends audio blob to Flask backend `/api/stt` or `/api/chat/voice` where Whisper transcribes it into text.
   - **Text Input:** Patient types directly into the kiosk interface, bypassing STT.

2. **Dual-Output Pipeline (Simultaneous):**
   - **Text Output:** Markdown-rendered AI triage response bubble in UI.
   - **TTS Output:** Audio synthesized via Piper (with fallback support for local engines/gTTS) returned as streaming audio or base64 audio URL that auto-plays with synchronized waveform visualizer.

3. **Live Audio Waveform Visualizer ("Chatbot Wave"):**
   - **Mic Listening Wave:** Real-time Web Audio API `AnalyserNode` rendering active voice amplitude waves while the patient speaks.
   - **AI Speaking Wave:** Pulsing, organic waveform animation rendered on HTML5 Canvas while Qwen's TTS response is playing through speakers.

4. **Local Qwen 2.5 Engine:**
   - Multi-mode engine connector:
     - **Mode 1 (Local Server / Ollama / LM Studio / vLLM / OpenAI-compatible endpoint):** e.g. `http://localhost:11434/v1` or `http://127.0.0.1:1234/v1`.
     - **Mode 2 (Local HuggingFace / Transformers / API Key):** Configurable in `.env` or settings modal.
     - **Mode 3 (Mock / Fallback Medical Engine):** Ensures the kiosk works instantly even before the user starts their local Qwen instance.
   - Built-in medical triage system prompt (empathic, structured questions, urgent symptom flagging, summary generation).

5. **Piper TTS Engine:**
   - Piper execution wrapper (supports direct Piper binary / python ONNX runtime / fallback to gTTS / Web Speech API) to guarantee audio generation across environments.
   - Audio caching for fast response times.

6. **JSON Database & Session Persistence:**
   - `data/patients.json`: Patient profiles and visit history.
   - `data/sessions/`: Full conversation logs with timestamps, input modality (voice vs text), and triage assessments.
   - `data/triage_records.json`: Structured triage reports (chief complaint, duration, severity, urgency category: Low / Moderate / Urgent / Emergency).

7. **Kiosk UI/UX:**
   - Modern medical glassmorphism aesthetic with high contrast accessibility.
   - Large touch-friendly kiosk buttons (Voice push-to-talk, Text mode toggle, Emergency SOS button, Language selector).
   - Live Patient Triage Sidebar showing real-time extracted symptoms and triage badge.
   - Audio playback controls (replay speech, mute/unmute, speed control).
   - Kiosk Admin / Settings drawer to adjust Qwen API keys, endpoint URLs, Piper voices, and view JSON logs.

---

## Proposed Project Structure

```
Medikiosk/
├── app.py                     # Flask application entry point & API routes
├── config.py                  # Environment config & constants
├── requirements.txt           # Python dependencies
├── .env.example               # Template environment configuration
│
├── services/
│   ├── __init__.py
│   ├── stt_service.py         # Whisper STT transcription service
│   ├── llm_service.py         # Qwen 2.5 model connector (Local/Ollama/API)
│   ├── tts_service.py         # Piper TTS synthesis & audio manager
│   ├── db_service.py          # JSON database manager for triage & history
│   └── triage_service.py      # Symptom extraction & triage categorization
│
├── data/                      # Local JSON storage directory
│   ├── patients.json
│   ├── triage_records.json
│   └── sessions/
│
├── static/
│   ├── css/
│   │   └── style.css          # Medical kiosk design & responsive styling
│   ├── js/
│   │   ├── app.js             # Main controller & state management
│   │   ├── audio_recorder.js  # Mic recording & Web Audio API handler
│   │   ├── visualizer.js      # Canvas waveform visualizer (Mic & TTS AI wave)
│   │   └── api.js             # Fetch wrappers for dual-output endpoints
│   ├── audio/                 # Generated TTS audio cache
│   └── assets/                # Icons and visual assets
│
└── templates/
    └── index.html             # Single-page interactive Kiosk interface
```

---

## API Endpoints Design

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the main kiosk UI |
| `POST` | `/api/chat/text` | Accepts text input -> Qwen LLM -> returns `{ text, audio_url, triage_info }` |
| `POST` | `/api/chat/voice` | Accepts audio file -> Whisper STT -> Qwen LLM -> Piper TTS -> returns `{ transcription, text, audio_url, triage_info }` |
| `POST` | `/api/stt` | Transcribes audio file only |
| `POST` | `/api/tts` | Generates Piper TTS audio for any text |
| `GET` | `/api/audio/<filename>` | Serves generated TTS audio file |
| `GET` | `/api/triage/history` | Fetches recent triage sessions from JSON database |
| `POST` | `/api/session/reset` | Resets current patient session and generates final triage summary |
| `GET` | `/api/config` / `POST` | Get/update runtime settings (Qwen endpoint, API keys, Piper voice) |

---

## Verification Plan

### Automated / Server Tests
1. Test Whisper STT audio transcription with sample audio files (`python -m pytest` or custom test runner `test_pipeline.py`).
2. Test Qwen LLM connector with local endpoint and mock fallback.
3. Test Piper / TTS engine audio file generation and URL serving.
4. Test JSON database reads and writes.

### Manual / Browser Verification
1. Open Kiosk UI at `http://127.0.0.1:5000`.
2. Test Text Input (`"I have a fever since yesterday"`) -> verify text response displays + TTS audio plays + AI soundwave animates.
3. Test Voice Input (Mic push-to-talk) -> verify live input wave -> Whisper transcription -> Qwen response -> Piper TTS audio playback.
4. Verify JSON logs updated in `data/triage_records.json`.
