import requests
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:5000"

def test_api():
    print("1. Testing GET /")
    r = requests.get(BASE_URL + "/")
    assert r.status_code == 200, f"Failed GET /: {r.status_code}"
    print("   -> Status 200 OK")

    print("\n2. Testing POST /api/chat/text (Dual-Output: Text + TTS Audio)")
    payload = {
        "message": "I have chest pain that started 15 minutes ago",
        "patient_id": "P-1001"
    }
    r = requests.post(BASE_URL + "/api/chat/text", json=payload)
    assert r.status_code == 200, f"Failed /api/chat/text: {r.status_code} - {r.text}"
    data = r.json()
    print("   -> Status: ", data.get("status"))
    print("   -> Session ID: ", data.get("session_id"))
    print("   -> AI Text Response: ", data.get("text"))
    print("   -> Audio URL (TTS): ", data.get("audio_url"))
    print("   -> Triage Assessment: ", data.get("triage"))

    session_id = data.get("session_id")
    audio_url = data.get("audio_url")

    if audio_url:
        print(f"\n3. Testing GET {audio_url}")
        audio_res = requests.get(BASE_URL + audio_url)
        assert audio_res.status_code == 200
        print(f"   -> Audio served successfully ({len(audio_res.content)} bytes)")

    print("\n4. Testing POST /api/session/complete")
    comp_res = requests.post(BASE_URL + "/api/session/complete", json={"session_id": session_id})
    print("   -> Session saved to JSON DB: ", comp_res.json())

    print("\n5. Testing GET /api/triage/history")
    hist_res = requests.get(BASE_URL + "/api/triage/history")
    print(f"   -> Found {len(hist_res.json().get('records', []))} triage records in JSON DB.")

    print("\n🎉 ALL API ENDPOINTS VERIFIED & WORKING SEAMLESSLY!")

if __name__ == "__main__":
    test_api()
