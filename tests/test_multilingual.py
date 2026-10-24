import sys
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.llm_service import llm_service
from app.services.tts_service import tts_service

languages = [
    ("hi", "मुझे तेज सिरदर्द और बुखार है"),
    ("ta", "எனக்கு கடுமையான தலைவலி உள்ளது"),
    ("te", "నాకు తీవ్రమైన తలనొప్పి మరియు జ్వరం ఉంది"),
    ("ml", "എനിക്ക് കടുത്ത തലവേദനയും പനിയും ഉണ്ട്"),
    ("kn", "ನನಗೆ ತೀವ್ರ ತಲೆನೋವು ಮತ್ತು ಜ್ವರ ಇದೆ"),
    ("en", "I have chest pain and shortness of breath")
]

print("=== MULTI-LANGUAGE DUAL-OUTPUT VALIDATION TEST ===")
for lang, user_input in languages:
    print(f"\n--- Testing Language: {lang} ---")
    print(f"Patient ({lang}):", user_input)
    response_text = llm_service.generate_response([{"sender": "patient", "text": user_input}], language=lang)
    print(f"AI Text ({lang}):", response_text)
    
    audio_file = tts_service.synthesize_speech(response_text, language=lang)
    print(f"TTS Audio ({lang}):", audio_file)
    assert audio_file is not None, f"Failed audio for {lang}"

print("\n🎉 ALL 6 LANGUAGES GENERATE TEXT + AUDIO SIMULTANEOUSLY!")
