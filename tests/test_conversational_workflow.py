"""
Comprehensive Test Suite for MediKiosk Free-Form Conversational AI & Clinical Extractor
Tests:
1. Free general inputs (e.g. "i need python code", "hi", "tell me a joke") -> natural non-medical response
2. Health & symptom conversations -> empathetic, context-aware follow-up
3. Topic changes
4. Clinical Fact Extractor (strict nulls for unmentioned attributes / non-medical turns)
5. Text chat endpoint
6. Deterministic emergency safety layer
"""

import sys
import unittest
from app import create_app
from app.services.llm_service import llm_service
from app.services.triage_service import triage_service
from app.services.db_service import db_service

class TestConversationalWorkflow(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_1_programming_and_general_input(self):
        messages = [{"sender": "patient", "text": "i need python code"}]
        response = llm_service.generate_conversational_response(messages, language="en")
        self.assertIsInstance(response, str)
        # Should not force a pain/symptom question
        self.assertNotIn("pain", response.lower())
        self.assertNotIn("வலி", response)

    def test_2_greeting_input(self):
        messages = [{"sender": "patient", "text": "hi"}]
        response = llm_service.generate_conversational_response(messages, language="en")
        self.assertIsInstance(response, str)
        self.assertTrue(any(w in response.lower() for w in ["hello", "hi", "help", "how"]))

    def test_3_medical_symptom_flow(self):
        messages = [
            {"sender": "patient", "text": "I have chest pain."},
            {"sender": "ai", "text": "I'm sorry you're experiencing that. Can you tell me more about the pain?"},
            {"sender": "patient", "text": "It feels like pressure and started yesterday."}
        ]
        response = llm_service.generate_conversational_response(messages, language="en")
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 5)

    def test_4_clinical_fact_extractor_strict_nulls(self):
        messages = [
            {"sender": "patient", "text": "My stomach pain started yesterday after walking."}
        ]
        facts = llm_service.extract_clinical_facts(messages, language="en")
        self.assertIsInstance(facts, dict)
        self.assertIn("chief_complaint", facts)
        self.assertIn("onset", facts)
        self.assertIn("severity", facts)
        self.assertIsNone(facts["severity"])

    def test_5_chat_text_endpoint(self):
        res = self.client.post("/api/chat/text", json={
            "message": "i need python code",
            "language": "en"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIn("text", data)
        self.assertNotIn("pain", data["text"].lower())

    def test_6_deterministic_emergency_safety(self):
        emergency_input = "Patient has severe crushing chest pain and cannot breathe"
        safety = triage_service.check_emergency(emergency_input)
        self.assertTrue(safety["is_emergency"])
        self.assertEqual(safety["urgency"], "Emergency")
        self.assertEqual(safety["department"], "Emergency Room (ER)")

if __name__ == "__main__":
    unittest.main()
