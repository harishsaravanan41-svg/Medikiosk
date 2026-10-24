from flask import Blueprint, request, jsonify

from app.services.llm_service import llm_service
from app.services.stt_service import stt_service
from app.services.tts_service import tts_service

config_bp = Blueprint("config_routes", __name__)


@config_bp.route("/api/config", methods=["GET", "POST"])
def manage_config():
    if request.method == "POST":
        data = request.get_json() or {}
        llm_service.update_config(
            api_base=data.get("qwen_api_url") or data.get("qwen_api_base"),
            api_key=data.get("qwen_api_key"),
            model=data.get("qwen_model"),
            mode=data.get("qwen_mode")
        )
        return jsonify({"status": "updated"})

    return jsonify({
        "qwen_api_base": llm_service.api_base,
        "qwen_api_url": llm_service.api_base,
        "qwen_mode": llm_service.mode,
        "qwen_model": llm_service.model,
        "whisper_model": stt_service.model_name,
        "tts_engine": tts_service.engine,
        "piper_voice": tts_service.piper_voice
    })
