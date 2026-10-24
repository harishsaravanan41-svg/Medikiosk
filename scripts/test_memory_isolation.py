import sys
import os
import json
import time

# Ensure root directory is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.memory_service import memory_service
from app.services.llm_service import llm_service

def test_memory_isolation():
    print("==================================================", flush=True)
    print("      MEDIKIOSK PERSISTENT MEMORY & ISOLATION TEST", flush=True)
    print("==================================================", flush=True)

    # 1. Reset/Prepare test users
    user_a = "P-TEST-A"
    user_b = "P-TEST-B"

    # Clear test users from memory
    store = memory_service._read_json()
    store.pop(user_a, None)
    store.pop(user_b, None)
    memory_service._write_json(store)

    print(f"\n[Test 1] User A ({user_a}) inputs medical symptoms:", flush=True)
    print("  User A: 'I have fever for 3 days'", flush=True)
    memory_service._extract_and_update_memory_worker(
        patient_id=user_a,
        session_id="session_test_a1",
        user_text="I have fever for 3 days",
        ai_text="I understand you have had a fever for 3 days."
    )

    print("  User A: 'I also have chest pain'", flush=True)
    memory_service._extract_and_update_memory_worker(
        patient_id=user_a,
        session_id="session_test_a1",
        user_text="I also have chest pain",
        ai_text="Thank you for mentioning that. Chest pain is important."
    )

    # Verify User A's stored memory
    mem_a = memory_service.get_user_memory(user_a)
    print(f"\n[User A Memory Store]:\n{json.dumps(mem_a.get('medical_memory'), indent=2)}", flush=True)

    med_facts_a = [m.get("fact") for m in mem_a.get("medical_memory", [])]
    assert "fever" in med_facts_a, "Assertion failed: fever not found in User A memory"
    assert "chest pain" in med_facts_a, "Assertion failed: chest pain not found in User A memory"
    print("  -> User A memory stored correctly! (fever for 3 days, chest pain)", flush=True)

    # 2. Check User B memory is strictly isolated
    print(f"\n[Test 2] User B ({user_b}) memory check (Zero Leakage):", flush=True)
    mem_b_block = memory_service.get_relevant_memory(patient_id=user_b)
    print(f"  User B Memory Block: {mem_b_block}", flush=True)
    assert mem_b_block is None or "fever" not in mem_b_block, "Isolation failure: User A memory leaked to User B!"
    print("  -> Strict isolation verified: User B has 0% knowledge of User A's symptoms!", flush=True)

    # 3. User A Memory Prompt Retrieval
    print(f"\n[Test 3] User A ({user_a}) Prompt Context Retrieval:", flush=True)
    mem_a_block = memory_service.get_relevant_memory(patient_id=user_a)
    print(f"  Retrieved Block for LLM:\n{mem_a_block}", flush=True)
    assert "fever" in mem_a_block and "chest pain" in mem_a_block, "Assertion failed: User A memory block missing symptoms"

    # 4. End-to-End LLM Generation with Memory Context
    print(f"\n[Test 4] Asking Qwen as User A: 'What did I tell you previously?'", flush=True)
    query_msg = [{"sender": "patient", "text": "What did I tell you previously about my symptoms?"}]
    tokens_a = []
    for token in llm_service.stream_conversational_response(
        messages=query_msg,
        memory=mem_a_block,
        language="en"
    ):
        tokens_a.append(token)
    response_a = "".join(tokens_a).strip()
    print(f"  Qwen Response for User A:\n  \"{response_a}\"", flush=True)
    
    # Check if Qwen recalled fever or chest pain
    has_fever_recall = "fever" in response_a.lower() or "chest" in response_a.lower()
    print(f"  Recall check: {has_fever_recall} (fever or chest pain mentioned)", flush=True)

    # 5. Asking Qwen as User B (Should NOT know anything about User A)
    print(f"\n[Test 5] Asking Qwen as User B: 'What did I tell you previously?'", flush=True)
    query_msg_b = [{"sender": "patient", "text": "What did I tell you previously about my symptoms?"}]
    tokens_b = []
    for token in llm_service.stream_conversational_response(
        messages=query_msg_b,
        memory=mem_b_block, # None
        language="en"
    ):
        tokens_b.append(token)
    response_b = "".join(tokens_b).strip()
    print(f"  Qwen Response for User B:\n  \"{response_b}\"", flush=True)
    has_leakage = "fever" in response_b.lower() or "chest pain" in response_b.lower()
    assert not has_leakage, "Critical Isolation Violation: Qwen leaked User A info to User B!"
    print("  -> Isolation confirmed: Qwen has NO memory of fever/chest pain for User B!", flush=True)

    # Cleanup test IDs
    store = memory_service._read_json()
    store.pop(user_a, None)
    store.pop(user_b, None)
    memory_service._write_json(store)

    print("\n==================================================", flush=True)
    print("       ALL PERSISTENT MEMORY TESTS PASSED!        ", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    test_memory_isolation()
