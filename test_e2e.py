import sys
import os

# Ensure UTF-8 output on Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath('.'))

from app.services.llm_service import llm_service

test_cases = [
    ("1. Greeting", "Hi"),
    ("2. General Knowledge", "What is Python?"),
    ("3. Code Generation", "Write a Python function to calculate BMI"),
    ("4. Medical Query (English)", "i have fever for 2 days"),
    ("5. Medical Query (Tamil)", "எனக்கு இரண்டு நாட்களாக காய்ச்சல் உள்ளது"),
    ("6. Drug Info (Tamil)", "பாராசிட்டமால் மாத்திரையின் பயன்பாடுகளை விளக்கவும்"),
]

print("=== STARTING MEDIKIOSK AI E2E TESTS ===")

for title, prompt in test_cases:
    print(f"\n--- TEST: {title} ---")
    print(f"User Input: '{prompt}'")
    print("Streaming AI Output: ", end="", flush=True)
    
    collected = []
    try:
        messages = [{"sender": "patient", "text": prompt}]
        for chunk in llm_service.stream_conversational_response(messages=messages, language="en"):
            print(chunk, end="", flush=True)
            collected.append(chunk)
        full_text = "".join(collected)
        print(f"\n[Status: SUCCESS | Length: {len(full_text)} chars]")
        assert len(full_text) > 0, "Empty response"
        assert "\ufffd" not in full_text, "Found replacement character \\ufffd"
    except Exception as e:
        print(f"\n[Status: FAILED | Error: {e}]")

print("\n=== ALL TESTS COMPLETED ===")
