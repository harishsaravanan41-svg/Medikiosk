import re
from typing import Dict, Any, List
from app.services.llm_service import llm_service

class TriageService:
    def __init__(self):
        # Deterministic emergency triggers across languages
        self.emergency_keywords = [
            "chest pain", "heart attack", "can't breathe", "cannot breathe", 
            "shortness of breath", "unconscious", "stroke", "paralysis", 
            "severe bleeding", "anaphylaxis", "convulsion", "seizure", "cyanosis",
            "सीने में दर्द", "सांस", "दिल का दौरा",
            "நெஞ்சு வலி", "மூச்சுத்திணறல்", "மாரடைப்பு",
            "ఛాతీ నొప్పి", "శ్వాస", "గుండెపోటు",
            "നെഞ്ചുവേദന", "ശ്വാസതടസ്സം", "ഹൃദയാഘാതം",
            "ಎದೆನೋವು", "ಉಸಿರಾಟ", "ಹೃದಯಾಘಾತ"
        ]
        
        self.urgent_keywords = [
            "high fever", "vomiting blood", "deep cut", "broken bone", "fracture",
            "severe headache", "intense pain", "blindness", "vision loss", "poison",
            "तेज बुखार", "खून की उल्टी", "கடுமையான காய்ச்சல்", "తీవ్రమైన జ్వరం"
        ]
        
        self.symptom_catalog = {
            "chest pain": {"dept": "Emergency / Cardiology", "urgency": "Emergency"},
            "breathing difficulty": {"dept": "Emergency / Pulmonology", "urgency": "Emergency"},
            "fever": {"dept": "General Medicine", "urgency": "Moderate"},
            "cough": {"dept": "Pulmonology / General Medicine", "urgency": "Low"},
            "headache": {"dept": "Neurology / General Medicine", "urgency": "Moderate"},
            "stomach pain": {"dept": "Gastroenterology", "urgency": "Moderate"},
            "abdominal pain": {"dept": "Gastroenterology", "urgency": "Moderate"},
            "nausea": {"dept": "Gastroenterology", "urgency": "Low"},
            "vomiting": {"dept": "Gastroenterology", "urgency": "Moderate"},
            "dizziness": {"dept": "Neurology / ENT", "urgency": "Moderate"},
            "sore throat": {"dept": "ENT", "urgency": "Low"},
            "back pain": {"dept": "Orthopedics", "urgency": "Low"},
            "joint pain": {"dept": "Orthopedics / Rheumatology", "urgency": "Low"},
            "rash": {"dept": "Dermatology", "urgency": "Low"},
            "eye irritation": {"dept": "Ophthalmology", "urgency": "Low"}
        }

    def check_emergency(self, text: str) -> Dict[str, Any]:
        """
        Deterministic safety rule check for immediate life-threatening symptoms.
        """
        text_lower = text.lower()
        for kw in self.emergency_keywords:
            if kw in text_lower:
                return {
                    "is_emergency": True,
                    "keyword_matched": kw,
                    "urgency": "Emergency",
                    "department": "Emergency Room (ER)"
                }
        return {
            "is_emergency": False,
            "keyword_matched": None,
            "urgency": None,
            "department": None
        }

    def analyze_conversation(self, messages: List[Dict[str, str]], language: str = "en") -> Dict[str, Any]:
        """
        Dual triage analysis:
        1. Extracts structured clinical facts from conversation via Qwen LLM.
        2. Applies deterministic safety rules to guarantee emergency escalation cannot be suppressed.
        """
        patient_texts = [m.get("text", "") for m in messages if m.get("sender") == "patient"]
        combined_text = " ".join(patient_texts).lower()

        # Step 1: Deterministic Safety Check
        deterministic_emergency = False
        emergency_trigger = None
        for kw in self.emergency_keywords:
            if kw in combined_text:
                deterministic_emergency = True
                emergency_trigger = kw
                break

        # Step 2: Extract Structured Facts via Qwen Fact Extractor
        clinical_facts = llm_service.extract_clinical_facts(messages, language=language)

        # Step 3: Determine Urgency and Recommended Department
        if deterministic_emergency:
            urgency_level = "Emergency"
            recommended_dept = "Emergency Room (ER)"
        else:
            # Check LLM suggested urgency or catalog lookup
            llm_urgency = (clinical_facts.get("urgency_level") or "needs_assessment").capitalize()
            if llm_urgency in ["Emergency", "Urgent", "Moderate", "Low"]:
                urgency_level = llm_urgency
            else:
                urgency_level = "Moderate" if len(patient_texts) > 0 else "Low"

            # Match department from symptom catalog
            recommended_dept = "General Medicine"
            for symptom, data in self.symptom_catalog.items():
                if symptom in combined_text:
                    recommended_dept = data["dept"]
                    break

        chief_complaint = (
            clinical_facts.get("chief_complaint")
            or (patient_texts[0][:50] if patient_texts else "General Check-in")
        )

        urgency_colors = {
            "Emergency": "#EF4444",
            "Urgent": "#F97316",
            "Moderate": "#F59E0B",
            "Low": "#10B981",
            "Needs_assessment": "#6B7280"
        }

        return {
            "chief_complaint": chief_complaint,
            "location": clinical_facts.get("location"),
            "onset": clinical_facts.get("onset"),
            "character": clinical_facts.get("character"),
            "severity": clinical_facts.get("severity"),
            "aggravating_factors": clinical_facts.get("aggravating_factors"),
            "relieving_factors": clinical_facts.get("relieving_factors"),
            "associated_symptoms": clinical_facts.get("associated_symptoms", []),
            "urgency_level": urgency_level,
            "urgency_color": urgency_colors.get(urgency_level, "#10B981"),
            "recommended_department": recommended_dept,
            "emergency_flag": deterministic_emergency,
            "total_exchanges": len(patient_texts)
        }

triage_service = TriageService()
