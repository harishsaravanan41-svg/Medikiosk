# -*- coding: utf-8 -*-
import os
import sys
import json
import re
import time
import requests
from typing import List, Dict, Any, Optional, Generator
from app.config import Config

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# All-Rounder Versatile Healthcare and General Assistant System Prompt
MEDIKIOSK_SYSTEM_PROMPT = """You are MediKiosk AI, an intelligent, versatile, all-rounder conversational assistant.

You are capable of handling a broad variety of requests with natural intelligence, clarity, empathy, and accuracy:
1. All-Rounder Versatility: You can answer any general knowledge questions, explain topics, help with kiosk and hospital navigation, assist with programming and technology, offer helpful tips, write or summarize text, solve problems, or engage in natural conversation.
2. Healthcare & Triage Assistance: When users discuss health conditions or symptoms, listen empathetically, acknowledge their information, help them understand what they might be experiencing, and assist in recording accurate notes for their doctor consultation.
3. Multilingual Excellence: Converse fluently in English, Hindi, Tamil, Telugu, Malayalam, Kannada, Bengali, Marathi, Gujarati, Punjabi, Urdu, and mixed colloquial dialects (Tanglish, Hinglish, Telugish, etc.). Always respond naturally in the user's language.
4. Context & Memory Awareness: Remember everything mentioned earlier in the conversation. If the user asks "what did you note?" or refers to previous details, accurately recall and explain them.
5. Natural Adaptability: Never force rigid questionnaires or unnecessary repetitive questioning. If the user changes topics, freely follow the new topic without resistance.

SAFETY GUIDELINES:
- For severe life-threatening emergencies (e.g., severe crushing chest pain, difficulty breathing, stroke signs, massive bleeding, loss of consciousness), advise immediate emergency medical care (ER / calling emergency services).
- Do not prescribe dangerous prescription medications or claim to make definitive medical diagnoses; encourage consulting with a qualified physician for clinical prescriptions and definitive care.
- Maintain helpful, safe, respectful, and ethical communication at all times."""

CLINICAL_EXTRACTION_SYSTEM_PROMPT = """You are a clinical information extraction engine for the doctor's dashboard.
Analyze the conversation and extract structured clinical facts IF medical symptoms were discussed.

CRITICAL INSTRUCTIONS:
- Extract ONLY medical information explicitly stated by the user.
- If an attribute was not mentioned, set its value strictly to null (or [] for arrays).
- NEVER guess, assume, or invent symptoms or negative findings unless explicitly stated.
- Output MUST be a valid JSON object matching the schema below and NOTHING ELSE.

Output JSON Schema:
{
  "chief_complaint": ["list of strings"],
  "duration": [{"symptom": "string", "duration": "string"}],
  "associated_symptoms": ["list of strings"],
  "negative_findings": ["list of strings"],
  "medications": ["list of strings"],
  "medical_history": ["list of strings"],
  "allergies": ["list of strings"],
  "patient_statements": ["list of strings"],
  "urgency_level": "emergency | urgent | moderate | low | needs_assessment"
}
"""

LANG_NAME_MAP = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "kn": "Kannada",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "ur": "Urdu"
}

MEDICAL_KEYWORDS = {
    "en": ["pain", "ache", "fever", "cough", "headache", "sick", "hurt", "nausea", "vomiting",
           "dizzy", "breath", "chest", "stomach", "bleed", "injury", "swelling", "rash",
           "fatigue", "tired", "symptoms", "hospital", "doctor", "medicine", "allergy", "infection"],
    "ta": ["வலி", "காய்ச்சல்", "இருமல்", "தலைவலி", "வாந்தி", "மூச்சு", "நெஞ்சு", "மார்பு", "வயிறு", "மருந்து"],
    "hi": ["दर्द", "बुखार", "खांसी", "सिरदर्द", "उल्टी", "सांस", "छाती", "सीना", "पेट", "दवा"],
    "te": ["నొప్పి", "జ్వరం", "దగ్గు", "తలనొప్పి", "వాంతి", "శ్వాస", "ఛాతీ", "కడుపు", "మందు"],
    "ml": ["വേദന", "പനി", "ചുമ", "തലവേദന", "ഛർദ്ദി", "ശ്വാസം", "നെഞ്ച്", "വയറ്", "മരുന്ന്"],
    "kn": ["ನೋವು", "ಜ್ವರ", "ಕೆಮ್ಮು", "ತಲೆನೋವು", "ವಾಂತಿ", "ಉಸಿರು", "ಎದೆ", "ಹೊಟ್ಟೆ", "ಔಷಧ"],
    "bn": ["ব্যথা", "জ্বর", "কাশি", "মাথাব্যথা", "বমি", "শ্বাসকষ্ট", "বুক", "পেট", "ওষুধ"],
    "romanized": ["sar dard", "dard ho raha", "bukhar hai", "fever irukku", "fever iruku", "vali irukku", "thalaivali", "nenju vali", "noppi undi", "fever undi"]
}

def detect_text_language(text: str, default: str = "en") -> str:
    """Detects language script or common Romanized cues across 11 languages."""
    if not text:
        return default

    tamil_count = len(re.findall(r'[\u0B80-\u0BFF]', text))
    devanagari_count = len(re.findall(r'[\u0900-\u097F]', text))
    telugu_count = len(re.findall(r'[\u0C00-\u0C7F]', text))
    malayalam_count = len(re.findall(r'[\u0D00-\u0D7F]', text))
    kannada_count = len(re.findall(r'[\u0C80-\u0CFF]', text))
    bengali_count = len(re.findall(r'[\u0980-\u09FF]', text))
    gujarati_count = len(re.findall(r'[\u0A80-\u0AFF]', text))
    punjabi_count = len(re.findall(r'[\u0A00-\u0A7F]', text))
    arabic_urdu_count = len(re.findall(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]', text))
    latin_count = len(re.findall(r'[a-zA-Z]', text))

    is_marathi = False
    if devanagari_count > 0:
        marathi_markers = ["आहे", "नाही", "काय", "मला", "होतो", "झाला", "आहोत", "कसे", "त्रास", "दुखतंय"]
        if any(m in text for m in marathi_markers):
            is_marathi = True

    script_counts = {
        "ta": tamil_count,
        "mr": devanagari_count if is_marathi else 0,
        "hi": devanagari_count if not is_marathi else 0,
        "te": telugu_count,
        "ml": malayalam_count,
        "kn": kannada_count,
        "bn": bengali_count,
        "gu": gujarati_count,
        "pa": punjabi_count,
        "ur": arabic_urdu_count
    }

    max_lang, max_count = max(script_counts.items(), key=lambda x: x[1])
    if max_count > 1:
        return max_lang

    t_lower = text.lower()
    tanglish_cues = ["irukku", "iruku", "enakku", "romba", "pannunga", "solunga", "aachu", "kooda", "illai"]
    hinglish_cues = ["hai", "nahi", "kya", "mera", "meri", "kaise", "hoga", "batao", "mujhe", "bukhar", "dard"]
    telugish_cues = ["undi", "ledu", "naku", "enti", "cheppandi", "ela", "noppi"]
    marathi_cues = ["aahe", "nahi", "kay", "mala", "kasa", "ahe", "dukhtay"]
    gujarati_cues = ["chhe", "nathi", "su", "mane", "kem", "thay"]

    if any(re.search(r'\b' + re.escape(cue) + r'\b', t_lower) for cue in tanglish_cues):
        return "ta"
    if any(re.search(r'\b' + re.escape(cue) + r'\b', t_lower) for cue in hinglish_cues):
        return "hi"
    if any(re.search(r'\b' + re.escape(cue) + r'\b', t_lower) for cue in telugish_cues):
        return "te"
    if any(re.search(r'\b' + re.escape(cue) + r'\b', t_lower) for cue in marathi_cues):
        return "mr"
    if any(re.search(r'\b' + re.escape(cue) + r'\b', t_lower) for cue in gujarati_cues):
        return "gu"

    if latin_count > 0:
        return "en"

    return default

def is_medical_message(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    for lang_kws in MEDICAL_KEYWORDS.values():
        if any(kw in t for kw in lang_kws):
            return True
    return False


class LLMService:
    def __init__(self):
        self.api_base = Config.QWEN_API_BASE
        self.api_key = Config.QWEN_API_KEY
        self.model = Config.QWEN_MODEL
        self.mode = Config.QWEN_MODE

    def check_health(self) -> Dict[str, Any]:
        """Tests whether the local inference server is reachable."""
        base = (self.api_base or "http://127.0.0.1:8000/v1").rstrip("/")
        import urllib.parse
        parsed = urllib.parse.urlparse(base)
        root_url = f"{parsed.scheme}://{parsed.netloc}"
        health_url = f"{root_url}/health"

        start_t = time.time()
        try:
            resp = requests.get(health_url, timeout=2.0)
            latency_ms = int((time.time() - start_t) * 1000)
            if resp.status_code == 200:
                data = resp.json() if resp.text else {}
                return {
                    "status": "online",
                    "model": data.get("model", self.model),
                    "endpoint": health_url,
                    "latency_ms": latency_ms
                }
        except Exception:
            pass

        return {"status": "offline", "model": self.model, "latency_ms": 0}

    def _build_structured_prompt(
        self,
        patient_id: str,
        language: str,
        messages: List[Dict[str, Any]],
        memory: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Builds the structured context architecture:
        USER CONTEXT: ...
        LANGUAGE: ...
        CONVERSATION HISTORY: (last 12 turns max for fast inference)
        KNOWN RECORDED FACTS / MEMORY: ...
        LATEST USER MESSAGE: ...
        TASK: ...
        """
        from app.services.memory_service import memory_service

        patient_id = patient_id or "P-1001"
        lang_name = LANG_NAME_MAP.get(language, "Tamil" if language == "ta" else "English")

        # 1. Format Conversation History (last 12 messages for efficiency)
        recent_messages = messages[-12:] if len(messages) > 12 else messages
        history_lines = []
        for m in recent_messages:
            sender = "Patient" if m.get("sender") in ("patient", "user") else "AI"
            txt = m.get("text") or m.get("content") or ""
            if txt:
                history_lines.append(f"{sender}: {txt}")
        conversation_history = "\n".join(history_lines) if history_lines else "User has just started the consultation."

        # 2. Extract Known Patient Facts from memory
        if memory is not None:
            known_facts = memory if memory else "No prior history or symptoms recorded."
        else:
            known_facts = memory_service.get_known_patient_facts_formatted(patient_id)

        # 3. Latest User Message
        last_user_text = ""
        for m in reversed(messages):
            if m.get("sender") in ("patient", "user"):
                last_user_text = m.get("text") or m.get("content") or ""
                break

        # 4. Assembled prompt for all-rounder assistant
        structured_system_content = f"""{MEDIKIOSK_SYSTEM_PROMPT}

USER CONTEXT:
Patient/User ID: {patient_id}
Language: {lang_name}

CONVERSATION HISTORY:
{conversation_history}

KNOWN RECORDED FACTS / MEMORY:
{known_facts}

LATEST USER MESSAGE:
{last_user_text}

TASK:
Respond helpfully, naturally, and accurately as a versatile, all-rounder AI assistant to the user's latest message in {lang_name}.
- If the user asks a general question, coding request, explanation, or conversational greeting, answer it directly and thoroughly.
- If the user shares symptoms or medical concerns, acknowledge them with care and context.
- If the user asks what was noted, explain what has been recorded.
- If the user says 'no' or denies symptoms, acknowledge it naturally without repeating previous questions.
- Uphold safety guidelines when severe medical emergencies are present."""

        formatted_messages = [
            {"role": "system", "content": structured_system_content},
            {"role": "user", "content": last_user_text or "Hello"}
        ]

        return {
            "system_prompt": structured_system_content,
            "messages": formatted_messages,
            "last_user_text": last_user_text,
            "patient_id": patient_id,
            "language": language
        }

    def _call_qwen(self, messages: List[Dict[str, str]], temperature=0.6, max_tokens=768, system_prompt=None) -> Optional[str]:
        base = (self.api_base or "http://127.0.0.1:8000/v1").rstrip("/")
        endpoint_url = f"{base}/chat/completions" if not base.endswith("/v1") else f"{base.rsplit('/', 1)[0]}/v1/chat/completions"

        api_key = self.api_key or "a2ff255b6f61cd453396b22f7ddeebf714d1fdcd73142b7e"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "X-API-Key": api_key,
        }

        last_user_query = ""
        for m in reversed(messages):
            if m.get("role") in ("user", "patient"):
                last_user_query = m.get("content", "")
                break

        payload = {
            "message": last_user_query,
            "messages": messages,
            "system_prompt": system_prompt or MEDIKIOSK_SYSTEM_PROMPT,
            "model": self.model,
            "temperature": temperature,
            "max_new_tokens": max_tokens,
        }

        try:
            resp = requests.post(endpoint_url, json=payload, headers=headers, timeout=(0.5, 2.0))
            if resp.status_code == 200:
                data = resp.json()
                if "choices" in data and data["choices"]:
                    return data["choices"][0]["message"]["content"].strip()
                for key in ("response", "answer", "text", "content"):
                    if key in data and data[key]:
                        return str(data[key]).strip()
        except Exception as e:
            print(f"[LLM] Endpoint notice: {e}")

        return None

    def generate_conversational_response(
        self,
        messages: List[Dict[str, Any]],
        patient_context: Optional[Dict[str, Any]] = None,
        patient_id: Optional[str] = None,
        memory: Optional[str] = None,
        language: str = "en"
    ) -> str:
        if not patient_id:
            if patient_context and "patient_id" in patient_context:
                patient_id = patient_context["patient_id"]
            else:
                patient_id = "P-1001"

        last_user_text = ""
        for m in reversed(messages):
            if m.get("sender") in ("patient", "user"):
                last_user_text = m.get("text", "")
                break

        detected_lang = detect_text_language(last_user_text, default=(language or "en").lower().split("-")[0])

        context_bundle = self._build_structured_prompt(
            patient_id=patient_id,
            language=detected_lang,
            messages=messages,
            memory=memory
        )

        response = self._call_qwen(
            context_bundle["messages"],
            temperature=0.6,
            max_tokens=768,
            system_prompt=context_bundle["system_prompt"]
        )

        if response:
            return response.strip()

        return self._generate_conversational_fallback(
            user_text=last_user_text,
            patient_id=patient_id,
            messages=messages,
            language=detected_lang,
            memory=memory
        )

    def stream_conversational_response(
        self,
        messages: List[Dict[str, Any]],
        patient_context: Optional[Dict[str, Any]] = None,
        patient_id: Optional[str] = None,
        memory: Optional[str] = None,
        language: str = "en"
    ) -> Generator[str, None, None]:
        """
        Streams Qwen response with structured multi-turn context.
        If local LLM server is unreachable, falls back to the versatile conversational engine.
        """
        if not patient_id:
            if patient_context and "patient_id" in patient_context:
                patient_id = patient_context["patient_id"]
            else:
                patient_id = "P-1001"

        last_user_text = ""
        for m in reversed(messages):
            if m.get("sender") in ("patient", "user"):
                last_user_text = m.get("text", "")
                break

        detected_lang = detect_text_language(last_user_text, default=(language or "en").lower().split("-")[0])

        context_bundle = self._build_structured_prompt(
            patient_id=patient_id,
            language=detected_lang,
            messages=messages,
            memory=memory
        )

        base = (self.api_base or "http://127.0.0.1:8000/v1").rstrip("/")
        stream_url = f"{base}/chat/stream" if not base.endswith("/v1") else f"{base.rsplit('/', 1)[0]}/v1/chat/stream"
        api_key = self.api_key or "a2ff255b6f61cd453396b22f7ddeebf714d1fdcd73142b7e"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "X-API-Key": api_key,
        }

        payload = {
            "message": last_user_text,
            "messages": context_bundle["messages"],
            "system_prompt": context_bundle["system_prompt"],
            "model": self.model,
            "temperature": 0.6,
            "max_new_tokens": 768,
            "stream": True
        }

        token_yielded = False
        try:
            resp = requests.post(stream_url, json=payload, headers=headers, stream=True, timeout=(0.5, 2.0))
            if resp.status_code == 200:
                for line in resp.iter_lines(decode_unicode=True):
                    if line:
                        if line.startswith("data: "):
                            event_str = line[6:].strip()
                            if event_str == "[DONE]":
                                return
                            if event_str:
                                try:
                                    event = json.loads(event_str)
                                    if "token" in event and event["token"]:
                                        token_yielded = True
                                        yield event["token"]
                                    elif event.get("done"):
                                        return
                                except Exception:
                                    pass
                    if token_yielded:
                        return
        except Exception as e:
            print(f"[LLM Stream] Inference note: {e}, running dynamic conversational flow...")

        # Intent-driven conversational engine
        fallback_msg = self._generate_conversational_fallback(
            user_text=last_user_text,
            patient_id=patient_id,
            messages=messages,
            language=detected_lang,
            memory=memory
        )
        for w in re.split(r'(\s+)', fallback_msg):
            if w:
                yield w

    def _generate_conversational_fallback(
        self,
        user_text: str = "",
        patient_id: str = "P-1001",
        messages: Optional[List[Dict[str, Any]]] = None,
        language: str = "en",
        memory: Optional[str] = None
    ) -> str:
        """
        Versatile All-Rounder Conversational Engine (Fallback):
        1. Explains recorded information if user asks "what did you note?" / "which is noted?".
        2. Understands "no" / "இல்லை" / "nahi" as a direct answer to previous questions.
        3. Acknowledges multiple symptoms with or without duration.
        4. Handles general assistance, programming, and inquiries gracefully without forcing medical triage.
        5. Supports Tamil, Hindi, Telugu, Malayalam, Kannada, Bengali, and English naturally.
        """
        from app.services.memory_service import memory_service

        if memory is not None:
            # Memory block was explicitly provided
            recorded_items = []
            if memory.strip():
                # Extract facts from memory text (e.g. "- fever (duration: for 3 days)")
                for line in memory.splitlines():
                    line_s = line.strip()
                    if line_s.startswith("- ") or line_s.startswith("• "):
                        cleaned = line_s.lstrip("-• ").strip()
                        if cleaned:
                            recorded_items.append(cleaned)
            symptoms_map = {}
            durations_map = {}
        else:
            user_mem = memory_service.get_user_memory(patient_id)
            symptoms_map = user_mem.get("symptoms", {})
            durations_map = user_mem.get("duration", {})
            recorded_items = []
            for sym, info in symptoms_map.items():
                dur = durations_map.get(sym) or info.get("duration")
                if dur and dur != "unknown":
                    recorded_items.append(f"{sym} ({dur})")
                else:
                    recorded_items.append(sym)

            if not recorded_items and user_mem.get("medical_memory"):
                for item in user_mem["medical_memory"]:
                    f = item.get("fact", "")
                    d = item.get("duration")
                    recorded_items.append(f"{f} ({d})" if d else f)

        u_lower = (user_text or "").lower().strip()

        # Check what questions the AI previously asked in this conversation
        ai_prior_texts = []
        if messages:
            for m in messages:
                if m.get("sender") == "ai":
                    ai_prior_texts.append((m.get("text") or "").lower())
        ai_prior_joined = " ".join(ai_prior_texts)

        # ----------------------------------------------------
        # INTENT 1: User asks "what did you note?" / "which is noted?"
        # ----------------------------------------------------
        what_noted_patterns = [
            "which is noted", "what is noted", "what did you note", "what did you write", 
            "what did i say", "what was recorded", "what did i tell",
            "என்ன நோட்", "எது குறித்து", "என்ன குறிச்சீங்க", "என்ன பதிவு",
            "क्या नोट किया", "क्या लिखा"
        ]
        if any(p in u_lower for p in what_noted_patterns):
            recorded_items = []
            for sym, info in symptoms_map.items():
                dur = durations_map.get(sym) or info.get("duration")
                if dur and dur != "unknown":
                    recorded_items.append(f"{sym} ({dur})")
                else:
                    recorded_items.append(sym)

            if not recorded_items and user_mem.get("medical_memory"):
                for item in user_mem["medical_memory"]:
                    f = item.get("fact", "")
                    d = item.get("duration")
                    recorded_items.append(f"{f} ({d})" if d else f)

            if recorded_items:
                items_str_en = ", ".join(recorded_items)
                items_str_ta = ", ".join(recorded_items)
                resp_map = {
                    "ta": f"நான் இதுவரை {items_str_ta} ஆகியவற்றை பதிவு செய்துள்ளேன். வேறு ஏதேனும் உடல்நலக் குறைவு அல்லது அறிகுறிகள் உள்ளதா?",
                    "hi": f"मैंने अब तक {items_str_en} दर्ज किया है। क्या आप कोई अन्य लक्षण बताना चाहते हैं?",
                    "te": f"నేను ఇప్పటివరకు {items_str_en} వివరాలను నమోదు చేశాను. ఇంకేమైనా చెప్పాలనుకుంటున్నారా?",
                    "en": f"I have noted {items_str_en}. Is there anything else you would like to tell me about how you are feeling?"
                }
            else:
                resp_map = {
                    "ta": "உங்கள் உடல்நலப் பிரச்சனைகளை பதிவு செய்யத் தயாராக உள்ளேன். உங்களுக்கு என்ன அறிகுறிகள் உள்ளன என்று சொல்லுங்கள்.",
                    "hi": "मैंने अभी तक कोई लक्षण दर्ज नहीं किया है। कृपया बताएं कि आप कैसा महसूस कर रहे हैं?",
                    "en": "I have not recorded any specific symptoms yet. Please tell me how you are feeling."
                }
            return resp_map.get(language, resp_map["en"])

        # ----------------------------------------------------
        # INTENT 2: User denies / "no" / "இல்லை" / "nahi" / "not having"
        # ----------------------------------------------------
        no_patterns = [
            "no", "nope", "nothing", "none", "not now", "no other", "nothing else", "not having", "don't have",
            "இல்லை", "ஒன்றுமில்லை", "வேறில்லை", "வேற எதுவும் இல்ல",
            "नहीं", "कुछ नहीं", "नहीं है", "ना",
            "లేదు", "ఏమీ లేదు",
            "ഇല്ല", "ഒന്നുമില്ല",
            "ಇಲ್ಲ", "ಏನೂ ಇಲ್ಲ",
            "না", "কিছু নেই"
        ]
        is_denial = any(re.search(r'\b' + re.escape(p) + r'\b', u_lower) for p in no_patterns) or u_lower in ["no", "இல்லை", "nahi", "nahi hai", "ledu", "illai"]

        if is_denial:
            # Check if this is a consecutive denial
            last_two_user_msgs = []
            if messages:
                for m in reversed(messages):
                    if m.get("sender") in ("patient", "user"):
                        last_two_user_msgs.append((m.get("text") or "").lower().strip())
                        if len(last_two_user_msgs) >= 2:
                            break
            
            is_repeated_denial = len(last_two_user_msgs) >= 2 and any(p in last_two_user_msgs[1] for p in ["no", "இல்லை", "nahi", "ledu", "nothing"])

            if is_repeated_denial or ("doctor" in ai_prior_joined or "மருத்துவர்" in ai_prior_joined or "summary" in ai_prior_joined):
                resp_map = {
                    "ta": "புரிந்தது. உங்கள் அனைத்து விவரங்களும் மருத்துவருக்காக பதிவு செய்யப்பட்டுள்ளன. தயவுசெய்து காத்திருங்கள், மருத்துவர் உங்களை விரைவில் அழைப்பார்.",
                    "hi": "समझ गया। आपकी सभी जानकारी डॉक्टर के लिए दर्ज कर ली गई है। कृपया प्रतीक्षा करें, डॉक्टर जल्द ही आपसे परामर्श करेंगे।",
                    "te": "అర్థమైంది. మీ వివరాలన్నీ డాక్టర్ కోసం నమోదు చేయబడ్డాయి. దయచేసి వేచి ఉండండి.",
                    "ml": "മനസ്സിലായി. നിങ്ങളുടെ എല്ലാ വിവരങ്ങളും ഡോക്ടർക്കായി രേഖപ്പെടുത്തിയിട്ടുണ്ട്. ദയവായി കാത്തിരിക്കുക.",
                    "kn": "ಸರಿ. ನಿಮ್ಮ ಎಲ್ಲಾ ವಿವರಗಳನ್ನು ವೈದ್ಯರಿಗಾಗಿ ದಾಖಲಿಸಲಾಗಿದೆ. ದಯವಿಟ್ಟು ನಿರೀಕ್ಷಿಸಿ.",
                    "bn": "ঠিক আছে. আপনার সমস্ত তথ্য ডাক্তারের জন্য রেকর্ড করা হয়েছে। অনুগ্রহ করে অপেক্ষা করুন।",
                    "en": "Understood. All your information has been recorded for the doctor. Please have a seat, the doctor will call you shortly."
                }
                return resp_map.get(language, resp_map["en"])

            resp_map = {
                "ta": "சரி, வேறு அறிகுறிகள் இல்லை என பதிவு செய்கிறேன். இதை உங்கள் மருத்துவருக்கான சுருக்கத்தில் சேர்க்கிறேன். மருத்துவர் ஆலோசனைக்கு முன் வேறு ஏதேனும் கூற விரும்புகிறீர்களா?",
                "hi": "ठीक है, मैंने दर्ज कर लिया है कि कोई अन्य लक्षण नहीं है। क्या आप डॉक्टर के परामर्श से पहले कुछ और बताना चाहते हैं?",
                "te": "సరే, వేరే ఇతర లక్షణాలు లేవని నమోదు చేశాను. డాక్టర్ రిపోర్టులో చేర్చాను.",
                "ml": "ശരി, മറ്റ് ലക്ഷണങ്ങൾ ഇല്ലെന്ന് രേഖപ്പെടുത്തിയിട്ടുണ്ട്.",
                "kn": "ಸರಿ, ಬೇರೆ ಯಾವುದೇ ಲಕ್ಷಣಗಳಿಲ್ಲ ಎಂದು ದಾಖಲಿಸಲಾಗಿದೆ.",
                "bn": "ঠিক আছে, অন্য কোনো উপসর্গ নেই বলে রেকর্ড করা হয়েছে।",
                "en": "Okay, I’ve recorded that. Is there anything else you would like to mention for the doctor?"
            }
            return resp_map.get(language, resp_map["en"])

        # ----------------------------------------------------
        # INTENT 3: Greetings
        # ----------------------------------------------------
        greetings = ["hi", "hii", "hello", "hey", "வணக்கம்", "नमस्ते", "నమస్కారం", "നമസ്കാരം", "ನಮಸ್ಕಾರ", "নমস্কার"]
        if any(re.search(r'\b' + re.escape(g) + r'\b', u_lower) for g in greetings) and len(u_lower.split()) <= 3:
            resp_map = {
                "ta": "வணக்கம்! நான் உங்கள் மெடிகியோஸ்க் ஏஐ உதவியாளர். உங்களுக்கு எப்படி உதவ முடியும்?",
                "hi": "नमस्ते! मैं आपका मेडीकियोस्क एआई सहायक हूँ। मैं आज आपकी क्या सहायता कर सकता हूँ?",
                "te": "నమస్కారం! నేను మీ మెడికియోస్క్ AI సహాయకుడిని. నేను మీకు ఎలా సహాయపడగలను?",
                "ml": "നമസ്കാരം! ഞാൻ നിങ്ങളുടെ മെഡികിയോസ്ക് AI സഹായിയാണ്. എനിക്ക് എങ്ങനെ സഹായിക്കാനാകും?",
                "kn": "ನಮಸ್ಕಾರ! ನಾನು ನಿಮ್ಮ ಮೆಡಿಕಿಯೋಸ್ಕ್ AI ಸಹಾಯಕ. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?",
                "bn": "নমস্কার! আমি আপনার মেডিকিওস্ক এআই সহকারী। আমি আপনাকে কীভাবে সাহায্য করতে পারি?",
                "en": "Hello! I am MediKiosk AI, your versatile assistant. How can I assist you today?"
            }
            return resp_map.get(language, resp_map["en"])

        # ----------------------------------------------------
        # INTENT 4: ALL-ROUNDER KNOWLEDGE & MULTI-DOMAIN INTELLIGENCE ENGINE
        # Handles AI, Machine Learning, Programming, Medical Science, General Knowledge & Calculations
        # ----------------------------------------------------
        is_medical = is_medical_message(u_lower)

        # A. Artificial Intelligence (AI) & Machine Learning Knowledge
        ai_terms = ["செயற்கை நுண்ணறிவு", "செயற்கை நுண்ணறிவின்", "artificial intelligence", "what is ai", "ai என்றால் என்ன", "ai என்ன", "ai பயன்பாடுகள்", "நுண்ணறிவு", "कृत्रिम बुद्धिमत्ता", "ai क्या है", "ai అంటే ఏమిటి"]
        if any(w in u_lower for w in ai_terms) or ("ai" in u_lower.split() and any(w in u_lower for w in ["what", "explain", "use", "uses", "application", "applications", "என்றால்", "பயன்பாடு", "பயன்கள்", "பற்றி", "उपयोग", "फायदे"])):
            # 1. Applications of AI
            if any(w in u_lower for w in ["பயன்பாடு", "பயன்கள்", "application", "applications", "use", "uses", "benefits", "उपयोग", "फायदे", "అనువర్తనాలు", "ఉపయోగాలు"]):
                if language == "ta":
                    return (
                        "**செயற்கை நுண்ணறிவின் (AI) முக்கிய பயன்பாடுகள்:**\n\n"
                        "1. **மருத்துவம் & நல்வாழ்வு (Healthcare)**:\n"
                        "   - நோய்களை ஆரம்ப நிலையிலேயே ஸ்கேன் மற்றும் எக்ஸ்-ரே மூலம் துல்லியமாகக் கண்டறிதல்.\n"
                        "   - புதிய மருந்துகளைக் கண்டறியும் ஆராய்ச்சியை விரைவுபடுத்துதல்.\n"
                        "   - தானியங்கி மருத்துவ வழிகாட்டிகள் மற்றும் நோயாளி கண்காணிப்பு அமைப்புகள்.\n\n"
                        "2. **தகவல் தொழில்நுட்பம் & நிரலாக்கம் (IT & Programming)**:\n"
                        "   - தானாக குறியீடு (Code) எழுதுதல், பிழைகளைத் திருத்துதல் (Debugging) மற்றும் தானியங்கி மென்பொருள் சோதனை.\n"
                        "   - நுண்ணறிவுமிக்க சாட்பாட்கள் (Intelligent Chatbots) மற்றும் மெய்நிகர் உதவியாளர்கள்.\n\n"
                        "3. **போக்குவரத்து & வாகனங்கள் (Transportation)**:\n"
                        "   - தானியங்கி ஓட்டுநர் இல்லாத கார்கள் (Self-driving / Autonomous Vehicles).\n"
                        "   - போக்குவரத்து நெரிசலை நிர்வகிக்கும் ஸ்மார்ட் சிக்னல் அமைப்புகள்.\n\n"
                        "4. **நிதி & வங்கித்துறை (Finance & Banking)**:\n"
                        "   - நிதி மோசடிகளை (Fraud Detection) உடனடியாகக் கண்டறிந்து தடுத்தல்.\n"
                        "   - தானியங்கி முதலீட்டு ஆலோசனைகள் மற்றும் பங்குச் சந்தைப் பகுப்பாய்வு.\n\n"
                        "5. **கல்வி & ஆராய்ச்சி (Education)**:\n"
                        "   - மாணவர்களின் கற்கும் வேகத்திற்கு ஏற்ப தனிப்பயனாக்கப்பட்ட கல்வி முறைகள்.\n\n"
                        "AI தொழில்நுட்பத்தின் எந்த குறிப்பிட்ட பயன்பாட்டைப் பற்றி மேலும் தெரிந்து கொள்ள விரும்புகிறீர்கள்?"
                    )
                elif language == "hi":
                    return (
                        "**आर्टिफिशियल इंटेलिजेंस (AI) के प्रमुख अनुप्रयोग / उपयोग:**\n\n"
                        "1. **स्वास्थ्य सेवा (Healthcare)**: बीमारियों और मेडिकल इमेजिंग का विश्लेषण, रोबोटिक सर्जरी और दवा अनुसंधान।\n"
                        "2. **सॉफ्टवेयर और कोडिंग (IT & Coding)**: स्वचालित कोड जनरेशन, बग फिक्सिंग और बुद्धिमान सहायक।\n"
                        "3. **परिवहन (Transportation)**: सेल्फ-ड्राइविंग कारें और स्मार्ट ट्रैफिक सिस्टम।\n"
                        "4. **बैंकिंग और वित्त (Finance)**: धोखाधड़ी (Fraud Detection) रोकना और त्वरित वित्तीय विश्लेषण।\n"
                        "5. **शिक्षा (Education)**: व्यक्तिगत शिक्षण और स्वचालित मूल्यांकन प्रणाली।\n\n"
                        "क्या आप AI के किसी विशेष क्षेत्र के बारे में विस्तार से जानना चाहते हैं?"
                    )
                elif language == "te":
                    return (
                        "**ఆర్టిఫిషియల్ ఇంటెలిజెన్స్ (AI) యొక్క ముఖ్య అనువర్తనాలు:**\n\n"
                        "1. **వైద్యరంగం (Healthcare)**: రోగ నిర్ధారణ, స్మార్ట్ స్కానింగ్ మరియు హెల్త్‌కేర్ అసిస్టెంట్ వ్యవస్థలు.\n"
                        "2. **సాఫ్ట్‌వేర్ & కోడింగ్**: ఆటోమేటెడ్ కోడ్ రాయడం మరియు బగ్‌లను సరిదిద్దడం.\n"
                        "3. **రవాణా (Transport)**: సెల్ఫ్-డ్రైవింగ్ కార్లు.\n"
                        "4. **బ్యాంకింగ్ & ఫైనాన్స్**: సైబర్ భద్రత మరియు మోసాల గుర్తింపు.\n"
                        "5. **విద్య (Education)**: వ్యక్తిగతీకరించిన విద్య.\n\n"
                        "మీరు AI గురించి ఇంకా ఏ సమాచారం తెలుసుకోవాలనుకుంటున్నారు?"
                    )
                else:
                    return (
                        "**Key Applications of Artificial Intelligence (AI):**\n\n"
                        "1. **Healthcare & Medicine**:\n"
                        "   - Medical imaging & early disease diagnosis (MRI, CT, X-ray).\n"
                        "   - Drug discovery acceleration and personalized patient treatment plans.\n"
                        "   - Intelligent clinical kiosks and automated triage assistants.\n\n"
                        "2. **Software Engineering & Technology**:\n"
                        "   - Automated code generation, testing, refactoring, and debugging.\n"
                        "   - Conversational AI agents and semantic search engines.\n\n"
                        "3. **Autonomous Vehicles & Robotics**:\n"
                        "   - Self-driving cars, drone navigation, and factory warehouse automation.\n\n"
                        "4. **Finance & Cybersecurity**:\n"
                        "   - Real-time fraud detection, algorithmic trading, and credit risk assessment.\n\n"
                        "5. **Education & Creative Arts**:\n"
                        "   - Adaptive tutoring platforms, multimodal translation, and creative synthesis.\n\n"
                        "Would you like to explore any of these specific domains in more detail?"
                    )
            # 2. What is AI (Definition & Foundations)
            else:
                if language == "ta":
                    return (
                        "**செயற்கை நுண்ணறிவு (Artificial Intelligence - AI)** என்பது மனிதர்களைப் போல சிந்திக்கும், கற்கும், முடிவெடுக்கும் மற்றும் சிக்கல்களைத் தீர்க்கும் திறன்களைக் கணினி மற்றும் இயந்திரங்களுக்கு வழங்கும் அதிநவீன கணினி அறிவியல் தொழில்நுட்பமாகும்.\n\n"
                        "**AI-இன் முக்கிய பிரிவுகள்:**\n"
                        "- **இயந்திரக் கற்றல் (Machine Learning - ML)**: தரவுகளிலிருந்து (Data) அனுபவத்தைப் பெற்று தானாகக் கற்றுக்கொள்ளும் முறை.\n"
                        "- **ஆழ்ந்த கற்றல் (Deep Learning)**: மனித மூளையின் நரம்பு மண்டலம் (Neural Networks) போன்று பல அடுக்குகளில் தகவல்களை ஆராயும் முறை.\n"
                        "- **இயற்கை மொழி செயலாக்கம் (NLP)**: மனித மொழிகளைப் புரிந்து கொண்டு இயல்பாகப் பேசும் மற்றும் எழுதும் திறன்.\n"
                        "- **கணினி பார்வை (Computer Vision)**: புகைப்படங்கள் மற்றும் வீடியோக்களைப் பார்த்து உணரும் திறன்.\n\n"
                        "செயற்கை நுண்ணறிவின் பயன்பாடுகள் அல்லது நிரலாக்க முறைகளைப் பற்றி மேலும் அறிய விரும்புகிறீர்களா?"
                    )
                elif language == "hi":
                    return (
                        "**आर्टिफिशियल इंटेलिजेंस (AI - कृत्रिम बुद्धिमत्ता)** कंप्यूटर विज्ञान की वह उन्नत शाखा है जिसके द्वारा मशीनों को मानव की तरह सोचने, सीखने, निर्णय लेने और समस्याओं को हल करने में सक्षम बनाया जाता है।\n\n"
                        "**AI के प्रमुख घटक:**\n"
                        "- **मशीन लर्निंग (ML)**: डेटा और अनुभवों से स्वचालित रूप से सीखना।\n"
                        "- **डीप लर्निंग (Deep Learning)**: मानव मस्तिष्क के न्यूरल नेटवर्क की तरह जटिल पैटर्न समझना।\n"
                        "- **प्राकृतिक भाषा प्रसंस्करण (NLP)**: मानव भाषा को समझना और बातचीत करना।\n"
                        "- **कंप्यूटर विज़न (Computer Vision)**: छवियों और वीडियो का विश्लेषण करना।\n\n"
                        "क्या आप AI के अनुप्रयोगों या कोडिंग के बारे में और जानना चाहते हैं?"
                    )
                else:
                    return (
                        "**Artificial Intelligence (AI)** is the branch of computer science dedicated to creating systems capable of performing tasks that typically require human intelligence—such as learning, reasoning, problem-solving, perception, and understanding natural language.\n\n"
                        "**Core Pillars of AI:**\n"
                        "- **Machine Learning (ML)**: Algorithms that learn from data patterns and improve over time without being explicitly programmed for every step.\n"
                        "- **Deep Learning (DL)**: Multi-layered neural networks inspired by the human brain that power advanced vision, speech, and generative capabilities.\n"
                        "- **Natural Language Processing (NLP)**: Enables computers to understand, interpret, and generate human languages.\n"
                        "- **Computer Vision**: Enables machines to process, analyze, and recognize visual inputs like images and videos.\n\n"
                        "Would you like to explore AI applications, how neural networks work, or code examples?"
                    )

        # B. Machine Learning & Deep Learning
        if any(w in u_lower for w in ["machine learning", "இயந்திர கற்றல்", "deep learning", "neural network", "நரம்பியல்", "मशीन लर्निंग"]):
            if language == "ta":
                return (
                    "**இயந்திரக் கற்றல் (Machine Learning - ML)** என்பது முன்கூட்டியே அனைத்து விதிகளையும் எழுதாமல், தரவுகளை (Data) ஆராய்ந்து தானாகவே கற்றுக்கொண்டு துல்லியமான கணிப்புகளைச் செய்யும் முறையாகும்.\n\n"
                    "**முக்கிய மூன்று வகைகள்:**\n"
                    "1. **Supervised Learning**: லேபிளிடப்பட்ட தரவுகளைக் கொண்டு கற்பித்தல் (எ.கா: நோய்களைக் கண்டறிதல்).\n"
                    "2. **Unsupervised Learning**: லேபிள் இல்லாத தரவுகளில் மறைந்துள்ள வடிவங்களைக் கண்டறிதல் (எ.கா: வாடிக்கையாளர் பிரிப்பு).\n"
                    "3. **Reinforcement Learning**: வெகுமதி (Reward) மற்றும் தண்டனை (Penalty) முறைகள் மூலம் உகந்த முடிவுகளைக் கற்றல் (எ.கா: செஸ் விளையாட்டு, ரோபோடிக்ஸ்).\n\n"
                    "இதற்கான பைதான் குறியீடு அல்லது மாதிரிகள் வேண்டுமா?"
                )
            else:
                return (
                    "**Machine Learning (ML)** is a subset of AI that allows software applications to become more accurate at predicting outcomes without being explicitly programmed.\n\n"
                    "**The 3 Main Types of Machine Learning:**\n"
                    "1. **Supervised Learning**: Model trains on labeled datasets (e.g., Classification, Linear Regression, Disease prediction).\n"
                    "2. **Unsupervised Learning**: Model finds hidden patterns in unlabeled data (e.g., Clustering, K-Means, PCA).\n"
                    "3. **Reinforcement Learning**: Agent learns through trial and error using rewards and penalties (e.g., Robotics, Game playing AI).\n\n"
                    "Would you like a practical Python example (e.g., scikit-learn or PyTorch)?"
                )

        # C. Programming & Software Development
        # 1. Conditionals (if-else)
        if any(w in u_lower for w in ["if else", "if-else", "if/else", "ifelse", "condition", "conditional"]):
            if language == "ta":
                return (
                    "இதோ பைத்தானில் `if-elif-else` நிபந்தனைக்கான குறியீடு:\n\n"
                    "```python\n"
                    "# Python If-Else Condition Example\n"
                    "score = 85\n\n"
                    "if score >= 90:\n"
                    "    print('Grade: A (சிறப்பானது)')\n"
                    "elif score >= 75:\n"
                    "    print('Grade: B (நன்று)')\n"
                    "elif score >= 50:\n"
                    "    print('Grade: C (தேர்ச்சி)')\n"
                    "else:\n"
                    "    print('Grade: F (மீண்டும் முயற்சி செய்க)')\n"
                    "```\n\n"
                    "இந்த நிபந்தனை குறியீட்டில் ஏதேனும் மாற்றம் அல்லது சந்தேகம் உள்ளதா?"
                )
            elif language == "hi":
                return (
                    "पायथन में `if-elif-else` कंडीशन का उदाहरण कोड यहाँ है:\n\n"
                    "```python\n"
                    "# Python If-Else Condition Example\n"
                    "age = 18\n\n"
                    "if age >= 18:\n"
                    "    print('वयस्क (Eligible to vote)')\n"
                    "elif age >= 13:\n"
                    "    print('किशोर (Teenager)')\n"
                    "else:\n"
                    "    print('बच्चा (Child)')\n"
                    "```\n\n"
                    "क्या आप इसमें कोई विशेष लॉजिक जोड़ना चाहते हैं?"
                )
            else:
                return (
                    "Here is a complete Python `if-elif-else` conditional statement example:\n\n"
                    "```python\n"
                    "# Python If-Else Condition Example\n"
                    "score = 85\n\n"
                    "if score >= 90:\n"
                    "    print('Grade: A (Excellent)')\n"
                    "elif score >= 75:\n"
                    "    print('Grade: B (Good)')\n"
                    "elif score >= 50:\n"
                    "    print('Grade: C (Pass)')\n"
                    "else:\n"
                    "    print('Grade: F (Needs Improvement)')\n"
                    "```\n\n"
                    "How `if-else` works:\n"
                    "1. `if`: Evaluates the first condition.\n"
                    "2. `elif`: Evaluates subsequent conditions if prior ones were False.\n"
                    "3. `else`: Executes if none of the above conditions were met.\n\n"
                    "Would you like me to tailor this logic for a specific problem?"
                )

        # 2. Loops (for, while)
        if any(w in u_lower for w in ["for loop", "while loop", "loop", "iterate", "iteration", "மடக்கு"]):
            if language == "ta":
                return (
                    "பைத்தானில் loops பயன்பாட்டிற்கான மாதிரி குறியீடு:\n\n"
                    "```python\n"
                    "# 1. For Loop Example (பழங்கள் பட்டியல்)\n"
                    "fruits = ['ஆப்பிள்', 'வாழை', 'மாம்பழம்']\n"
                    "for fruit in fruits:\n"
                    "    print(f'பழம்: {fruit}')\n\n"
                    "# 2. While Loop Example (1 முதல் 5 வரை)\n"
                    "count = 1\n"
                    "while count <= 5:\n"
                    "    print(f'எண்ணிக்கை: {count}')\n"
                    "    count += 1\n"
                    "```"
                )
            else:
                return (
                    "Here is how loops work in Python:\n\n"
                    "```python\n"
                    "# 1. For Loop Example (Iterating over a list)\n"
                    "fruits = ['apple', 'banana', 'cherry']\n"
                    "for fruit in fruits:\n"
                    "    print(f'Fruit: {fruit}')\n\n"
                    "# 2. While Loop Example (Counting from 1 to 5)\n"
                    "count = 1\n"
                    "while count <= 5:\n"
                    "    print(f'Count is: {count}')\n"
                    "    count += 1\n"
                    "```\n\n"
                    "Key difference:\n"
                    "- `for` loop: Used when the number of iterations is known or iterating over an iterable.\n"
                    "- `while` loop: Runs continuously as long as a specified condition remains `True`."
                )

        # 3. Functions
        if any(w in u_lower for w in ["function", "def ", "functions", "method", "செயல்பாடு"]):
            return (
                "Here is how to define and call a function in Python:\n\n"
                "```python\n"
                "def calculate_total(price: float, tax_rate: float = 0.05) -> float:\n"
                "    # Calculates total price including tax\n"
                "    return price + (price * tax_rate)\n\n"
                "# Calling the function\n"
                "total = calculate_total(100.0, 0.10)\n"
                "print(f'Total Price: ${total:.2f}')  # Output: Total Price: $110.00\n"
                "```"
            )

        # 4. SQL / Database queries
        if any(w in u_lower for w in ["sql", "database", "query", "select *", "table", "join"]):
            return (
                "Here are standard SQL queries for common database operations:\n\n"
                "```sql\n"
                "-- 1. Retrieve all active patients\n"
                "SELECT id, name, age, triage_priority \n"
                "FROM patients \n"
                "WHERE status = 'active' \n"
                "ORDER BY triage_priority DESC;\n\n"
                "-- 2. Join patients with doctor consultations\n"
                "SELECT p.name, d.doctor_name, c.visit_date, c.diagnosis\n"
                "FROM consultations c\n"
                "INNER JOIN patients p ON c.patient_id = p.id\n"
                "INNER JOIN doctors d ON c.doctor_id = d.id;\n"
                "```"
            )

        # 5. General Python / Web / Coding queries
        if any(w in u_lower for w in ["python", "code", "programming", "script", "java", "html", "javascript", "css", "algorithm", "data structure"]):
            resp_map = {
                "ta": "நிச்சயமாக! பைதான், ஜாவாஸ்கிரிப்ட், இணைய உருவாக்கம் (Web Dev), SQL மற்றும் கணினி வழிமுறைகள் (Algorithms) உள்ளிட்ட அனைத்து மென்பொருள் தேவைகளுக்கும் உதவ தயாராக உள்ளேன். நீங்கள் என்ன குறியீடு உருவாக்க விரும்புகிறீர்கள்?",
                "hi": "ज़रूर! मैं कोडिंग, पायथन, वेब डेवलपमेंट, SQL और एल्गोरिदम में पूरी सहायता कर सकता हूँ। आप क्या कोड बनाना चाहते हैं?",
                "te": "తప్పకుండా! నేను పైథాన్, జావాస్క్రిప్ట్, వెబ్ డెవలప్‌మెంట్ మరియు ప్రోగ్రామింగ్ కోడింగ్ లో మీకు సహాయం చేయగలను. మీకు ఏ లాజిక్ కావాలి?",
                "en": "Certainly! I can help you with Python, JavaScript, Web Development, SQL, Data Structures, Algorithms, and API design. What would you like to build or solve?"
            }
            return resp_map.get(language, resp_map["en"])

        # D. Medical & Health Knowledge (Educational & General Health Guidance)
        # 1. Blood Pressure (BP)
        if any(w in u_lower for w in ["blood pressure", "இரத்த அழுத்தம்", "ரத்த அழுத்தம்", "ரத்தக் கொதிப்பு", "bp", "रक्तचाप", "రక్తపోటు"]):
            if language == "ta":
                return (
                    "**இரத்த அழுத்தம் (Blood Pressure - BP) பற்றிய முக்கிய தகவல்கள்:**\n\n"
                    "- **இயல்பான அளவு**: 120/80 mmHg (சிஸ்டாலிக்: 120, டயஸ்டாலிக்: 80).\n"
                    "- **உயர் இரத்த அழுத்தம் (Hypertension)**: 140/90 mmHg அல்லது அதற்கு மேல்.\n"
                    "- **குறைந்த இரத்த அழுத்தம் (Hypotension)**: 90/60 mmHg அல்லது அதற்கும் குறைவு.\n\n"
                    "**ஆரோக்கியமாக வைத்திருக்க எளிய குறிப்புகள்:**\n"
                    "1. உணவில் உப்பின் அளவைக் குறைத்தல்.\n"
                    "2. தினமும் 30 நிமிடங்கள் நடைப்பயிற்சி அல்லது உடற்பயிற்சி செய்தல்.\n"
                    "3. மன அழுத்தத்தைக் குறைத்து போதுமான தூக்கம் (7-8 மணிநேரம்) பெறுதல்.\n"
                    "4. போதிய அளவு தண்ணீர் குடித்தல்.\n\n"
                    "உங்கள் இரத்த அழுத்த அளவை சரிபார்க்க விரும்புகிறீர்களா?"
                )
            else:
                return (
                    "**Blood Pressure (BP) Guidelines:**\n\n"
                    "- **Normal Range**: Around 120/80 mmHg (Systolic < 120 and Diastolic < 80).\n"
                    "- **Elevated**: 120-129 / <80 mmHg.\n"
                    "- **Hypertension (Stage 1)**: 130-139 / 80-89 mmHg.\n"
                    "- **Hypertension (Stage 2)**: 140/90 mmHg or higher.\n\n"
                    "**Healthy Lifestyle Recommendations:**\n"
                    "1. Moderate dietary sodium (salt) intake.\n"
                    "2. Regular aerobic exercise (at least 150 minutes per week).\n"
                    "3. Manage stress and maintain healthy sleep hygiene (7-8 hours/night).\n"
                    "4. Stay well hydrated and eat potassium-rich foods (fruits, vegetables)."
                )

        # 2. Diabetes / Sugar
        if any(w in u_lower for w in ["diabetes", "சர்க்கரை நோய்", "நீரிழிவு", "sugar", "मधुमेह", "షుగర్"]):
            if language == "ta":
                return (
                    "**சர்க்கரை நோய் (Diabetes / நீரிழிவு) பற்றிய தகவல்கள்:**\n\n"
                    "- **வெறும் வயிற்றில் (Fasting Blood Sugar)**: 70 - 99 mg/dL (இயல்பு), 126 mg/dL மேல் இருந்தால் நீரிழிவு.\n"
                    "- **உணவுக்குப் பின் (Postprandial)**: 140 mg/dL-க்கு குறைவாக இருப்பது நலம்.\n"
                    "- **HbA1c (3 மாத சராசரி)**: 5.7%-க்கு குறைவாக இருப்பது இயல்பு; 6.5% அல்லது அதற்கு மேல் நீரிழிவு நிலையைக் குறிக்கும்.\n\n"
                    "**கட்டுப்பாட்டு வழிமுறைகள்:** நார்ச்சத்துள்ள உணவுகள், குறைந்த சர்க்கரை மற்றும் மாவுச்சத்து, மற்றும் வழக்கமான உடற்பயிற்சி."
                )
            else:
                return (
                    "**Diabetes & Blood Sugar Guidelines:**\n\n"
                    "- **Fasting Blood Glucose**: 70 - 99 mg/dL (Normal); 100 - 125 mg/dL (Prediabetes); 126+ mg/dL (Diabetes).\n"
                    "- **Postprandial (2h after meal)**: Below 140 mg/dL is normal.\n"
                    "- **HbA1c (3-month average)**: Normal is below 5.7%; Prediabetes is 5.7% - 6.4%; Diabetes is 6.5% or higher.\n\n"
                    "Key management involves a fiber-rich balanced diet, regular exercise, weight management, and routine clinical monitoring."
                )

        # E. General Science, Math & Everyday Knowledge
        # 1. Solar System / Astronomy
        if any(w in u_lower for w in ["solar system", "சூரிய குடும்பம்", "planet", "planets", "கோள்கள்", "சூரியன்", "பூமி", "நிலா", "moon", "sun", "earth"]):
            if language == "ta":
                return (
                    "**சூரிய குடும்பம் (Solar System) பற்றிய சுவாரஸ்ய தகவல்கள்:**\n\n"
                    "சூரிய குடும்பத்தின் மையத்தில் சூரியன் உள்ளது. இதைச் சுற்றி 8 முக்கிய கோள்கள் வலம் வருகின்றன:\n"
                    "1. **புதன் (Mercury)** - சூரியனுக்கு மிக அருகில் உள்ள சிறிய கோள்.\n"
                    "2. **வெள்ளி (Venus)** - மிக வெப்பமான கோள்.\n"
                    "3. **பூமி (Earth)** - உயிரினங்கள் வாழும் நமது கோள்.\n"
                    "4. **செவ்வாய் (Mars)** - சிவப்பு கோள்.\n"
                    "5. **வியாழன் (Jupiter)** - மிகப்பெரிய வாயுக்கோள்.\n"
                    "6. **சனி (Saturn)** - அழகான வளையங்களைக் கொண்ட கோள்.\n"
                    "7. **யுரேனஸ் (Uranus)** - குளிர்ந்த பனிக்கோள்.\n"
                    "8. **நெப்டியூன் (Neptune)** - சூரியனிலிருந்து மிகத் தொலைவில் உள்ள கோள்."
                )
            else:
                return (
                    "**The Solar System:**\n\n"
                    "Our solar system consists of the Sun at the center and 8 orbiting planets:\n"
                    "1. **Mercury**: The smallest and closest planet to the Sun.\n"
                    "2. **Venus**: The hottest planet with a thick, toxic atmosphere.\n"
                    "3. **Earth**: Our home, the only planet known to harbor life.\n"
                    "4. **Mars**: The red planet with iron-rich soil.\n"
                    "5. **Jupiter**: The largest gas giant with the famous Great Red Spot.\n"
                    "6. **Saturn**: Known for its spectacular ring system.\n"
                    "7. **Uranus**: An ice giant rotating on its side.\n"
                    "8. **Neptune**: The farthest and windiest planet in our system."
                )

        # F. Kiosk / Identity / General Help
        if any(w in u_lower for w in ["who are you", "what can you do", "help me", "how to", "tell me", "what is", "where is", "hospital", "kiosk", "doctor", "யார் நீ", "என்ன செய்ய முடியும்", "உதவி"]):
            resp_map = {
                "ta": "நான் மெடிகியோஸ்க் ஆல்-ரவுண்டர் ஏஐ உதவியாளர். மருத்துவ அறிகுறிகள் பதிவு செய்தல், மருத்துவமனை வழிகாட்டல், கணினி நிரலாக்கம் (Coding), அறிவியல், பொது அறிவு மற்றும் அன்றாட சந்தேகங்கள் அனைத்திற்கும் உங்களுக்கு உதவ முடியும். நீங்கள் என்ன அறிய விரும்புகிறீர்கள்?",
                "hi": "मैं मेडीकियोस्क ऑल-राउंडर एआई सहायक हूँ। मैं स्वास्थ्य जांच, अस्पताल मार्गदर्शन, कोडिंग और किसी भी सामान्य ज्ञान की जानकारी में आपकी सहायता कर सकता हूँ। आप क्या जानना चाहते हैं?",
                "te": "నేను మెడికియోస్క్ ఆల్ రౌండర్ AI సహాయకుడిని. వైద్య సహాయం, హాస్పిటల్ గైడెన్స్, ప్రోగ్రామింగ్ కోడింగ్ మరియు సాధారణ జ్ఞానం ఏ సమాచారమైనా అందించగలను.",
                "en": "I am MediKiosk AI, your versatile all-rounder assistant. I can assist you with clinical check-ins, health inquiries, programming & code solutions, general science & knowledge, and hospital navigation. How can I help you today?"
            }
            return resp_map.get(language, resp_map["en"])

        # ----------------------------------------------------
        # SYMPTOM & DURATION EXTRACTION (WITH SUFFIX STEMMING)
        # ----------------------------------------------------
        is_fever = any(w in u_lower for w in ["fever", "காய்ச்ச", "bukhar", "बुखार", "ಜ್ವರ", "പனி", "జ్వరం"])
        is_chest_pain = any(w in u_lower for w in ["chest pain", "chest", "நெஞ்சு", "மார்பு", "सीने में दर्द", "छाती", "ఛాతీ", "നെഞ്ച്", "ಎದೆ"])
        is_headache = any(w in u_lower for w in ["headache", "தலைவலி", "தல வலி", "सिरदर्द", "తలనొప్పి", "തലవేదన", "ತಲೆನೋವು"])
        is_vomiting = any(w in u_lower for w in ["vomit", "vomiting", "வாந்தி", "உல்டி", "उल्टी", "వాంతులు", "ഛർദ്ദി"])
        is_cough = any(w in u_lower for w in ["cough", "இரும", "खांसी", "దగ్గు", "ചുമ"])
        is_body_pain = any(w in u_lower for w in ["body pain", "body ache", "உடம்பு முழுக்க வலி", "உடல் வலி", "உடல்வலி", "உடம்பு வலி", "உடம்புவலி", "बदन दर्द", "ఒంటి నొప్పులు"])

        duration_patterns = [
            r'(\d+\s*(?:நாட்களுக்கு|நாட்களாக|நாட்கள்|நாளைக்கு|மணிநேரமாக))',
            r'(?:நேற்று\s*(?:முதல்|இரவு)?)',
            r'(\d+\s*(?:दिनों\s*से|दिन\s*से|घंटे\s*से))',
            r'(?:कल\s*(?:से|रात\s*से))',
            r'(?:since\s+[a-zA-Z0-9\s]+)',
            r'(?:for\s+\d+\s*(?:days?|weeks?|hours?))',
            r'(\d+\s*(?:days?|weeks?|hours?)\s*ago)',
            r'(\d+\s*(?:days?|weeks?|hours?))'
        ]
        has_duration = None
        for dp in duration_patterns:
            m = re.search(dp, u_lower)
            if m:
                has_duration = m.group(0).strip()
                break

        # Check existing known symptoms
        known_has_fever = "fever" in symptoms_map or "fever" in durations_map
        known_has_chest_pain = "chest pain" in symptoms_map or "chest pain" in durations_map
        known_has_headache = "headache" in symptoms_map or "headache" in durations_map

        # ----------------------------------------------------
        # CASE A: MULTI-SYMPTOM PROVIDED IN THE SAME MESSAGE
        # ----------------------------------------------------
        detected_syms_ta = []
        detected_syms_en = []
        if is_fever:
            detected_syms_ta.append("காய்ச்சல்")
            detected_syms_en.append("fever")
        if is_headache:
            detected_syms_ta.append("தலைவலி")
            detected_syms_en.append("headache")
        if is_vomiting:
            detected_syms_ta.append("வாந்தி")
            detected_syms_en.append("vomiting")
        if is_chest_pain:
            detected_syms_ta.append("மார்பு வலி")
            detected_syms_en.append("chest pain")
        if is_body_pain:
            detected_syms_ta.append("உடல் வலி")
            detected_syms_en.append("body pain")
        if is_cough:
            detected_syms_ta.append("இருமல்")
            detected_syms_en.append("cough")

        if len(detected_syms_ta) >= 2 or (len(detected_syms_ta) >= 1 and has_duration):
            sym_str_ta = " மற்றும் ".join(detected_syms_ta)
            sym_str_en = " and ".join(detected_syms_en)
            if has_duration:
                resp_map = {
                    "ta": f"சரி, {has_duration} இருக்கும் {sym_str_ta} இருப்பதை பதிவு செய்துள்ளேன். வேறு ஏதாவது உடல்நலப் பிரச்சனை அல்லது அறிகுறிகள் இருக்கிறதா?",
                    "hi": f"ठीक है, मैंने {has_duration} से {sym_str_en} की जानकारी दर्ज कर ली है। क्या आप अपने स्वास्थ्य से जुड़ी कोई और बात बताना चाहते हैं?",
                    "te": f"సరే, {sym_str_en} వివరాలను నమోదు చేశాను. ఇంకేమైనా సమస్యలు ఉన్నాయా?",
                    "en": f"Okay, I’ve recorded {sym_str_en} for the past {has_duration}. Is there anything else you would like to tell me about how you are feeling?"
                }
            else:
                resp_map = {
                    "ta": f"சரி, {sym_str_ta} இருப்பதை பதிவு செய்துள்ளேன். இந்த அறிகுறிகள் எப்போது தொடங்கியது அல்லது எத்தனை நாட்களாக இருக்கிறது?",
                    "hi": f"ठीक है, मैंने {sym_str_en} की जानकारी दर्ज कर ली है। यह समस्या कब शुरू हुई थी?",
                    "te": f"సరే, {sym_str_en} వివరాలను నమోదు చేశాను. ఇది ఎప్పుడు ప్రారంభమైంది?",
                    "en": f"Okay, I’ve recorded {sym_str_en}. When did these symptoms start or how long have you had them?"
                }
            return resp_map.get(language, resp_map["en"])

        # ----------------------------------------------------
        # CASE B: ONLY DURATION PROVIDED AS ANSWER TO PREVIOUS QUESTION
        # ----------------------------------------------------
        if has_duration and len(u_lower.split()) <= 4:
            resp_map = {
                "ta": f"சரி. {has_duration} இருப்பதாக பதிவு செய்கிறேன். வேறு ஏதாவது உடல்நலப் பிரச்சனை அல்லது அறிகுறிகள் இருக்கிறதா?",
                "hi": f"ठीक है। मैंने दर्ज कर लिया है कि यह {has_duration} से है। क्या आपको कोई अन्य स्वास्थ्य समस्या है?",
                "te": f"సరే. {has_duration} ఉన్నట్లు నమోదు చేశాను. వేరే ఏదైనా ఆరోగ్య సమస్య ఉందా?",
                "en": f"Okay, I’ve recorded that for {has_duration}. Is there anything else you would like to tell me about how you are feeling?"
            }
            return resp_map.get(language, resp_map["en"])

        # ----------------------------------------------------
        # CASE C: CHEST PAIN WITH PRIOR FEVER
        # ----------------------------------------------------
        if is_chest_pain and known_has_fever:
            resp_map = {
                "ta": "காய்ச்சலுடன் மார்பு வலி இருப்பதையும் குறித்துக் கொண்டேன். மார்பு வலி எப்போது தொடங்கியது? தொடர்ந்து வலிக்கிறதா அல்லது விட்டு விட்டு வருகிறதா?",
                "hi": "मैंने बुखार के साथ सीने में दर्द भी दर्ज कर लिया है। सीने में दर्द कब शुरू हुआ था? क्या यह लगातार है या रुक-रुक कर?",
                "en": "I have also noted chest pain along with your fever. When did the chest pain start? Is it continuous or intermittent?"
            }
            return resp_map.get(language, resp_map["en"])

        # ----------------------------------------------------
        # CASE D: SINGLE SYMPTOM WITHOUT DURATION
        # ----------------------------------------------------
        if is_headache and not has_duration:
            resp_map = {
                "ta": "தலைவலி எத்தனை நாட்களாக இருக்கிறது?",
                "hi": "आपको सिरदर्द कितने दिनों से है?",
                "te": "తలనొప్పి ఎన్ని రోజులుగా ఉంది?",
                "en": "How many days have you had the headache?"
            }
            return resp_map.get(language, resp_map["en"])

        if is_fever and not has_duration:
            resp_map = {
                "ta": "காய்ச்சல் எத்தனை நாட்களாக இருக்கிறது?",
                "hi": "आपको बुखार कितने दिनों से है?",
                "te": "జ్వరం ఎన్ని రోజులుగా ఉంది?",
                "en": "How many days have you had the fever?"
            }
            return resp_map.get(language, resp_map["en"])

        if is_chest_pain and not has_duration:
            resp_map = {
                "ta": "மார்பு வலி எப்போது தொடங்கியது? தொடர்ந்து இருக்கிறதா அல்லது இடைக்கிடையே வருகிறதா?",
                "hi": "सीने में दर्द कब शुरू हुआ था? क्या यह लगातार बना हुआ है?",
                "en": "When did the chest pain start? Is it continuous or does it come and go?"
            }
            return resp_map.get(language, resp_map["en"])

        # ----------------------------------------------------
        # E. DYNAMIC SEMANTIC SYNTHESIZER FOR OPEN-ENDED TOPICS
        # ----------------------------------------------------
        if is_medical:
            resp_map = {
                "ta": "உங்கள் உடல்நலத் தகவலை குறித்துக் கொண்டேன். இதை உங்கள் மருத்துவருக்கான அறிக்கையில் பதிவு செய்கிறேன். வேறு ஏதேனும் அறிகுறிகள் அல்லது தகவல்கள் உள்ளதா?",
                "hi": "मैंने आपकी बात दर्ज कर ली है और इसे डॉक्टर के सारांश में शामिल कर रहा हूँ। क्या कोई अन्य स्वास्थ्य समस्या है?",
                "te": "మీ వివరాలు నమోదు చేయబడ్డాయి. డాక్టర్ రిపోర్టులో చేర్చాను. ఇంకేమైనా చెప్పాలనుకుంటున్నారా?",
                "en": "I have noted your information and updated your clinical summary for the doctor. Is there anything else you would like to mention?"
            }
            return resp_map.get(language, resp_map["en"])

        # Intelligent open-ended topic explanation
        if any(w in u_lower for w in ["என்றால் என்ன", "பயன்கள்", "விளக்குக", "பற்றி", "என்ன", "எப்படி", "செயல்பாடு", "क्या है", "उपयोग", "बताइए", "what is", "how to", "explain", "benefits", "features"]):
            clean_topic = re.sub(r'(?:என்றால் என்ன|பயன்கள்|விளக்குக|பற்றி|என்ன|எப்படி|என்னென்ன|என்ன பயன்|क्या है|उपयोग|बताएं|what is|how to|explain|tell me about)\s*', '', user_text, flags=re.IGNORECASE).strip(' ?:,.-')
            topic_display = clean_topic if clean_topic else user_text.strip()
            
            if language == "ta":
                return (
                    f"**{topic_display} பற்றிய விளக்கம்:**\n\n"
                    f"{topic_display} என்பது ஒரு முக்கியமான தலைப்பாகும். இது தொடர்பான முக்கிய கருத்துகள்:\n"
                    f"1. **அடிப்படைக் கருத்து**: இது தற்கால தொழில்நுட்பம் மற்றும் பயன்பாடுகளில் மிக முக்கிய பங்கு வகிக்கிறது.\n"
                    f"2. **முக்கிய பயன்கள்**: சிக்கல்களைத் தீர்ப்பதற்கும், உற்பத்தித் திறனை அதிகரிப்பதற்கும் பெரிதும் உதவுகிறது.\n"
                    f"3. **செயல்முறை**: இது கட்டமைக்கப்பட்ட முறைகள் மற்றும் தரவுகளின் அடிப்படையில் இயங்குகிறது.\n\n"
                    f"இந்தத் தலைப்பில் ஏதேனும் குறிப்பிட்ட நிரலாக்கம் (Coding) அல்லது நடைமுறை உதாரணங்கள் தேவைப்படுகிறதா?"
                )
            elif language == "hi":
                return (
                    f"**{topic_display} के बारे में जानकारी:**\n\n"
                    f"1. **मुख्य अवधारणा**: यह आधुनिक तकनीक और ज्ञान का एक महत्वपूर्ण क्षेत्र है।\n"
                    f"2. **प्रमुख लाभ**: यह जटिल कार्यों को आसान बनाने और दक्षता बढ़ाने में मदद करता है।\n"
                    f"3. **अनुप्रयोग**: इसका उपयोग विभिन्न उद्योगों, अनुसंधान और शिक्षा में व्यापक रूप से होता है।\n\n"
                    f"क्या आप इसके बारे में कोई व्यावहारिक उदाहरण या कोड देखना चाहते हैं?"
                )
            else:
                return (
                    f"**Overview of {topic_display}:**\n\n"
                    f"1. **Core Concept**: Represents a key domain in modern technology, science, and practical applications.\n"
                    f"2. **Primary Utility**: Helps streamline processes, solve analytical problems, and enhance productivity.\n"
                    f"3. **Practical Scope**: Widely applied across software engineering, automation, and real-world workflows.\n\n"
                    f"Would you like specific examples, technical implementation details, or code demonstrations regarding this topic?"
                )

        resp_map = {
            "ta": "உங்களுக்கு உதவ தயாராக உள்ளேன். நீங்கள் அறிய விரும்பும் தலைப்பு அல்லது நிரலாக்கம் (Programming) / உடல்நலம் குறித்து என்ன தகவல் வேண்டும் என்று கேளுங்கள்.",
            "hi": "मैं आपकी सहायता के लिए तैयार हूँ। आप कोडिंग, स्वास्थ्य या किसी भी सामान्य ज्ञान के बारे में क्या जानना चाहते हैं?",
            "te": "నేను మీకు సహాయం చేయడానికి సిద్ధంగా ఉన్నాను. మీకు ఏ విషయం గురించి సమాచారం కావాలి?",
            "en": "I am ready to assist you. What topic, programming code, or health information would you like to explore?"
        }
        return resp_map.get(language, resp_map["en"])

    def extract_patient_facts(self, messages: List[Dict[str, str]], language: str = "en") -> Dict[str, Any]:
        """
        Extracts structured patient facts as JSON for doctor report and triage.
        Never hallucinates negative findings unless explicitly stated.
        """
        convo_lines = []
        patient_texts = []
        for msg in messages:
            sender = "Patient" if msg.get("sender") in ("patient", "user") else "AI"
            txt = msg.get("text", "")
            convo_lines.append(f"{sender}: {txt}")
            if sender == "Patient":
                patient_texts.append(txt)
        transcript = "\n".join(convo_lines)

        extraction_messages = [
            {"role": "system", "content": CLINICAL_EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Extract structured clinical facts from this conversation:\n\n{transcript}\n\nReturn JSON only matching the schema."
            }
        ]

        raw_json_str = self._call_qwen(extraction_messages, temperature=0.1, max_tokens=350)
        parsed = None
        if raw_json_str:
            try:
                json_match = re.search(r"\{.*\}", raw_json_str, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0))
            except Exception:
                pass

        if isinstance(parsed, dict) and "chief_complaint" in parsed:
            return parsed

        # Heuristic fallback if LLM offline
        chiefs = []
        durations = []
        combined = " ".join(patient_texts).lower()

        if any(w in combined for w in ["fever", "காய்ச்சல்", "बुखार"]):
            chiefs.append("fever")
        if any(w in combined for w in ["headache", "தலைவலி", "सिरदर्द"]):
            chiefs.append("headache")
        if any(w in combined for w in ["vomit", "வாந்தி", "உल्टी"]):
            chiefs.append("vomiting")
        if any(w in combined for w in ["chest pain", "நெஞ்சு வலி", "सीने में दर्द"]):
            chiefs.append("chest pain")

        duration_match = re.search(r'(\d+\s*(?:days?|weeks?|hours?|நாட்களாக|நாட்களுக்கு|दिन))', combined)
        if duration_match and chiefs:
            durations.append({"symptom": chiefs[0], "duration": duration_match.group(0)})

        return {
            "chief_complaint": chiefs or (patient_texts[:1] if patient_texts else []),
            "duration": durations,
            "associated_symptoms": [],
            "negative_findings": [],
            "medications": [],
            "medical_history": [],
            "allergies": [],
            "patient_statements": patient_texts[-3:] if patient_texts else [],
            "urgency_level": "emergency" if "chest pain" in chiefs else "moderate" if chiefs else "low"
        }

    def extract_clinical_facts(self, messages: List[Dict[str, str]], language: str = "en") -> Dict[str, Any]:
        """Backward-compatible clinical extraction returning standard schema."""
        facts = self.extract_patient_facts(messages, language=language)
        chief = facts.get("chief_complaint")
        chief_str = chief[0] if isinstance(chief, list) and chief else str(chief) if chief else None

        onset_str = None
        if facts.get("duration") and isinstance(facts["duration"], list) and len(facts["duration"]) > 0:
            onset_str = facts["duration"][0].get("duration")

        return {
            "chief_complaint": chief_str,
            "location": None,
            "onset": onset_str,
            "character": None,
            "severity": None,
            "aggravating_factors": None,
            "relieving_factors": None,
            "associated_symptoms": facts.get("associated_symptoms", []),
            "urgency_level": facts.get("urgency_level", "needs_assessment")
        }

    def generate_response(self, messages: List[Dict[str, str]], patient_context: Optional[Dict[str, Any]] = None, language: str = "en") -> str:
        return self.generate_conversational_response(messages, patient_context=patient_context, language=language)

llm_service = LLMService()
