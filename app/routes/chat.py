import re
from flask import Blueprint, request, jsonify, Response
from flask_socketio import emit
import threading
import os
import time
import json

from app.extensions import socketio
from app.services.db_service import db_service
from app.services.memory_service import memory_service
from app.services.stt_service import stt_service
from app.services.llm_service import llm_service, is_medical_message, detect_text_language
from app.services.tts_service import tts_service
from app.services.triage_service import triage_service

chat_bp = Blueprint("chat", __name__)


# ==========================================
# 1. Health Check Endpoint
# ==========================================

@chat_bp.route("/api/health/llm", methods=["GET"])
def health_llm():
    """
    Verifies if the Qwen LLM server is reachable and active.
    Returns JSON with status ('online' or 'offline'), model name, and latency in ms.
    """
    health_info = llm_service.check_health()
    status_code = 200 if health_info.get("status") == "online" else 503
    return jsonify(health_info), status_code


# ==========================================
# 2. Background Asynchronous Triage Worker
# ==========================================

def _run_triage_in_background(session_id: str, messages: list, language: str):
    """
    Runs clinical fact extraction and triage analysis ONLY if medical symptoms were discussed.
    Updates session and syncs structured clinical findings to active doctor encounter.
    """
    try:
        has_medical = any(is_medical_message(m.get("text", "")) for m in messages if m.get("sender") in ("patient", "user"))
        if not has_medical:
            return

        triage_info = triage_service.analyze_conversation(messages, language=language)
        session = db_service.get_session(session_id)
        if session:
            session["triage_summary"] = triage_info
            db_service.save_session(session_id, session)
            
            patient_id = session.get("patient_id", "P-1001")
            try:
                enc = db_service.create_or_get_active_encounter(patient_id, session_id=session_id)
                if enc and enc.get("encounter_id"):
                    report = memory_service.generate_doctor_report(patient_id, session_id=session_id)
                    db_service.update_ai_history(enc["encounter_id"], {
                        "chief_complaint": triage_info.get("chief_complaint") or "Clinical Check-in",
                        "hpi_json": json.dumps(triage_info),
                        "notes": report
                    })
            except Exception as enc_err:
                print(f"[Triage Background Encounter Sync] {enc_err}")
    except Exception as e:
        print(f"[Triage Background] Error: {e}")


# ==========================================
# 3. Duplicate Prevention & Unified AI Pipeline
# ==========================================

import hashlib

_recent_message_fingerprints = {}

def is_duplicate_user_message(session_id: str, text: str) -> bool:
    """Prevents processing the exact same user text twice within 3 seconds."""
    norm = " ".join((text or "").strip().lower().split())
    raw = f"{session_id}|{norm}"
    fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    now = time.time()

    # Clean old fingerprints
    for k in list(_recent_message_fingerprints.keys()):
        if now - _recent_message_fingerprints[k] > 10.0:
            _recent_message_fingerprints.pop(k, None)

    if fingerprint in _recent_message_fingerprints:
        if now - _recent_message_fingerprints[fingerprint] < 3.0:
            return True

    _recent_message_fingerprints[fingerprint] = now
    return False

def is_duplicate_ai_response(session_id: str, response_text: str) -> bool:
    """Checks if the generated response is identical to the immediately preceding AI response."""
    session = db_service.get_session(session_id)
    if not session:
        return False
    messages = session.get("messages", [])
    ai_messages = [m for m in messages if m.get("sender") == "ai"]
    if not ai_messages:
        return False
    previous = ai_messages[-1].get("text", "")
    norm_prev = " ".join((previous or "").strip().lower().split())
    norm_curr = " ".join((response_text or "").strip().lower().split())
    return norm_prev == norm_curr


def process_patient_message(
    sid: str,
    session_id: str,
    patient_id: str,
    user_text: str,
    language: str = "auto",
    modality: str = "text"
):
    """
    Unified AI pipeline for BOTH typed text and voice STT.
    1. Immediately emits 'response_start' for lowest latency.
    2. Streams tokens from Qwen with structured patient context.
    3. Prevents duplicate AI message bubbles.
    4. Offloads memory updates and clinical triage to background threads.
    """
    t_start = time.time()
    try:
        # Immediate start notification
        socketio.emit(
            "response_start",
            {
                "session_id": session_id,
                "patient_id": patient_id
            },
            to=sid
        )

        session = db_service.get_session(session_id)
        if not session:
            session_id = db_service.create_session(patient_id)
            session = db_service.get_session(session_id)

        messages = session.get("messages", [])

        user_memory = memory_service.get_relevant_memory(
            patient_id=patient_id,
            query=user_text
        )

        full_text_acc = []
        first_token_time = None

        # Real-time Qwen token streaming
        try:
            for token in llm_service.stream_conversational_response(
                messages,
                patient_id=patient_id,
                memory=user_memory,
                language=language
            ):
                if not token:
                    continue
                if first_token_time is None:
                    first_token_time = time.time()
                full_text_acc.append(token)

                socketio.emit(
                    "response_chunk",
                    {
                        "token": token,
                        "session_id": session_id,
                        "patient_id": patient_id
                    },
                    to=sid
                )
        except Exception as stream_err:
            print(f"[WS AI Stream Notice] {stream_err}")

        # Fallback if no tokens yielded
        if not full_text_acc:
            fallback_msg = llm_service._generate_conversational_fallback(
                user_text=user_text,
                patient_id=patient_id,
                messages=messages,
                language=language
            )
            for w in re.split(r'(\s+)', fallback_msg):
                if w:
                    full_text_acc.append(w)
                    socketio.emit(
                        "response_chunk",
                        {
                            "token": w,
                            "session_id": session_id,
                            "patient_id": patient_id
                        },
                        to=sid
                    )

        complete_text = "".join(full_text_acc).strip()
        if not complete_text:
            complete_text = "I have noted this for your consultation with the doctor."

        llm_total_ms = int((time.time() - t_start) * 1000)
        llm_first_token_ms = int((first_token_time - t_start) * 1000) if first_token_time else llm_total_ms

        # Save AI response to DB
        ai_message = db_service.append_message(
            session_id,
            sender="ai",
            text=complete_text,
            modality="stream"
        )

        # Emit completion immediately
        socketio.emit(
            "response_complete",
            {
                "session_id": session_id,
                "patient_id": patient_id,
                "message_id": ai_message.get("id"),
                "full_text": complete_text,
                "language": language,
                "telemetry": {
                    "llm_first_token_ms": llm_first_token_ms,
                    "llm_total_ms": llm_total_ms
                }
            },
            to=sid
        )

        # Asynchronously update persistent patient memory
        memory_service.extract_and_update_memory_async(
            patient_id=patient_id,
            session_id=session_id,
            user_text=user_text,
            ai_text=complete_text
        )

        # Asynchronously run clinical triage and doctor report sync
        updated_messages = db_service.get_session(session_id).get("messages", [])
        if any(is_medical_message(m.get("text", "")) for m in updated_messages if m.get("sender") in ("patient", "user")):
            t = threading.Thread(
                target=_run_triage_in_background,
                args=(session_id, updated_messages, language),
                daemon=True
            )
            t.start()

    except Exception as e:
        print(f"[AI PIPELINE ERROR] {repr(e)}")
        socketio.emit(
            "error",
            {
                "code": "ai_error",
                "message": "The AI could not generate a response. Please try again."
            },
            to=sid
        )

# Backward-compatibility alias
process_ai_message = process_patient_message


# ==========================================
# 4. WebSocket Real-Time Event Handlers
# ==========================================

@socketio.on("connect")
def handle_ws_connect():
    emit("connected", {"status": "connected", "message": "MediKiosk WebSocket Active"})


@socketio.on("disconnect")
def handle_ws_disconnect():
    pass


@socketio.on("chat_message")
def handle_ws_chat_message(data):
    """
    Handles typed chat messages over WebSocket.
    """
    from flask import request

    if not isinstance(data, dict):
        emit("error", {"code": "invalid_payload", "message": "Invalid message format."})
        return

    user_text = str(data.get("message", "")).strip()
    patient_id = data.get("patient_id", "P-1001")
    session_id = data.get("session_id")
    language = data.get("language", "auto")

    if not user_text:
        emit("error", {"code": "empty_message", "message": "Please enter a message."})
        return

    if not patient_id:
        emit("error", {"code": "missing_patient", "message": "Patient ID is required."})
        return

    if not session_id or not db_service.get_session(session_id):
        session_id = db_service.create_session(patient_id)

    # Check duplicate patient message
    if is_duplicate_user_message(session_id, user_text):
        print(f"[WS Notice] Duplicate user message dropped: '{user_text}'")
        return

    # Detect language dynamically
    detected_lang = detect_text_language(user_text, default="en")
    if language != "auto":
        detected_lang = language

    memory_service.record_patient_language(patient_id, detected_lang)

    # Save patient message
    db_service.append_message(
        session_id,
        sender="patient",
        text=user_text,
        modality="text"
    )

    # Start unified AI pipeline
    socketio.start_background_task(
        process_patient_message,
        request.sid,
        session_id,
        patient_id,
        user_text,
        detected_lang,
        "text"
    )


# In-memory voice PCM buffers per client SID
_voice_buffers = {}

@socketio.on("voice_start")
def handle_voice_start(data=None):
    from flask import request
    sid = getattr(request, "sid", "default")
    _voice_buffers[sid] = bytearray()
    emit("voice_ready", {"status": "recording_started"})


@socketio.on("voice_chunk")
def handle_voice_chunk(data):
    from flask import request
    sid = getattr(request, "sid", "default")
    if sid not in _voice_buffers:
        _voice_buffers[sid] = bytearray()

    if isinstance(data, (bytes, bytearray)):
        _voice_buffers[sid].extend(data)
    elif isinstance(data, dict) and "pcm" in data:
        pcm = data["pcm"]
        if isinstance(pcm, (bytes, bytearray)):
            _voice_buffers[sid].extend(pcm)


@socketio.on("voice_end")
def handle_voice_end(data=None):
    """
    Handles end of voice recording:
    1. STT Whisper transcription from in-memory 16kHz PCM buffer
    2. Appends patient voice message
    3. Emits 'voice_transcript' for immediate UI display
    4. Automatically starts the same AI pipeline as typed text
    """
    from flask import request
    sid = getattr(request, "sid", "default")
    pcm_bytes = bytes(_voice_buffers.pop(sid, b""))

    data = data or {}
    session_id = data.get("session_id")
    patient_id = data.get("patient_id", "P-1001")
    requested_lang = data.get("language", "auto")

    if not patient_id:
        emit("error", {
            "code": "missing_patient",
            "message": "Patient ID is required"
        })
        return

    if not pcm_bytes:
        emit("error", {
            "code": "no_speech",
            "message": "No speech detected. Please speak again."
        })
        return

    try:
        # 1. STT Whisper transcription
        stt_result = stt_service.transcribe_pcm_bytes(
            pcm_bytes,
            language=requested_lang
        )

        user_text = stt_result.get("text", "").strip()
        raw_text = stt_result.get("raw_text", "").strip() or user_text
        detected_lang = stt_result.get(
            "language",
            requested_lang if requested_lang != "auto" else "en"
        )
        confidence = float(stt_result.get("confidence", 0.85))
        speech_detected = stt_result.get("speech_detected", bool(user_text))

        if not user_text or not speech_detected:
            emit("error", {
                "code": "no_clear_speech",
                "message": "I could not hear the speech clearly. Please speak a little closer to the microphone."
            })
            return

        # 2. Ensure active session
        if not session_id or not db_service.get_session(session_id):
            session_id = db_service.create_session(patient_id)

        # 3. Save exact patient voice input
        db_service.append_message(
            session_id,
            sender="patient",
            text=user_text,
            modality="voice"
        )
        memory_service.record_patient_language(patient_id, detected_lang)

        # 4. Emit transcript (UI immediately displays patient bubble)
        emit("voice_transcript", {
            "status": "success",
            "text": user_text,
            "raw_text": raw_text,
            "language": detected_lang,
            "confidence": confidence
        })

        # 5. Start unified AI pipeline in background task
        socketio.start_background_task(
            process_patient_message,
            sid,
            session_id,
            patient_id,
            user_text,
            detected_lang,
            "voice"
        )

    except Exception as e:
        print(f"[VOICE ERROR] {repr(e)}")
        emit("error", {
            "code": "voice_processing_error",
            "message": "Voice processing failed. Please try again."
        })



# ==========================================
# 4. SSE Streaming Endpoint
# ==========================================

@chat_bp.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """
    Real-time Server-Sent Events (SSE) streaming endpoint.
    Streams AI tokens immediately and measures performance metrics.
    """
    data = request.get_json() or {}
    user_text = data.get("message", "").strip()
    session_id = data.get("session_id")
    patient_id = data.get("patient_id", "P-1001")
    language = data.get("language", "en")

    if not user_text:
        return jsonify({"error": "Empty message"}), 400

    if not session_id or not db_service.get_session(session_id):
        session_id = db_service.create_session(patient_id)

    db_service.append_message(session_id, sender="patient", text=user_text, modality="text")
    session = db_service.get_session(session_id)
    messages = session.get("messages", [])

    t_start = time.time()
    user_memory = memory_service.get_relevant_memory(patient_id=patient_id, query=user_text)
    memory_ms = int((time.time() - t_start) * 1000)

    def generate_events():
        full_text_acc = []
        first_token_time = None
        try:
            for token in llm_service.stream_conversational_response(messages, patient_id=patient_id, memory=user_memory, language=language):
                if token:
                    if first_token_time is None:
                        first_token_time = time.time()
                    full_text_acc.append(token)
                    yield f"data: {json.dumps({'token': token, 'session_id': session_id, 'patient_id': patient_id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            print(f"[Chat Stream] Token generation error: {e}")

        complete_text = "".join(full_text_acc).strip()
        if not complete_text:
            complete_text = "I am ready to help. Please ask your question."

        llm_total_ms = int((time.time() - t_start) * 1000)
        llm_first_token_ms = int((first_token_time - t_start) * 1000) if first_token_time else llm_total_ms

        ai_msg = db_service.append_message(session_id, sender="ai", text=complete_text, modality="stream")

        memory_service.extract_and_update_memory_async(
            patient_id=patient_id,
            session_id=session_id,
            user_text=user_text,
            ai_text=complete_text
        )

        updated_messages = db_service.get_session(session_id).get("messages", [])
        if any(is_medical_message(m.get("text", "")) for m in updated_messages if m.get("sender") in ("patient", "user")):
            t = threading.Thread(
                target=_run_triage_in_background,
                args=(session_id, updated_messages, language),
                daemon=True
            )
            t.start()

        yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'patient_id': patient_id, 'full_text': complete_text, 'message_id': ai_msg.get('id'), 'telemetry': {'memory_ms': memory_ms, 'llm_first_token_ms': llm_first_token_ms, 'llm_total_ms': llm_total_ms}}, ensure_ascii=False)}\n\n"

    return Response(generate_events(), content_type="text/event-stream; charset=utf-8")


# ==========================================
# 5. REST Decoupled Synthesize & Transcription
# ==========================================

@chat_bp.route("/api/chat/synthesize", methods=["POST"])
def chat_synthesize():
    """
    Decoupled background TTS endpoint. Generates audio without blocking text streaming.
    """
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    language = data.get("language", "en")

    if not text:
        return jsonify({"audio_url": None}), 200

    audio_filename = tts_service.synthesize_speech(text, language=language)
    audio_url = f"/api/audio/{audio_filename}" if audio_filename else None

    return jsonify({
        "status": "success",
        "audio_url": audio_url
    })


@chat_bp.route("/api/chat/transcribe", methods=["POST"])
def chat_transcribe():
    """
    Fast Whisper STT endpoint with automatic language detection, MIME format inspection, and de-hallucination.
    """
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    session_id = request.form.get("session_id")
    patient_id = request.form.get("patient_id", "P-1001")

    if not session_id or not db_service.get_session(session_id):
        session_id = db_service.create_session(patient_id)

    # Determine file extension from filename or mime type
    ext = ".webm"
    if audio_file.filename and "." in audio_file.filename:
        ext = os.path.splitext(audio_file.filename)[1]
    elif audio_file.content_type:
        ct = audio_file.content_type.lower()
        if "mp4" in ct or "m4a" in ct:
            ext = ".mp4"
        elif "ogg" in ct:
            ext = ".ogg"
        elif "wav" in ct:
            ext = ".wav"
        elif "aac" in ct:
            ext = ".aac"

    audio_bytes = audio_file.read()
    stt_result = stt_service.transcribe_audio_bytes(audio_bytes, file_ext=ext, language=None)
    transcribed_text = stt_result.get("text", "").strip()
    detected_lang = stt_result.get("language", "en")

    if not transcribed_text:
        return jsonify({
            "status": "error",
            "message": "Sorry, I couldn't hear that clearly. Please try speaking again or typing your message.",
            "session_id": session_id,
            "patient_id": patient_id
        }), 422

    # Save patient voice message
    db_service.append_message(session_id, sender="patient", text=transcribed_text, modality="voice")

    return jsonify({
        "status": "success",
        "session_id": session_id,
        "patient_id": patient_id,
        "text": transcribed_text,
        "language": detected_lang
    })


@chat_bp.route("/api/chat/text", methods=["POST"])
def chat_text():
    """
    Synchronous fallback text endpoint.
    """
    data = request.get_json() or {}
    user_text = data.get("message", "").strip()
    session_id = data.get("session_id")
    patient_id = data.get("patient_id", "P-1001")
    language = data.get("language", "en")

    if not user_text:
        return jsonify({"error": "Empty message"}), 400

    if not session_id or not db_service.get_session(session_id):
        session_id = db_service.create_session(patient_id)

    db_service.append_message(session_id, sender="patient", text=user_text, modality="text")
    session = db_service.get_session(session_id)
    messages = session.get("messages", [])

    user_memory = memory_service.get_relevant_memory(patient_id=patient_id, query=user_text)

    ai_response_text = llm_service.generate_conversational_response(
        messages,
        memory=user_memory,
        language=language
    )

    audio_filename = tts_service.synthesize_speech(ai_response_text, language=language)
    audio_url = f"/api/audio/{audio_filename}" if audio_filename else None

    ai_msg = db_service.append_message(
        session_id, sender="ai", text=ai_response_text, modality="dual", audio_url=audio_url
    )

    memory_service.extract_and_update_memory_async(
        patient_id=patient_id,
        session_id=session_id,
        user_text=user_text,
        ai_text=ai_response_text
    )

    updated_messages = db_service.get_session(session_id).get("messages", [])
    if any(is_medical_message(m.get("text", "")) for m in updated_messages if m.get("sender") in ("patient", "user")):
        t = threading.Thread(
            target=_run_triage_in_background,
            args=(session_id, updated_messages, language),
            daemon=True
        )
        t.start()

    last_triage = session.get("triage_summary") or {}

    return jsonify({
        "status": "success",
        "session_id": session_id,
        "patient_id": patient_id,
        "text": ai_response_text,
        "audio_url": audio_url,
        "language": language,
        "triage": last_triage,
        "message_id": ai_msg["id"]
    })


@chat_bp.route("/api/chat/voice", methods=["POST"])
def chat_voice():
    """
    Synchronous fallback voice endpoint with multilingual support.
    """
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    session_id = request.form.get("session_id")
    patient_id = request.form.get("patient_id", "P-1001")
    requested_lang = request.form.get("language", "auto")

    if not session_id or not db_service.get_session(session_id):
        session_id = db_service.create_session(patient_id)

    ext = ".webm"
    if audio_file.filename and "." in audio_file.filename:
        ext = os.path.splitext(audio_file.filename)[1]
    elif audio_file.content_type:
        ct = audio_file.content_type.lower()
        if "mp4" in ct or "m4a" in ct:
            ext = ".mp4"
        elif "ogg" in ct:
            ext = ".ogg"
        elif "wav" in ct:
            ext = ".wav"

    audio_bytes = audio_file.read()
    stt_result = stt_service.transcribe_audio_bytes(
        audio_bytes,
        file_ext=ext,
        language=requested_lang if requested_lang != "auto" else None
    )

    transcribed_text = stt_result.get("text", "").strip()
    detected_lang = stt_result.get("language", requested_lang if requested_lang != "auto" else "en")

    if not transcribed_text:
        return jsonify({
            "status": "error",
            "message": "Sorry, I couldn't hear that clearly. Please try speaking again or typing your message.",
            "session_id": session_id,
            "patient_id": patient_id
        }), 422

    db_service.append_message(session_id, sender="patient", text=transcribed_text, modality="voice")
    memory_service.record_patient_language(patient_id, detected_lang)
    session = db_service.get_session(session_id)
    messages = session.get("messages", [])

    user_memory = memory_service.get_relevant_memory(patient_id=patient_id, query=transcribed_text)
    ai_response_text = llm_service.generate_conversational_response(
        messages,
        memory=user_memory,
        language=detected_lang
    )

    audio_filename = tts_service.synthesize_speech(ai_response_text, language=detected_lang)
    audio_url = f"/api/audio/{audio_filename}" if audio_filename else None

    ai_msg = db_service.append_message(
        session_id, sender="ai", text=ai_response_text, modality="dual", audio_url=audio_url
    )

    memory_service.extract_and_update_memory_async(
        patient_id=patient_id,
        session_id=session_id,
        user_text=transcribed_text,
        ai_text=ai_response_text
    )

    updated_messages = db_service.get_session(session_id).get("messages", [])
    if any(is_medical_message(m.get("text", "")) for m in updated_messages if m.get("sender") in ("patient", "user")):
        t = threading.Thread(
            target=_run_triage_in_background,
            args=(session_id, updated_messages, detected_lang),
            daemon=True
        )
        t.start()

    last_triage = session.get("triage_summary") or {}

    return jsonify({
        "status": "success",
        "session_id": session_id,
        "patient_id": patient_id,
        "transcription": transcribed_text,
        "text": ai_response_text,
        "audio_url": audio_url,
        "language": detected_lang,
        "triage": last_triage,
        "message_id": ai_msg["id"]
    })

