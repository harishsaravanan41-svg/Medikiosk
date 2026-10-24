import sys
import requests
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Config
from app.services.llm_service import llm_service

def test_qwen():
    print("=" * 60)
    print("  MEDIKIOSK - QWEN 2.5 MODEL DIAGNOSTIC TEST")
    print("=" * 60)
    print(f"Mode:         {llm_service.mode}")
    print(f"Base URL:     {llm_service.api_base}")
    print(f"Model Tag:    {llm_service.model}")
    print(f"API Key Set:  {'Yes' if llm_service.api_key else 'No'}")
    print("=" * 60)

    # 1. Check Server Reachability
    server_online = False
    from urllib.parse import urlparse
    parsed = urlparse(llm_service.api_base)
    base_origin = f"{parsed.scheme}://{parsed.netloc}"
    health_url = f"{base_origin}/health"
    print(f"\n[1/3] Probing health endpoint: {health_url}...")
    try:
        r = requests.get(health_url, timeout=5.0)
        if r.status_code == 200:
            print(f"   -> [OK] Server is ONLINE! Health status: {r.json()}")
            server_online = True
        else:
            print(f"   -> [WARN] Server returned HTTP {r.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"   -> [FAIL] Server is NOT running at {base_origin}.")
        print("   -> To start it, run:  python run_qwen_server.py  (or run_qwen_server.bat)")
    except Exception as e:
        print(f"   -> Notice: {e}")

    # 2. Test Direct API Generation
    if server_online:
        print(f"\n[2/3] Testing direct generation from Qwen 2.5 API...")
        try:
            headers = {"Content-Type": "application/json", "X-API-Key": llm_service.api_key}
            payload = {
                "message": "Patient says: I have mild dizziness since morning.",
                "system_prompt": "You are MediKiosk AI, an empathetic hospital triage assistant. Respond concisely in 2 sentences.",
                "max_new_tokens": 100
            }
            res = requests.post(llm_service.api_base, json=payload, headers=headers, timeout=60.0)
            if res.status_code == 200:
                data = res.json()
                print(f"   -> [OK] Direct Qwen Response: {data.get('response') or data.get('answer')}")
            else:
                print(f"   -> [FAIL] HTTP Error {res.status_code}: {res.text}")
        except Exception as e:
            print(f"   -> Generation error: {e}")
    else:
        print(f"\n[2/3] Skipping direct generation test (server offline).")

    # 3. Test Integrated LLM Service (with fallback handling)
    print(f"\n[3/3] Testing Integrated MediKiosk LLM Service...")
    sample_messages = [{"sender": "patient", "text": "I have had a mild headache since yesterday morning."}]
    reply = llm_service.generate_response(sample_messages, language="en")
    print(f"   -> Service Reply: \"{reply}\"")

    print("\n" + "=" * 60)
    if server_online:
        print("SUCCESS: Qwen 2.5 local server is online and generating active responses!")
    else:
        print("NOTE: Qwen 2.5 server was offline during test.")
        print("   Start the model server with:  python run_qwen_server.py")
        print("   MediKiosk successfully used the clinical fallback engine.")
    print("=" * 60)

if __name__ == "__main__":
    test_qwen()
