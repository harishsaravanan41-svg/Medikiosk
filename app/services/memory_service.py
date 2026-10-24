# -*- coding: utf-8 -*-
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import Config

class MemoryService:
    """
    Persistent Per-Patient Isolated Memory Service.
    Strict isolation: Patient P-1001 memory is NEVER accessible to Patient P-1002.
    
    Structure per patient:
    Patient P-1001
     ├── conversations (chronological turns)
     ├── symptoms (symptom catalog with status & onset)
     ├── duration (symptom duration details)
     ├── previous_answers (questions asked & patient answers)
     ├── uploaded_records (extracted reports & summaries)
     ├── ai_responses (history of AI answers)
     └── doctor_report (generated clinical summary)
    """

    def __init__(self):
        self.data_dir = Path(Config.DATA_DIR)
        self.memory_file = self.data_dir / "user_memory.json"
        self._lock = threading.Lock()
        self._init_storage()

    def _init_storage(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.memory_file.exists():
            self._write_json({})

    def _read_json(self) -> Dict[str, Any]:
        if not self.memory_file.exists():
            return {}
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[MemoryService] Error reading memory file: {e}")
            return {}

    def _write_json(self, data: Dict[str, Any]):
        temp_file = self.memory_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_file.replace(self.memory_file)
        except Exception as e:
            print(f"[MemoryService] Error writing memory file: {e}")
            if temp_file.exists():
                temp_file.unlink()

    def _get_or_create_patient_memory(self, patient_id: str, store: Dict[str, Any]) -> Dict[str, Any]:
        if not patient_id:
            patient_id = "P-1001"

        if patient_id not in store:
            store[patient_id] = {
                "patient_id": patient_id,
                "profile": {
                    "patient_id": patient_id,
                    "created_at": datetime.now().isoformat()
                },
                "preferences": {
                    "language": "en"
                },
                "languages": ["en"],
                "preferred_language": "en",
                "recent_language": "en",
                # Dedicated per-patient memory architecture
                "conversations": [],
                "symptoms": {},        # e.g. {"fever": {"status": "yes", "duration": "3 days", "severity": "unknown"}}
                "duration": {},        # e.g. {"fever": "3 days", "chest pain": "since yesterday"}
                "previous_answers": {},# e.g. {"fever_duration": "3 days", "chest_pain_onset": "yesterday"}
                "uploaded_records": [],# e.g. ["Blood test: HbA1c 7.1%", "ECG normal"]
                "ai_responses": [],    # list of recent AI messages
                "doctor_report": None, # formatted chronological clinical summary
                # Backward-compatibility lists
                "conversation_memory": [],
                "medical_memory": [],
                "important_facts": []
            }
        else:
            # Ensure all architecture keys exist
            mem = store[patient_id]
            mem.setdefault("conversations", [])
            mem.setdefault("symptoms", {})
            mem.setdefault("duration", {})
            mem.setdefault("previous_answers", {})
            mem.setdefault("uploaded_records", [])
            mem.setdefault("ai_responses", [])
            mem.setdefault("doctor_report", None)
            mem.setdefault("medical_memory", [])
            mem.setdefault("important_facts", [])
            mem.setdefault("conversation_memory", [])
            mem.setdefault("languages", ["en"])

        return store[patient_id]

    def record_patient_language(self, patient_id: str, language_code: str):
        """Records language for this patient without touching any other patient's data."""
        if not patient_id or not language_code:
            return
        with self._lock:
            store = self._read_json()
            user_mem = self._get_or_create_patient_memory(patient_id, store)
            langs = user_mem.setdefault("languages", [])
            clean_lang = language_code.strip().lower()
            if clean_lang and clean_lang not in langs:
                langs.append(clean_lang)
            user_mem["recent_language"] = clean_lang
            if not user_mem.get("preferred_language") or user_mem["preferred_language"] == "en":
                user_mem["preferred_language"] = clean_lang
            self._write_json(store)

    def get_user_memory(self, patient_id: str) -> Dict[str, Any]:
        """Strictly retrieves memory for ONLY the specified patient_id."""
        if not patient_id:
            patient_id = "P-1001"
        with self._lock:
            store = self._read_json()
            return self._get_or_create_patient_memory(patient_id, store)

    def save_user_memory(self, patient_id: str, memory: Dict[str, Any]):
        """Strictly saves memory under patient_id."""
        if not patient_id:
            return
        with self._lock:
            store = self._read_json()
            store[patient_id] = memory
            self._write_json(store)

    def record_turn(self, patient_id: str, session_id: str, user_text: str, ai_text: str):
        """Records a user-AI conversation turn into patient memory."""
        if not patient_id:
            patient_id = "P-1001"
        with self._lock:
            store = self._read_json()
            user_mem = self._get_or_create_patient_memory(patient_id, store)
            turn_data = {
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "user_text": user_text,
                "ai_text": ai_text
            }
            user_mem.setdefault("conversations", []).append(turn_data)
            user_mem["conversations"] = user_mem["conversations"][-25:]
            user_mem.setdefault("ai_responses", []).append(ai_text)
            user_mem["ai_responses"] = user_mem["ai_responses"][-15:]
            self._write_json(store)

    def add_medical_fact(self, patient_id: str, fact: str, duration: Optional[str] = None, source: str = "user"):
        """Adds or updates a symptom and duration in the patient's isolated memory."""
        if not patient_id or not fact:
            return
        with self._lock:
            store = self._read_json()
            user_mem = self._get_or_create_patient_memory(patient_id, store)
            
            clean_fact = fact.strip().lower()
            symptoms_map = user_mem.setdefault("symptoms", {})
            durations_map = user_mem.setdefault("duration", {})

            # Update structured symptoms dict
            if clean_fact not in symptoms_map:
                symptoms_map[clean_fact] = {
                    "status": "yes",
                    "duration": duration or "unknown",
                    "source": source,
                    "first_reported": datetime.now().isoformat()
                }
            else:
                if duration and symptoms_map[clean_fact].get("duration") in (None, "unknown"):
                    symptoms_map[clean_fact]["duration"] = duration

            if duration:
                durations_map[clean_fact] = duration

            # Also maintain backward-compatible medical_memory list
            med_mem = user_mem.setdefault("medical_memory", [])
            existing = False
            for item in med_mem:
                if item.get("fact", "").strip().lower() == clean_fact:
                    if duration and not item.get("duration"):
                        item["duration"] = duration
                    existing = True
                    break
            if not existing:
                rec = {
                    "fact": fact.strip(),
                    "source": source,
                    "timestamp": datetime.now().isoformat()
                }
                if duration:
                    rec["duration"] = duration.strip()
                med_mem.append(rec)

            self._write_json(store)

    def add_important_fact(self, patient_id: str, fact: str):
        """Adds identity or allergy facts to isolated patient memory."""
        if not patient_id or not fact:
            return
        with self._lock:
            store = self._read_json()
            user_mem = self._get_or_create_patient_memory(patient_id, store)
            facts = user_mem.setdefault("important_facts", [])
            clean_fact = fact.strip()
            if clean_fact and clean_fact not in facts:
                facts.append(clean_fact)
            self._write_json(store)

    def get_known_patient_facts_formatted(self, patient_id: str) -> str:
        """
        Formats known patient facts as clean bullet points for LLM context injection:
        - Fever: yes
        - Fever duration: 3 days
        - Chest pain: yes
        - Chest pain duration: unknown
        """
        user_mem = self.get_user_memory(patient_id)
        symptoms_map = user_mem.get("symptoms", {})
        durations_map = user_mem.get("duration", {})
        important_facts = user_mem.get("important_facts", [])

        # If symptoms_map is empty, check legacy medical_memory
        if not symptoms_map and user_mem.get("medical_memory"):
            for item in user_mem["medical_memory"]:
                sym = item.get("fact", "").strip().lower()
                dur = item.get("duration", "unknown")
                if sym:
                    symptoms_map[sym] = {"status": "yes", "duration": dur}
                    if dur != "unknown":
                        durations_map[sym] = dur

        lines = []
        for sym_name, sym_info in symptoms_map.items():
            sym_title = sym_name.capitalize()
            lines.append(f"- {sym_title}: yes")
            dur = durations_map.get(sym_name) or sym_info.get("duration") or "unknown"
            lines.append(f"- {sym_title} duration: {dur}")

        for fact in important_facts:
            lines.append(f"- {fact}")

        if not lines:
            return "- No prior symptoms recorded"

        return "\n".join(lines)

    def add_conversation_summary(self, patient_id: str, session_id: str, summary: str):
        """Saves a summary of a completed conversation session for cross-session recall."""
        if not patient_id or not summary:
            return
        with self._lock:
            store = self._read_json()
            user_mem = self._get_or_create_patient_memory(patient_id, store)
            convo_mem = user_mem.setdefault("conversation_memory", [])
            convo_mem.append({
                "session_id": session_id,
                "summary": summary,
                "timestamp": datetime.now().isoformat()
            })
            user_mem["conversation_memory"] = convo_mem[-10:]
            self._write_json(store)

    def get_relevant_memory(self, patient_id: str, query: str = "") -> Optional[str]:
        """
        Retrieves relevant persistent memory for the specified patient_id.
        User A NEVER receives User B's memory.
        """
        if not patient_id:
            patient_id = "P-1001"
        user_mem = self.get_user_memory(patient_id)

        medical_memory = user_mem.get("medical_memory", [])
        symptoms_map = user_mem.get("symptoms", {})
        durations_map = user_mem.get("duration", {})
        important_facts = user_mem.get("important_facts", [])
        conversation_memory = user_mem.get("conversation_memory", [])

        if not medical_memory and not symptoms_map and not important_facts and not conversation_memory:
            return None

        lines = [f"RELEVANT USER MEMORY (Patient ID: {patient_id}):"]

        # Medical symptoms
        if symptoms_map or medical_memory:
            lines.append("• Reported Medical Symptoms & Observations:")
            if medical_memory:
                for item in medical_memory[-8:]:
                    fact_str = item.get("fact", "")
                    dur = item.get("duration")
                    if dur:
                        fact_str += f" (duration: {dur})"
                    lines.append(f"  - {fact_str}")
            else:
                for sym, info in symptoms_map.items():
                    dur = durations_map.get(sym) or info.get("duration")
                    dur_str = f" (duration: {dur})" if dur and dur != "unknown" else ""
                    lines.append(f"  - {sym}{dur_str}")

        if important_facts:
            lines.append("• User Facts:")
            for fact in important_facts[-5:]:
                lines.append(f"  - {fact}")

        if conversation_memory:
            lines.append("• Previous Conversations Summary:")
            for entry in conversation_memory[-3:]:
                lines.append(f"  - {entry.get('summary', '')}")

        return "\n".join(lines)

    def generate_doctor_report(self, patient_id: str, session_id: Optional[str] = None) -> str:
        """
        Generates a chronological doctor report strictly derived from:
        all saved patient facts + conversation history + uploaded records.
        """
        user_mem = self.get_user_memory(patient_id)
        symptoms_map = user_mem.get("symptoms", {})
        durations_map = user_mem.get("duration", {})
        conversations = user_mem.get("conversations", [])
        uploaded_records = user_mem.get("uploaded_records", [])

        # Fallback to legacy medical_memory if symptoms dict is empty
        if not symptoms_map and user_mem.get("medical_memory"):
            for item in user_mem["medical_memory"]:
                sym = item.get("fact", "").strip().lower()
                dur = item.get("duration", "unknown")
                if sym:
                    symptoms_map[sym] = {"status": "yes", "duration": dur}
                    if dur != "unknown":
                        durations_map[sym] = dur

        # 1. Chief Complaints
        chief_complaints = []
        for sym in symptoms_map.keys():
            chief_complaints.append(f"- {sym.capitalize()}")
        if not chief_complaints:
            chief_complaints.append("- General medical check-in / review")

        # 2. History with durations
        history_lines = []
        for sym, info in symptoms_map.items():
            dur = durations_map.get(sym) or info.get("duration")
            if dur and dur != "unknown":
                history_lines.append(f"- {sym.capitalize()} for {dur}")
            else:
                history_lines.append(f"- {sym.capitalize()} (duration not yet specified)")
        if not history_lines:
            history_lines.append("- No specific symptom timeline recorded")

        # 3. Conversation-derived information
        derived_lines = []
        if conversations:
            for turn in conversations:
                ut = turn.get("user_text", "")
                if ut:
                    derived_lines.append(f"- Patient stated: \"{ut}\"")
        else:
            for sym, info in symptoms_map.items():
                dur = durations_map.get(sym)
                if dur and dur != "unknown":
                    derived_lines.append(f"- Patient reported {sym} lasting {dur}.")
                else:
                    derived_lines.append(f"- Patient reported {sym}.")
        if not derived_lines:
            derived_lines.append("- Patient engaged in initial consultation intake.")

        # 4. Important missing information
        missing_lines = []
        for sym in symptoms_map.keys():
            if "fever" in sym:
                missing_lines.append("- Fever exact temperature not provided")
            elif "chest" in sym or "pain" in sym:
                missing_lines.append(f"- {sym.capitalize()} severity scale (1-10) not yet recorded")
        missing_lines.append("- Associated symptoms not yet established")

        # 5. Source
        source_str = "Patient conversation"
        if uploaded_records:
            source_str += f" + {len(uploaded_records)} uploaded records"

        today_str = datetime.now().strftime("%d %b %Y")

        report = f"""PATIENT CLINICAL SUMMARY

Patient: {patient_id}

Chief complaints:
{chr(10).join(chief_complaints)}

History:
{chr(10).join(history_lines)}

Conversation-derived information:
{chr(10).join(derived_lines[-6:])}

Important missing information:
{chr(10).join(missing_lines[:4])}

Source:
{source_str}

Generated:
{today_str}"""

        # Save to memory record
        with self._lock:
            store = self._read_json()
            um = self._get_or_create_patient_memory(patient_id, store)
            um["doctor_report"] = report
            self._write_json(store)

        return report

    def extract_and_update_memory_async(
        self,
        patient_id: str,
        session_id: str,
        user_text: str,
        ai_text: str
    ):
        """Asynchronously extracts symptoms, durations, and facts without blocking token stream."""
        t = threading.Thread(
            target=self._extract_and_update_memory_worker,
            args=(patient_id, session_id, user_text, ai_text),
            daemon=True
        )
        t.start()

    def _extract_and_update_memory_worker(
        self,
        patient_id: str,
        session_id: str,
        user_text: str,
        ai_text: str
    ):
        try:
            if not user_text or not patient_id:
                return

            # Record turn
            self.record_turn(patient_id, session_id, user_text, ai_text)

            text_lower = user_text.lower().strip()

            # Duration pattern matching across languages
            duration_patterns = [
                r'(\d+\s*(?:நாட்களாக|நாட்கள்|நாளைக்கு|மணிநேரமாக))',
                r'(?:நேற்று\s*(?:முதல்|இரவு))',
                r'(\d+\s*(?:दिनों\s*से|दिन\s*से|घंटे\s*से))',
                r'(?:कल\s*(?:से|रात\s*से))',
                r'(?:since\s+([a-zA-Z0-9\s]+))',
                r'(?:for\s+(\d+\s*(?:days?|weeks?|months?|hours?)))',
                r'(?:from\s+last\s+([a-zA-Z0-9\s]+))',
                r'(\d+\s*(?:days?|weeks?|months?|hours?)\s*ago)',
                r'(\d+\s*(?:days?|weeks?|months?|hours?))'
            ]
            detected_duration = None
            for dp in duration_patterns:
                match = re.search(dp, text_lower)
                if match:
                    detected_duration = match.group(0).strip()
                    break

            symptom_keywords = {
                "fever": ["fever", "காய்ச்சல்", "बुखार", "ಜ್ವರ", "പനി", "జ్వరం"],
                "chest pain": ["chest pain", "நெஞ்சு வலி", "மார்பு வலி", "सीने में दर्द", "छाती में दर्द", "ఛాతీ నొప్పి", "നെഞ്ചുവേദന", "ಎದೆ ನೋವು"],
                "headache": ["headache", "தலைவலி", "सिरदर्द", "తలనొప్పి", "തലവേദന", "ತಲೆನೋವು"],
                "cough": ["cough", "இருமல்", "खांसी", "దగ్గు", "ചുമ", "ಕೆಮ್ಮು"],
                "vomiting": ["vomiting", "வாந்தி", "उल्टी", "వాంతులు", "ഛർദ്ദി"],
                "breathlessness": ["shortness of breath", "மூச்சுத்திணறல்", "सांस लेने में तकलीफ", "శ్వాస ఆడకపోవడం", "ശ്വാസതടസ്സം"],
                "body pain": ["body pain", "உடல் வலி", "बदन दर्द", "ఒంటి నொప్పులు", "ശരീരവേദന"],
                "stomach pain": ["stomach pain", "வயிற்று வலி", "पेट दर्द", "కడుపు నొప్పి", "വയറുവേദന"]
            }

            found_any_symptom = False
            for sym_canonical, kws in symptom_keywords.items():
                if any(kw in text_lower for kw in kws):
                    found_any_symptom = True
                    self.add_medical_fact(
                        patient_id=patient_id,
                        fact=sym_canonical,
                        duration=detected_duration,
                        source="user"
                    )

            # If user provided a duration in a follow-up turn without repeating symptom name
            if detected_duration and not found_any_symptom:
                user_mem = self.get_user_memory(patient_id)
                symptoms_map = user_mem.get("symptoms", {})
                for sym_name, sym_data in reversed(list(symptoms_map.items())):
                    if sym_data.get("duration") in (None, "unknown"):
                        self.add_medical_fact(
                            patient_id=patient_id,
                            fact=sym_name,
                            duration=detected_duration,
                            source="user"
                        )
                        break

            # Extract identity facts
            name_match = re.search(r'(?:my name is|i am|i\'m)\s+([a-zA-Z]+)', user_text, re.IGNORECASE)
            if name_match:
                candidate = name_match.group(1).strip()
                if candidate.lower() not in ["having", "feeling", "suffering", "sick", "in", "a", "an", "the", "not", "also", "here", "fine", "good"]:
                    self.add_important_fact(patient_id, f"Name: {candidate}")

            allergy_match = re.search(r'(?:allergic to|allergy to)\s+([a-zA-Z\s]+)', user_text, re.IGNORECASE)
            if allergy_match:
                self.add_important_fact(patient_id, f"Allergy: {allergy_match.group(1).strip()}")

            # Refresh doctor report for this patient
            report = self.generate_doctor_report(patient_id, session_id=session_id)

            # Sync to DB active encounter so doctor workstation sees it immediately
            try:
                from app.services.db_service import db_service
                enc = db_service.create_or_get_active_encounter(patient_id, session_id=session_id)
                if enc and enc.get("encounter_id"):
                    chief_complaint_str = ", ".join([s.capitalize() for s in self.get_user_memory(patient_id).get("symptoms", {}).keys()]) or "General Consultation"
                    db_service.update_ai_history(enc["encounter_id"], {
                        "chief_complaint": chief_complaint_str,
                        "hpi_json": json.dumps(self.get_user_memory(patient_id).get("symptoms", {})),
                        "notes": report
                    })
            except Exception as db_sync_err:
                print(f"[MemoryService] DB sync note: {db_sync_err}")

        except Exception as e:
            print(f"[MemoryService Worker Error] {e}")

memory_service = MemoryService()
