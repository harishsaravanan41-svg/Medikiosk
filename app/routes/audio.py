from flask import Blueprint, request, jsonify, send_from_directory

from app.config import Config
from app.services.stt_service import stt_service
from app.services.tts_service import tts_service

audio_bp = Blueprint("audio", __name__)


@audio_bp.route("/api/stt", methods=["POST"])
def stt_only():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    audio_file = request.files["audio"]
    audio_bytes = audio_file.read()
    res = stt_service.transcribe_audio_bytes(audio_bytes)
    return jsonify(res)


@audio_bp.route("/api/tts", methods=["POST"])
def tts_only():
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    voice = data.get("voice")
    if not text:
        return jsonify({"error": "No text provided"}), 400
    audio_filename = tts_service.synthesize_speech(text, voice=voice)
    if not audio_filename:
        return jsonify({"error": "TTS synthesis failed"}), 500
    return jsonify({
        "audio_url": f"/api/audio/{audio_filename}"
    })


@audio_bp.route("/api/audio/<filename>")
def serve_audio(filename):
    return send_from_directory(Config.AUDIO_CACHE_DIR, filename)
