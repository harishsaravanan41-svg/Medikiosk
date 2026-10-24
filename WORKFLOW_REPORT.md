# MediKiosk AI — Workflow & Architecture Report

**Project:** MediKiosk AI — Dynamic Conversational Assistant & Background Triage
**Status:** Fully Aligned with ChatGPT-Style Conversational Architecture

---

## 1. System Map

| Layer | Files | Responsibility |
|---|---|---|
| **Frontend** | `app/templates/index.html`, `app/static/js/app.js`, `api.js`, `audio_recorder.js`, `visualizer.js`, `css/style.css` | UI, voice/text capture, dynamic audio playback, API transmission |
| **API** | `app/routes/chat.py`, `audio.py`, `session.py`, `config_routes.py` | Unified REST endpoints |
| **AI** | `app/services/llm_service.py` | ChatGPT-style general-purpose dialogue + decoupled clinical extraction |
| **Speech** | `app/services/stt_service.py` (Whisper with Auto-Language Detection), `tts_service.py` (Piper / gTTS / pyttsx3) | Multilingual voice in/out |
| **Logic & Safety** | `app/services/triage_service.py`, `db_service.py` | Deterministic safety floor, background structured facts, JSON persistence |

---

## 2. End-to-End User Workflows

### Flow A — Text Input (ChatGPT-Style)
```text
USER TEXT → Chat UI → POST /api/chat/text → Qwen LLM (Full History) → Dynamic AI Response → Chat UI Text + TTS Voice → USER
```

### Flow B — Voice Input (Dynamic Multilingual STT & TTS)
```text
USER VOICE → Microphone → Whisper STT (Auto-Detection) → POST /api/chat/voice → Qwen LLM (Full History) → Dynamic AI Response → Chat UI Text + TTS Voice → USER
```

---

## 3. Decoupled Responsibilities

```text
                    USER MESSAGE (Text / Voice)
                                 │
                      ┌──────────┴──────────┐
                      ▼                     ▼
             CONVERSATIONAL QWEN       CLINICAL EXTRACTOR
             (Full Dynamic Chat)       (Background JSON)
                      │                     │
                      ▼                     ▼
               Natural Response      Structured Facts
                      │                     │
                      ▼                     ▼
                 PATIENT / USER      DOCTOR DASHBOARD
```

---

## 4. Key Fixes Applied

1. **Endpoint Alignment & URL Fix**:
   - `.env` configured with `QWEN_API_URL=http://localhost:8000/v1` and `QWEN_API_BASE=http://localhost:8000/v1`.
   - `llm_service.py` evaluates exact endpoint as `http://localhost:8000/v1/chat/completions` with universal schema payload (`message`, `messages`, `system_prompt`, `history`).
2. **True ChatGPT-Style Prompting**:
   - Zero hardcoded questionnaire sequences or symptom forcing.
   - Handles programming queries (`"i need python code"`), math, jokes, translations, greetings, and medical inquiries.
3. **Multilingual Auto-Detection**:
   - Whisper STT auto-detects English, Tamil, Hindi, Telugu, Malayalam, Kannada, etc.
   - Qwen dynamically responds in the user's active language and supports mid-dialogue switching.
4. **All Tests Passed**:
   - `Ran 6 tests in 24.8s -> OK (Exit code 0)`