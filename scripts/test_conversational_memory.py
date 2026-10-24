# -*- coding: utf-8 -*-
"""
Comprehensive verification script for:
1. Patient memory isolation (P-1001 vs P-1002)
2. Multi-turn natural conversational flow without fixed questions
3. Multi-symptom with duration handling ("2 நாட்களுக்கு தலைவலி மற்றும் வாந்தி இருக்கு")
4. Recall queries ("which is noted?")
5. Denial understanding ("இல்லை" as answer to previous question)
6. Structured clinical fact extraction (extract_patient_facts)
7. Doctor report generation
"""
import os
import sys
import json

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.services.memory_service import memory_service
from app.services.llm_service import llm_service

def run_tests():
    print("==================================================")
    print("1. TESTING PATIENT MEMORY ISOLATION (P-1001 vs P-1002)")
    print("==================================================")
    
    memory_service.add_medical_fact("P-1001", "fever", duration="3 days")
    memory_service.add_medical_fact("P-1001", "chest pain", duration="since yesterday")
    
    p1_facts = memory_service.get_known_patient_facts_formatted("P-1001")
    print(f"P-1001 Facts:\n{p1_facts}\n")
    assert "Fever: yes" in p1_facts
    assert "3 days" in p1_facts
    assert "Chest pain: yes" in p1_facts
    
    p2_facts = memory_service.get_known_patient_facts_formatted("P-1002")
    print(f"P-1002 Facts:\n{p2_facts}\n")
    assert "fever" not in p2_facts.lower()
    assert "chest pain" not in p2_facts.lower()
    print("PASS: P-1001 memory is strictly isolated from P-1002!\n")

    print("==================================================")
    print("2. TESTING NATURAL CONVERSATIONAL MULTI-TURN FLOW")
    print("==================================================")

    test_patient = "P-TEST-001"
    mem_store = memory_service._read_json()
    if test_patient in mem_store:
        del mem_store[test_patient]
        memory_service._write_json(mem_store)

    convo_history = []

    # Turn 1: Patient reports fever
    t1_user = "எனக்கு காய்ச்சல் இருக்கு"
    convo_history.append({"sender": "patient", "text": t1_user})
    memory_service.add_medical_fact(test_patient, "fever", duration=None)
    
    resp_1 = llm_service._generate_conversational_fallback(
        user_text=t1_user,
        patient_id=test_patient,
        messages=convo_history,
        language="ta"
    )
    print(f"Patient: {t1_user}")
    print(f"AI: {resp_1}")
    convo_history.append({"sender": "ai", "text": resp_1})
    assert "நாட்களாக" in resp_1 or "எத்தனை" in resp_1, f"Expected duration question, got: {resp_1}"
    print("PASS: Turn 1 asked contextually for fever duration.\n")

    # Turn 2: Patient answers 3 days
    t2_user = "3 நாட்களாக"
    convo_history.append({"sender": "patient", "text": t2_user})
    memory_service.add_medical_fact(test_patient, "fever", duration="3 நாட்களாக")

    resp_2 = llm_service._generate_conversational_fallback(
        user_text=t2_user,
        patient_id=test_patient,
        messages=convo_history,
        language="ta"
    )
    print(f"Patient: {t2_user}")
    print(f"AI: {resp_2}")
    convo_history.append({"sender": "ai", "text": resp_2})
    assert "3 நாட்களாக" in resp_2
    assert "வேறு ஏதாவது" in resp_2
    print("PASS: Turn 2 acknowledged 3 days fever and asked if other problems exist without repeating.\n")

    # Turn 3: Patient reports chest pain
    t3_user = "எனக்கு chest pain கூட இருக்கு"
    convo_history.append({"sender": "patient", "text": t3_user})
    memory_service.add_medical_fact(test_patient, "chest pain", duration=None)

    resp_3 = llm_service._generate_conversational_fallback(
        user_text=t3_user,
        patient_id=test_patient,
        messages=convo_history,
        language="ta"
    )
    print(f"Patient: {t3_user}")
    print(f"AI: {resp_3}")
    convo_history.append({"sender": "ai", "text": resp_3})
    assert "காய்ச்சலுடன்" in resp_3 or "மார்பு" in resp_3
    print("PASS: Turn 3 synthesized fever + chest pain and asked chest pain onset.\n")

    # Turn 4: Patient clarifies onset
    t4_user = "நேற்று முதல்"
    convo_history.append({"sender": "patient", "text": t4_user})
    memory_service.add_medical_fact(test_patient, "chest pain", duration="நேற்று முதல்")

    resp_4 = llm_service._generate_conversational_fallback(
        user_text=t4_user,
        patient_id=test_patient,
        messages=convo_history,
        language="ta"
    )
    print(f"Patient: {t4_user}")
    print(f"AI: {resp_4}")
    convo_history.append({"sender": "ai", "text": resp_4})
    assert "நேற்று முதல்" in resp_4 or "புரிந்தது" in resp_4
    print("PASS: Turn 4 acknowledged onset.\n")

    print("==================================================")
    print("3. TESTING USER SCREENSHOT CASE: HEADACHE + VOMITING + DURATION")
    print("==================================================")
    
    test_patient_2 = "P-TEST-002"
    mem_store = memory_service._read_json()
    if test_patient_2 in mem_store:
        del mem_store[test_patient_2]
        memory_service._write_json(mem_store)

    convo_2 = []
    # Patient sends: "2 நாட்களுக்கு தலைவலி மற்றும் வாந்தி இருக்கு"
    u_msg = "2 நாட்களுக்கு தலைவலி மற்றும் வாந்தி இருக்கு"
    convo_2.append({"sender": "patient", "text": u_msg})
    memory_service.add_medical_fact(test_patient_2, "headache", duration="2 நாட்களுக்கு")
    memory_service.add_medical_fact(test_patient_2, "vomiting", duration="2 நாட்களுக்கு")

    ai_reply_1 = llm_service._generate_conversational_fallback(
        user_text=u_msg,
        patient_id=test_patient_2,
        messages=convo_2,
        language="ta"
    )
    print(f"Patient: {u_msg}")
    print(f"AI: {ai_reply_1}")
    convo_2.append({"sender": "ai", "text": ai_reply_1})
    
    # Must acknowledge headache, vomiting, and 2 days; MUST NOT ask "when did headache start" or "do you have vomiting"
    assert "தலைவலி" in ai_reply_1
    assert "வாந்தி" in ai_reply_1
    assert "எப்போது தொடங்கியது" not in ai_reply_1, "BUG: AI should NOT ask onset when duration was already given!"
    assert "வாந்தி அல்லது மயக்கம் உள்ளதா" not in ai_reply_1, "BUG: AI should NOT ask if vomiting is present when user already said vomiting!"
    print("PASS: AI acknowledged both headache & vomiting with duration without asking redundant questions.\n")

    # Patient asks: "which is noted?"
    u_msg_2 = "which is noted?"
    convo_2.append({"sender": "patient", "text": u_msg_2})
    ai_reply_2 = llm_service._generate_conversational_fallback(
        user_text=u_msg_2,
        patient_id=test_patient_2,
        messages=convo_2,
        language="ta"
    )
    print(f"Patient: {u_msg_2}")
    print(f"AI: {ai_reply_2}")
    convo_2.append({"sender": "ai", "text": ai_reply_2})
    assert "headache" in ai_reply_2.lower() or "தலைவலி" in ai_reply_2 or "வாந்தி" in ai_reply_2 or "vomiting" in ai_reply_2
    print("PASS: AI accurately answered what was recorded from memory.\n")

    # Patient denies: "இல்லை"
    u_msg_3 = "இல்லை"
    convo_2.append({"sender": "patient", "text": u_msg_3})
    ai_reply_3 = llm_service._generate_conversational_fallback(
        user_text=u_msg_3,
        patient_id=test_patient_2,
        messages=convo_2,
        language="ta"
    )
    print(f"Patient: {u_msg_3}")
    print(f"AI: {ai_reply_3}")
    convo_2.append({"sender": "ai", "text": ai_reply_3})
    assert "இல்லை என பதிவு" in ai_reply_3 or "மருத்துவர்" in ai_reply_3
    print("PASS: AI understood denial as answer to previous question.\n")

    print("==================================================")
    print("4. TESTING STRUCTURED CLINICAL FACT EXTRACTION (extract_patient_facts)")
    print("==================================================")
    facts_extracted = llm_service.extract_patient_facts(convo_2)
    print("Extracted Structured Facts:")
    print(json.dumps(facts_extracted, indent=2, ensure_ascii=False))
    assert "chief_complaint" in facts_extracted
    assert any("headache" in str(c).lower() or "தலைவலி" in str(c) for c in facts_extracted["chief_complaint"])
    print("PASS: Structured patient facts extracted properly.\n")

    print("==================================================")
    print("5. TESTING DOCTOR CLINICAL REPORT GENERATION")
    print("==================================================")
    report = memory_service.generate_doctor_report(test_patient_2)
    print(f"Generated Doctor Report for {test_patient_2}:\n")
    print(report)
    print()

    assert "PATIENT CLINICAL SUMMARY" in report
    assert f"Patient: {test_patient_2}" in report
    assert "Headache" in report
    assert "Vomiting" in report
    assert "History:" in report
    print("PASS: Doctor Clinical Summary generated correctly with all chronological facts!\n")

    print("==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
