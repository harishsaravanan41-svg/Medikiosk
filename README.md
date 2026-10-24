# MediKiosk AI 🏥

> **Virtual Multilingual Clinical Triage & Reception Assistant**  
> Powered by **Qwen 2.5 LLM**, **OpenAI Whisper STT**, and **Piper / gTTS Text-to-Speech**.

---

## 🌟 Overview

**MediKiosk AI** is an intelligent, voice-and-text clinical assistant designed for hospital reception and kiosk deployments. It provides a natural, ChatGPT-style conversational experience with automatic multilingual detection, zero hardcoded questionnaires, and decoupled background clinical extraction for doctor dashboards.

```
                    ┌────────────────────────┐
                    │  USER (Text / Voice)   │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Whisper STT (Auto)    │
                    │  or Direct Text Input  │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Conversation Manager  │
                    │  (Multi-Turn History)  │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │       Qwen LLM         │
                    │   Dynamic Response     │
                    └───────────┬────────────┘
                                │
                    ┌───────────┴────────────┐
                    ▼                        ▼
             Text Bubble               Piper/gTTS Speech
                    │                        │
                    ▼                        ▼
             Patient Screen            Patient Audio
                                             +
                                             │ (Background Extractor)
                                             ▼
                                      Doctor Dashboard
```

---

## 📁 Project Structure

```text
Medikiosk/
├── .env.example                     # Environment configuration template
├── .gitignore                       # Ignored cache, data, and virtual env files
├── README.md                        # Project documentation & guide
├── requirements.txt                 # Categorized dependencies
├── run.py                           # Application entry point
├── WORKFLOW_REPORT.md               # Technical architecture report
│
├── app/                             # Main Application Package
│   ├── __init__.py                  # Flask Application Factory
│   ├── config.py                    # Environment & configuration loader
│   ├── extensions.py                # Flask extensions (CORS, etc.)
│   │
│   ├── models/                      # Domain Data Models & Typed Schemas
│   │   ├── __init__.py
│   │   ├── patient.py               # Patient & ChatSession models
│   │   └── triage.py                # Clinical facts & TriageSummary models
│   │
│   ├── routes/                      # REST API Endpoints
│   │   ├── __init__.py
│   │   ├── chat.py                  # Text and Voice chat pipeline
│   │   ├── audio.py                 # Static TTS audio streaming
│   │   ├── session.py               # Session lifecycle & history
│   │   └── config_routes.py         # Runtime LLM & system configuration
│   │
│   ├── services/                    # Core Business & AI Logic
│   │   ├── __init__.py
│   │   ├── llm_service.py           # Qwen conversational AI & clinical fact extractor
│   │   ├── stt_service.py           # Whisper multilingual speech-to-text
│   │   ├── tts_service.py           # Piper, gTTS, and pyttsx3 speech synthesis
│   │   ├── triage_service.py        # Clinical triage & deterministic emergency safety
│   │   └── db_service.py            # Thread-safe JSON persistence storage
│   │
│   ├── static/                      # Frontend Assets
│   │   ├── css/
│   │   │   └── style.css            # Modern responsive medical kiosk design system
│   │   ├── js/
│   │   │   ├── api.js               # REST API Client
│   │   │   ├── audio_recorder.js    # Web Audio API microphone recorder
│   │   │   ├── visualizer.js        # HTML5 Canvas real-time waveform visualizer
│   │   │   └── app.js               # Main UI controller & state manager
│   │   ├── img/
│   │   │   └── doctor_banner.png    # Clinical UI banner photography
│   │   └── audio/                   # Generated audio cache
│   │
│   └── templates/                   # Web Templates
│       └── index.html               # Main Kiosk Interface
│
├── bin/                             # Third-Party Binaries (e.g. ffmpeg)
│
├── data/                            # Persistent JSON Storage
│   ├── patients.json
│   ├── triage_records.json
│   └── sessions/
│
├── scripts/                         # Automation & Launcher Scripts
│   ├── start_medikiosk.bat          # Windows one-click start script
│   ├── run_qwen_server.bat          # Local Qwen 2.5 API launcher
│   └── run_qwen_server.py           # Qwen FastAPI bootstrap script
│
└── tests/                           # Comprehensive Test Suite
    ├── __init__.py
    ├── test_conversational_workflow.py # Full multi-turn & ChatGPT-style workflow tests
    ├── test_endpoints.py            # API endpoint integration tests
    ├── test_multilingual.py         # Language handling tests
    ├── test_pipeline.py             # STT -> LLM -> TTS pipeline tests
    └── test_qwen_api.py             # Direct Qwen server tests
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Python 3.10+**
- **Microphone and Speakers** for voice input and audio playback.

### 2. Installation
```powershell
# Clone or navigate to the repository
cd c:\Users\Harish\Desktop\MEDIKIOSK\Medikiosk

# Create and activate virtual environment (optional)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and verify settings:
```env
PORT=5000
HOST=0.0.0.0
DEBUG=True

QWEN_MODE=custom_api
QWEN_API_URL=http://localhost:8000/v1
QWEN_API_BASE=http://localhost:8000/v1
QWEN_API_KEY=a2ff255b6f61cd453396b22f7ddeebf714d1fdcd73142b7e
QWEN_MODEL=qwen-compliance

WHISPER_MODEL=base
WHISPER_DEVICE=cpu
TTS_ENGINE=auto
```

### 4. Running the Application
```powershell
# Start the MediKiosk Server
python run.py
```
Open your browser and navigate to: **`http://localhost:5000`**

---

## 🧪 Running Automated Tests

Run the complete test suite:
```powershell
python -m unittest discover tests
```

To run conversational & fact extraction tests specifically:
```powershell
python -m unittest tests/test_conversational_workflow.py
```

---

## 🌐 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat/text` | Sends text message; returns dynamic AI text, TTS audio URL, and triage facts |
| `POST` | `/api/chat/voice` | Sends recorded voice audio (`.webm`); transcribes with Whisper and responds |
| `GET` | `/api/session/new` | Initializes a new patient check-in session |
| `GET` | `/api/session/<id>` | Retrieves session conversation history and triage report |
| `GET` | `/api/audio/<filename>` | Streams synthesized TTS audio |
| `GET/POST` | `/api/config` | Reads or updates runtime LLM and speech configurations |

---

## 🔒 Safety & Medical Disclaimer
*MediKiosk AI is an assistive pre-triage intake tool. It does not provide definitive medical diagnoses or prescribe medications. Life-threatening symptoms trigger immediate emergency alerts.*
