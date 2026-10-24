import sys
import os
import json
import glob

# Ensure root directory is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.services.memory_service import memory_service
from app.services.db_service import db_service
from app.services.llm_service import llm_service, detect_text_language, is_medical_message, MEDIKIOSK_SYSTEM_PROMPT
from app.services.stt_service import _clean_hallucinated_text
from app.services.tts_service import _detect_tts_language, _clean_text_for_speech


def run_verification():
    print("==================================================")
    print("      MEDIKIOSK ARCHITECTURE VERIFICATION TEST    ")
    print("==================================================")

    # 1. Test Clinical Relevance Gate (Non-medical vs Medical)
    print("\n--- 1. Testing Clinical Relevance Gate (Zero Hardcoded Questionnaires) ---")
    general_queries = ["hello", "hi there", "what is python?", "who is the prime minister of India?", "write a loop in js"]
    medical_queries = ["I have a fever", "severe chest pain", "enakku 3 days ah fever irukku", "mujhe sar dard ho raha hai"]

    for q in general_queries:
        assert not is_medical_message(q), f"Gate failed: '{q}' should NOT trigger clinical extraction"
    print("✓ General queries correctly bypassed clinical extraction.")

    for q in medical_queries:
        assert is_medical_message(q), f"Gate failed: '{q}' SHOULD trigger clinical extraction"
    print("✓ Medical queries correctly flagged for background clinical extraction.")

    # 2. Test Dynamic Multilingual Detection across all 11 languages
    print("\n--- 2. Testing Dynamic Language Detection (11 Indian Languages & Code-Switching) ---")
    lang_tests = [
        ("Hello, how are you?", "en"),
        ("வணக்கம், எனக்கு காய்ச்சல் உள்ளது", "ta"),
        ("नमस्ते, मुझे सिरदर्द है", "hi"),
        ("నమస్కారం, నాకు జ్వరం ఉంది", "te"),
        ("നമസ്കാരം, എനിക്ക് പനിയുണ്ട്", "ml"),
        ("ನಮಸ್ಕಾರ, ನನಗೆ ಜ್ವರ ಇದೆ", "kn"),
        ("নমস্কার, আমার জ্বর হয়েছে", "bn"),
        ("मला ताप आला आहे आणि डोकेदुखी त्रास होतो", "mr"),
        ("મને તાવ આવ્યો છે અને માથું દુખે છે", "gu"),
        ("ਮੈਨੂੰ ਬੁਖ਼ਾਰ ਹੈ ਅਤੇ ਸਿਰਦਰਦ ਹੈ", "pa"),
        ("مجھے تیز بخار ہے اور سر में दर्द है", "ur"),
        ("enakku romba fever irukku", "ta"),  # Tanglish
        ("mujhe bukhar hai aur dard ho raha hai", "hi"),  # Hinglish
        ("naku fever undi cheppandi", "te"),  # Telugish
        ("mala khup fever ahe", "mr"),  # Marathish
        ("mane fever chhe", "gu"),  # Gujaratish
    ]
    for text, expected_lang in lang_tests:
        detected = detect_text_language(text)
        print(f"  Input: '{text}' -> Detected: {detected} (Expected: {expected_lang})")
        assert detected == expected_lang, f"Language detection mismatch for '{text}': got {detected}, expected {expected_lang}"
    print("✓ Dynamic multilingual & mixed-language detection verified across all 11 languages.")

    # 3. Test Multi-Turn Medical Memory Accumulation (Non-Overwriting)
    print("\n--- 3. Testing Patient Memory Accumulation (User A: P-1001) ---")
    user_a = "P-1001"
    user_b = "P-1002"

    store = memory_service._read_json()
    store.pop(user_a, None)
    store.pop(user_b, None)
    memory_service._write_json(store)

    # Turn 1: "I have fever"
    memory_service._extract_and_update_memory_worker(
        patient_id=user_a,
        session_id="session_001",
        user_text="I have fever",
        ai_text="I'm sorry you're feeling unwell. How long have you had the fever?"
    )

    # Turn 2: "for 3 days" (follow-up duration)
    memory_service._extract_and_update_memory_worker(
        patient_id=user_a,
        session_id="session_001",
        user_text="for 3 days",
        ai_text="Okay, you've had fever for 3 days."
    )

    # Turn 3: "I also have chest pain"
    memory_service._extract_and_update_memory_worker(
        patient_id=user_a,
        session_id="session_001",
        user_text="I also have chest pain",
        ai_text="Chest pain is an important symptom to evaluate carefully."
    )

    mem_a = memory_service.get_user_memory(user_a)
    med_facts_a = [m.get("fact") for m in mem_a.get("medical_memory", [])]
    durations_a = {m.get("fact"): m.get("duration") for m in mem_a.get("medical_memory", [])}

    print(f"User A ({user_a}) Medical Facts: {med_facts_a}")
    print(f"User A Durations: {durations_a}")

    assert "fever" in med_facts_a, "Assertion failed: fever missing from User A memory"
    assert "chest pain" in med_facts_a, "Assertion failed: chest pain missing from User A memory"
    assert durations_a.get("fever") == "for 3 days", "Assertion failed: duration missing for fever"
    print("✓ User A symptoms and duration accumulated additively without overwriting.")

    # 4. Test Strict Patient Isolation (Zero Leakage between User A and User B)
    print("\n--- 4. Testing Strict Patient Isolation (User B: P-1002) ---")
    mem_b = memory_service.get_relevant_memory(patient_id=user_b)
    print(f"User B ({user_b}) Retrieved Memory Context: {mem_b}")

    assert mem_b is None, "Assertion failed: User B received User A's memory!"
    print("✓ User B has ZERO access to User A's memory (Strict Isolation Verified).")

    # 5. Test Memory Retrieval Context for LLM Prompt Injection
    print("\n--- 5. Testing Prompt Context Builder for Recall Queries ---")
    context_a = memory_service.get_relevant_memory(patient_id=user_a, query="how many days did I say I had fever?")
    print("Retrieved Context Block for Qwen:")
    print("--------------------------------------------------")
    print(context_a)
    print("--------------------------------------------------")

    assert "RELEVANT USER MEMORY (Patient ID: P-1001):" in context_a
    assert "fever (duration: for 3 days)" in context_a
    assert "chest pain" in context_a
    print("✓ Memory context provides exact facts for answering user questions.")

    # 6. Test Multi-Session Cross-Session Recall
    print("\n--- 6. Testing Multi-Session Cross-Recall ---")
    memory_service.add_conversation_summary(
        patient_id=user_a,
        session_id="session_001",
        summary="Patient discussed fever (3 days) and chest pain."
    )
    context_a_s2 = memory_service.get_relevant_memory(patient_id=user_a)
    assert "Previous Conversations Summary:" in context_a_s2
    print("✓ Multi-session cross-conversation recall verified.")

    # 7. Test STT De-Hallucination & Speech Normalization
    print("\n--- 7. Testing STT De-Hallucination & Speech Normalization ---")
    assert _clean_hallucinated_text("Thank you for watching!") == "", "Failed to filter phantom subtitle"
    assert _clean_hallucinated_text("fever fever fever fever") == "fever", "Failed to collapse repetitive loop"
    assert _clean_hallucinated_text("I have a headache") == "I have a headache", "Normal speech should be preserved"
    
    from app.services.stt_service import normalize_speech_text
    norm_tanglish = normalize_speech_text("enaku fever iruku two days ah", "ta")
    assert "enakku" in norm_tanglish and "irukku" in norm_tanglish and "2 days-ஆ" in norm_tanglish
    norm_hindi = normalize_speech_text("mujhe bukhar h aur dard ho ra", "hi")
    assert "bukhar hai" in norm_hindi and "dard ho raha hai" in norm_hindi
    print("✓ STT de-hallucination and speech normalization verified.")

    # 8. Test Response-Driven TTS Language & Text Cleaning across scripts
    print("\n--- 8. Testing TTS Script Selection & Normalization ---")
    assert _detect_tts_language("Hello there", "en") == "en"
    assert _detect_tts_language("வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்?", "en") == "ta"
    assert _detect_tts_language("नमस्ते, क्या हाल है?", "en") == "hi"
    assert _detect_tts_language("मला ताप आला आहे आणि त्रास होतो", "en") == "mr"
    assert _detect_tts_language("నమస్కారం, ఎలా ఉన్నారు?", "en") == "te"
    assert _detect_tts_language("നമസ്കാരം, എങ്ങനെയുണ്ട്?", "en") == "ml"
    assert _detect_tts_language("ನಮಸ್ಕಾರ, ಹೇಗಿದ್ದೀರಿ?", "en") == "kn"
    assert _detect_tts_language("নমস্কার, কেমন আছেন?", "en") == "bn"
    assert _detect_tts_language("નમસ્તે, તમે કેમ છો?", "en") == "gu"
    assert _detect_tts_language("ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ, ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?", "en") == "pa"
    assert _detect_tts_language("السلام علیکم، آپ کیسے ہیں؟", "en") in ["ur", "ar"]
    
    clean_code_text = _clean_text_for_speech("Here is the code: ```python\nprint('hello')\n``` Enjoy!")
    assert "print('hello')" not in clean_code_text
    assert "Here is the code." in clean_code_text
    print("✓ TTS script-driven voice detection and markdown cleaning verified across all scripts.")

    # 9. Test 7 Localization JSON files
    print("\n--- 9. Testing 7 UI Localization JSON Files ---")
    locales_dir = os.path.join(os.path.dirname(__file__), "..", "app", "static", "locales")
    expected_locales = ["en", "ta", "hi", "ml", "kn", "bn", "te"]
    required_keys = [
        "brand_name", "brand_tagline", "choose_language", "patient_role", "doctor_role",
        "save_consultation", "uploaded_documents", "patient_timeline", "clinical_findings",
        "assessment", "diagnosis", "treatment_prescription", "follow_up"
    ]
    for lang in expected_locales:
        file_path = os.path.join(locales_dir, f"{lang}.json")
        assert os.path.exists(file_path), f"Locale file missing: {file_path}"
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k in required_keys:
                assert k in data, f"Key '{k}' missing from locale '{lang}'"
        print(f"  ✓ Locale '{lang}.json' validated with {len(data)} translation keys.")
    print("✓ All 7 UI locale JSON files verified.")

    # 10. Test Database Models & Seed Data Integrity
    print("\n--- 10. Testing Relational DB Service & Seed Data ---")
    p1 = db_service.get_patient_by_abha("DEMO-ABHA-001")
    assert p1 is not None, "DEMO-ABHA-001 patient record missing in database"
    assert p1["name"] == "Ravi Kumar"
    print(f"  ✓ Patient record found: {p1['name']} ({p1['abha_id']})")

    doc1 = db_service.authenticate_doctor("doctor1@demo.medikiosk", "DemoDoc#123")
    assert doc1 is not None, "doctor1@demo.medikiosk authentication failed in db_service"
    print(f"  ✓ Doctor authenticated: {doc1['name']} ({doc1['specialization']})")

    # 11. Test Flask App Test Client (Auth, Doctor Portal & History Append Workflow)
    print("\n--- 11. Testing Flask REST Endpoints & Never-Overwrite Consultation Flow ---")
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()

    # 11a. Patient Login
    res = client.post("/api/auth/patient/login", json={"abha_id": "DEMO-ABHA-001"})
    assert res.status_code == 200, f"Patient login failed: {res.data}"
    res_data = res.get_json()
    assert res_data["status"] == "success" and res_data["patient"]["abha_id"] == "DEMO-ABHA-001"
    print("  ✓ Patient ABHA login endpoint successful.")

    # 11b. Doctor Login
    res = client.post("/api/auth/doctor/login", json={"email": "doctor1@demo.medikiosk", "password": "DemoDoc#123"})
    assert res.status_code == 200, f"Doctor login failed: {res.data}"
    doc_login_data = res.get_json()
    assert doc_login_data["status"] == "success" and doc_login_data["doctor"]["email"] == "doctor1@demo.medikiosk"
    print("  ✓ Doctor password authenticated login successful.")

    # 11c. Session Info
    res = client.get("/api/auth/me")
    assert res.status_code == 200 and res.get_json()["authenticated"]
    print("  ✓ Session /api/auth/me validated.")

    # 11d. Doctor Dashboard Stats
    res = client.get("/api/doctor/dashboard-stats")
    assert res.status_code == 200
    stats = res.get_json()["data"]
    assert "new_cases" in stats and "completed" in stats
    print(f"  ✓ Dashboard stats retrieved: {stats['completed']} completed encounters.")

    # 11e. Patient Search by ABHA
    res = client.get("/api/doctor/patient/by-abha/DEMO-ABHA-001")
    assert res.status_code == 200
    patient_full = res.get_json()
    patient_id = patient_full["patient"]["patient_id"]
    active_enc = patient_full.get("active_encounter")
    assert active_enc is not None, "Active encounter missing for DEMO-ABHA-001"
    print(f"  ✓ Patient search returned active encounter: {active_enc['encounter_id']}")

    # 11f. AI Clinical History Review & Verification
    res = client.put(f"/api/doctor/encounter/{active_enc['encounter_id']}/history", json={
        "chief_complaint": "Chest pain with left arm radiation (Doctor Verified)",
        "allergies": "Penicillin (Severe Rash in 2018)"
    })
    assert res.status_code == 200
    print("  ✓ AI History edited successfully by doctor.")

    res = client.post(f"/api/doctor/encounter/{active_enc['encounter_id']}/verify")
    assert res.status_code == 200
    print("  ✓ AI History verified successfully by doctor.")

    # 11g. Save Consultation -> Permanent Record Creation
    # First, record existing completed encounters count
    res_before = client.get(f"/api/doctor/patient/{patient_id}/history")
    history_before = res_before.get_json()["encounters"]
    completed_before = [e for e in history_before if e.get("status") == "completed"]
    count_before = len(completed_before)
    print(f"  Existing completed encounters before saving: {count_before}")

    consultation_payload = {
        "clinical_findings": "BP: 136/86 mmHg, PR: 82 bpm. S1, S2 audible, no murmurs.",
        "assessment": "Stable Angina Pectoris in diabetic patient.",
        "diagnosis": "Angina Pectoris - Stable Exertional",
        "prescription_treatment": "1. Tab Aspirin 75mg OD\n2. Tab Sorbitrate 5mg SOS\n3. 12-Lead ECG",
        "follow_up": "Review with 12-lead ECG tomorrow.",
        "notes": "Patient advised strict lifestyle modifications."
    }
    res = client.post(f"/api/doctor/encounter/{active_enc['encounter_id']}/consultation", json=consultation_payload)
    assert res.status_code == 200, f"Consultation save failed: {res.data}"
    save_result = res.get_json()
    assert save_result["status"] == "success" and save_result["encounter"]["status"] == "completed"
    print(f"  ✓ Consultation saved! Completed encounter: {save_result['encounter']['encounter_id']}")

    # 11h. Verify Date-Wise History Append (NEVER OVERWRITES PREVIOUS HISTORY)
    res_after = client.get(f"/api/doctor/patient/{patient_id}/history")
    history_after = res_after.get_json()["encounters"]
    completed_after = [e for e in history_after if e.get("status") == "completed"]
    count_after = len(completed_after)
    print(f"  Completed encounters after saving: {count_after}")
    assert count_after == count_before + 1, "Completed encounter count did not increase by 1!"

    # Verify older encounters remain unchanged
    older_problems = [enc["current_problem"] for enc in history_after]
    print(f"  Encounter problems across patient timeline: {older_problems}")
    assert "Viral Fever & Body Pain" in older_problems, "Older encounter 'Fever' was overwritten!"
    assert "Tension Headache & Eye Strain" in older_problems, "Older encounter 'Headache' was overwritten!"
    print("  ✓ Confirmed: Past encounters (Fever, Headache) are permanently intact and NOT overwritten!")

    # 11i. Verify Patient Documents & OCR Extraction
    res_docs = client.get(f"/api/doctor/patient/{patient_id}/documents")
    assert res_docs.status_code == 200
    docs = res_docs.get_json()["documents"]
    assert len(docs) >= 3, f"Expected at least 3 documents for DEMO-ABHA-001, got {len(docs)}"
    print(f"  ✓ Patient documents retrieved: {len(docs)} permanent documents stored.")

    first_doc_id = docs[0]["document_id"]
    res_ocr = client.get(f"/api/doctor/document/{first_doc_id}/extraction")
    assert res_ocr.status_code == 200
    ocr_data = res_ocr.get_json()
    assert ocr_data["document"] is not None
    assert ocr_data["extraction"] is not None
    print(f"  ✓ Side-by-side Document OCR extraction retrieved for '{docs[0]['title']}'.")

    # 11j. Verify Unified Patient Timeline
    res_timeline = client.get(f"/api/doctor/patient/{patient_id}/timeline")
    assert res_timeline.status_code == 200
    timeline = res_timeline.get_json()["timeline"]
    assert len(timeline) >= 5, f"Expected unified timeline entries, got {len(timeline)}"
    print(f"  ✓ Unified timeline retrieved: {len(timeline)} chronological consultation and document events.")

    # 11k. Test Logout
    res_logout = client.post("/api/auth/logout")
    assert res_logout.status_code == 200
    print("  ✓ Logout successful.")

    print("\n==================================================")
    print("    ALL ARCHITECTURAL & WORKFLOW CHECKS PASSED!   ")
    print("==================================================")


if __name__ == "__main__":
    run_verification()
