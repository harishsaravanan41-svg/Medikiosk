import sys
from pathlib import Path

# Fix Windows console encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Config
from app.services.db_service import db_service
from app.services.triage_service import triage_service
from app.services.llm_service import llm_service
from app.services.tts_service import tts_service
from app.services.stt_service import stt_service

def test_json_database():
    print("Testing JSON Database...")
    session_id = db_service.create_session("P-TEST")
    assert session_id is not None, "Failed to create session"
    
    msg = db_service.append_message(session_id, "patient", "I have chest pain and shortness of breath", modality="voice")
    assert msg["text"] == "I have chest pain and shortness of breath"
    
    session = db_service.get_session(session_id)
    assert len(session["messages"]) == 1
    print("✅ JSON Database passed.")
    return session_id

def test_triage_analysis(session_id):
    print("Testing Triage Engine...")
    session = db_service.get_session(session_id)
    triage = triage_service.analyze_conversation(session["messages"])
    
    assert triage["urgency_level"] == "Emergency", f"Expected Emergency, got {triage['urgency_level']}"
    assert "chest pain" in triage["chief_complaint"].lower(), f"Expected chest pain in complaint, got {triage['chief_complaint']}"
    print(f"✅ Triage Engine passed. Assessment: {triage['urgency_level']} -> {triage['recommended_department']}")

def test_llm_response():
    print("Testing Qwen LLM / Clinical Engine...")
    messages = [{"sender": "patient", "text": "I have had a mild headache since yesterday morning."}]
    response = llm_service.generate_response(messages)
    assert response and len(response) > 5, "Empty LLM response"
    print(f"✅ LLM Engine Response: \"{response}\"")
    return response

def test_tts_generation(sample_text):
    print("Testing TTS Engine...")
    audio_file = tts_service.synthesize_speech(sample_text)
    assert audio_file is not None, "TTS synthesis returned None"
    file_path = Config.AUDIO_CACHE_DIR / audio_file
    assert file_path.exists() and file_path.stat().st_size > 0, "Audio file not created on disk"
    print(f"✅ TTS Audio generated: {file_path} ({file_path.stat().st_size} bytes)")

def test_stt_module():
    print("Testing STT Whisper Module...")
    assert stt_service is not None
    print(f"✅ STT Service ready with model '{stt_service.model_name}'.")

def main():
    print("==========================================")
    print("  MEDIKIOSK PIPELINE VALIDATION TEST")
    print("==========================================")
    session_id = test_json_database()
    test_triage_analysis(session_id)
    reply = test_llm_response()
    test_tts_generation(reply)
    test_stt_module()
    print("==========================================")
    print("🎉 ALL TESTS PASSED SUCCESSFULLY!")
    print("==========================================")

if __name__ == "__main__":
    main()
