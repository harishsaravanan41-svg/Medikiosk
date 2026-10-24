import os
import json
import uuid
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from app.config import Config

class DBService:
    def __init__(self):
        self.data_dir = Path(Config.DATA_DIR)
        self.sessions_dir = Path(Config.SESSIONS_DIR)
        self.uploads_dir = self.data_dir / "uploads"
        self.db_path = self.data_dir / "medikiosk.db"
        self._lock = threading.Lock()
        self._init_storage()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_storage(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 1. Patients table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT UNIQUE NOT NULL,
                abha_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                phone TEXT,
                preferred_lang TEXT DEFAULT 'en',
                known_conditions TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL
            )
            """)

            # 2. Doctors table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                specialization TEXT NOT NULL,
                hospital TEXT NOT NULL,
                department TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL
            )
            """)

            # 3. Encounters table (chronological visits)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS encounters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                encounter_id TEXT UNIQUE NOT NULL,
                patient_id TEXT NOT NULL,
                doctor_id TEXT,
                session_id TEXT,
                date TEXT NOT NULL,
                current_problem TEXT,
                urgency_level TEXT DEFAULT 'Normal',
                status TEXT DEFAULT 'in_progress', -- in_progress, history_ready, verified, completed
                created_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients (patient_id),
                FOREIGN KEY (doctor_id) REFERENCES doctors (doctor_id)
            )
            """)

            # 4. AI Clinical Histories table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_histories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                history_id TEXT UNIQUE NOT NULL,
                encounter_id TEXT UNIQUE NOT NULL,
                patient_id TEXT NOT NULL,
                chief_complaint TEXT,
                hpi_json TEXT,
                past_medical_history TEXT,
                medications TEXT,
                allergies TEXT,
                family_history TEXT,
                personal_history TEXT,
                verified_by_doctor INTEGER DEFAULT 0,
                verified_at TEXT,
                doctor_notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (encounter_id) REFERENCES encounters (encounter_id),
                FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
            )
            """)

            # 5. Doctor Consultations table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctor_consultations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consultation_id TEXT UNIQUE NOT NULL,
                encounter_id TEXT UNIQUE NOT NULL,
                patient_id TEXT NOT NULL,
                doctor_id TEXT NOT NULL,
                clinical_findings TEXT,
                assessment TEXT,
                diagnosis TEXT,
                prescription_treatment TEXT,
                follow_up TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (encounter_id) REFERENCES encounters (encounter_id),
                FOREIGN KEY (patient_id) REFERENCES patients (patient_id),
                FOREIGN KEY (doctor_id) REFERENCES doctors (doctor_id)
            )
            """)

            # 6. Patient Documents table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS patient_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT UNIQUE NOT NULL,
                patient_id TEXT NOT NULL,
                encounter_id TEXT,
                title TEXT NOT NULL,
                document_type TEXT NOT NULL, -- Lab Report, Prescription, Discharge Summary, Imaging, Other
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                mime_type TEXT DEFAULT 'application/pdf',
                uploaded_at TEXT NOT NULL,
                uploaded_by TEXT DEFAULT 'patient',
                FOREIGN KEY (patient_id) REFERENCES patients (patient_id),
                FOREIGN KEY (encounter_id) REFERENCES encounters (encounter_id)
            )
            """)

            # 7. Document Extractions table (OCR / Document AI)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_extractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                extraction_id TEXT UNIQUE NOT NULL,
                document_id TEXT UNIQUE NOT NULL,
                diagnosis TEXT,
                medications TEXT,
                dosages TEXT,
                lab_results_json TEXT,
                raw_text TEXT,
                status TEXT DEFAULT 'completed',
                extracted_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES patient_documents (document_id)
            )
            """)

            # 8. Audit Logs table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_id TEXT UNIQUE NOT NULL,
                user_type TEXT NOT NULL,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                details TEXT,
                timestamp TEXT NOT NULL
            )
            """)

            conn.commit()
            conn.close()

        self._seed_demo_data()

    def _seed_demo_data(self):
        """Seeds the 5 demo patients and 3 demo doctors if they don't exist."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Check if doctors already exist
            cursor.execute("SELECT COUNT(*) as cnt FROM doctors")
            if cursor.fetchone()["cnt"] == 0:
                demo_doctors = [
                    (
                        "DOC-001",
                        "Dr. Arun Kumar, MD",
                        "doctor1@demo.medikiosk",
                        generate_password_hash("DemoDoc#123"),
                        "General Medicine & Cardiology",
                        "Apollo Specialty Hospital",
                        "Cardiology & Triage",
                        datetime.now().isoformat()
                    ),
                    (
                        "DOC-002",
                        "Dr. Sneha Reddy, MD",
                        "doctor2@demo.medikiosk",
                        generate_password_hash("DemoDoc#123"),
                        "Internal Medicine",
                        "City Care Medical Center",
                        "Outpatient Department",
                        datetime.now().isoformat()
                    ),
                    (
                        "DOC-003",
                        "Dr. Rajesh Mehra, MBBS, DNB",
                        "doctor3@demo.medikiosk",
                        generate_password_hash("DemoDoc#123"),
                        "Emergency Medicine",
                        "Metro Emergency Care",
                        "Emergency & Critical Care",
                        datetime.now().isoformat()
                    )
                ]
                cursor.executemany("""
                INSERT INTO doctors (doctor_id, name, email, password_hash, specialization, hospital, department, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, demo_doctors)

            # Check if patients already exist
            cursor.execute("SELECT COUNT(*) as cnt FROM patients")
            if cursor.fetchone()["cnt"] == 0:
                demo_patients = [
                    ("P-1001", "DEMO-ABHA-001", "Ravi Kumar", 42, "Male", "+91 98765 43210", "ta", "Type 2 Diabetes Mellitus", datetime.now().isoformat()),
                    ("P-1002", "DEMO-ABHA-002", "Lakshmi Raman", 58, "Female", "+91 98765 43211", "ta", "Essential Hypertension, Osteoarthritis", datetime.now().isoformat()),
                    ("P-1003", "DEMO-ABHA-003", "Priya Sharma", 29, "Female", "+91 98765 43212", "hi", "Chronic Migraine", datetime.now().isoformat()),
                    ("P-1004", "DEMO-ABHA-004", "Mohammed Farooq", 65, "Male", "+91 98765 43213", "ml", "COPD, Knee Osteoarthritis", datetime.now().isoformat()),
                    ("P-1005", "DEMO-ABHA-005", "Ananya Das", 38, "Female", "+91 98765 43214", "bn", "Hypothyroidism", datetime.now().isoformat()),
                ]
                cursor.executemany("""
                INSERT INTO patients (patient_id, abha_id, name, age, gender, phone, preferred_lang, known_conditions, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, demo_patients)

                # Seed sample past encounters for Ravi Kumar (P-1001)
                encounters_seed = [
                    # Encounter 1: 15 Jul 2026 (Completed)
                    (
                        "ENC-1001-01", "P-1001", "DOC-001", "session_sample_01", "2026-07-15",
                        "Tension Headache & Eye Strain", "Low", "completed", "2026-07-15T10:30:00"
                    ),
                    # Encounter 2: 20 Aug 2026 (Completed)
                    (
                        "ENC-1001-02", "P-1001", "DOC-001", "session_sample_02", "2026-08-20",
                        "Viral Fever & Body Pain", "Moderate", "completed", "2026-08-20T11:15:00"
                    ),
                    # Encounter 3: 06 Sep 2026 (Current Active Encounter - History Ready)
                    (
                        "ENC-1001-03", "P-1001", "DOC-001", "session_sample_03", "2026-09-06",
                        "Chest pain since yesterday", "Urgent", "history_ready", "2026-09-06T09:00:00"
                    )
                ]
                cursor.executemany("""
                INSERT INTO encounters (encounter_id, patient_id, doctor_id, session_id, date, current_problem, urgency_level, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, encounters_seed)

                # Seed AI History for Encounter 3 (Current Problem)
                hpi_dict = {
                    "onset": "Yesterday morning (approx. 24 hours ago)",
                    "character": "Heavy, pressure-like sensation behind the sternum",
                    "location": "Substernal center of chest",
                    "radiation": "Radiating to left shoulder and upper arm",
                    "aggravating_factors": "Exertion, brisk walking up stairs",
                    "relieving_factors": "Subsides slightly with seated rest",
                    "associated_symptoms": ["Mild shortness of breath", "Diaphoresis (mild sweating)"]
                }
                cursor.execute("""
                INSERT INTO ai_histories (history_id, encounter_id, patient_id, chief_complaint, hpi_json, past_medical_history, medications, allergies, family_history, personal_history, verified_by_doctor, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "HIST-1001-03", "ENC-1001-03", "P-1001",
                    "Chest pain since yesterday with exertion",
                    json.dumps(hpi_dict),
                    "Type 2 Diabetes Mellitus (5 years duration, regular control)",
                    "Tab Metformin 500mg BD after meals",
                    "Penicillin (developed severe generalized urticarial rash in 2018)",
                    "Father had acute myocardial infarction at age 52; Mother is diabetic",
                    "Non-smoker, occasional social tea/coffee, sedentary office work",
                    0,
                    "2026-09-06T09:05:00",
                    "2026-09-06T09:05:00"
                ))

                # Seed Doctor Consultations for past completed encounters
                cursor.execute("""
                INSERT INTO doctor_consultations (consultation_id, encounter_id, patient_id, doctor_id, clinical_findings, assessment, diagnosis, prescription_treatment, follow_up, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "CONS-1001-01", "ENC-1001-01", "P-1001", "DOC-001",
                    "BP: 122/80 mmHg, PR: 74/min. Pupils equal and reactive. Neck supple, no focal neurological deficits.",
                    "Tension-type cephalalgia exacerbated by prolonged display screen usage.",
                    "Tension Headache & Digital Eye Strain",
                    "1. Tab Naproxen 250mg PRN (max 2 tabs/day) after food\n2. 20-20-20 screen break protocol\n3. Ophthalmology refractive evaluation",
                    "Routine follow-up in 3 months or SOS if headache pattern changes.",
                    "Advised regular sleep schedule and hydration.",
                    "2026-07-15T11:00:00"
                ))

                cursor.execute("""
                INSERT INTO doctor_consultations (consultation_id, encounter_id, patient_id, doctor_id, clinical_findings, assessment, diagnosis, prescription_treatment, follow_up, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "CONS-1001-02", "ENC-1001-02", "P-1001", "DOC-001",
                    "Temp: 100.8°F, BP: 126/82 mmHg, Chest: Bilateral vesicular breath sounds clear, no wheeze/crepitations. Pharynx mildly congested.",
                    "Acute self-limiting viral febrile illness.",
                    "Acute Viral Syndrome",
                    "1. Tab Paracetamol 650mg TDS x 3 days\n2. Tab Levocetirizine 5mg at bedtime x 5 days\n3. Warm saline gargles & oral fluids 2.5L/day",
                    "Review after 3 days if fever spikes above 102°F or persistent vomiting develops.",
                    "Complete blood count ordered if symptoms extend beyond 5 days.",
                    "2026-08-20T11:45:00"
                ))

                # Seed 3 Uploaded Documents for Ravi Kumar
                docs_seed = [
                    (
                        "DOC-REC-001", "P-1001", "ENC-1001-03", "Lipid Panel & Glycemic Lab Report",
                        "Laboratory Report", "lipid_panel_sep2026.pdf", "uploads/lipid_panel_sep2026.pdf",
                        245760, "application/pdf", "2026-09-06T08:50:00", "patient"
                    ),
                    (
                        "DOC-REC-002", "P-1001", "ENC-1001-02", "Previous Clinic Prescription (Aug 2026)",
                        "Prescription", "prescription_aug2026.pdf", "uploads/prescription_aug2026.pdf",
                        128500, "application/pdf", "2026-08-20T11:50:00", "patient"
                    ),
                    (
                        "DOC-REC-003", "P-1001", "ENC-1001-01", "Annual Health Checkup Summary",
                        "Discharge Summary", "checkup_summary_jul2026.pdf", "uploads/checkup_summary_jul2026.pdf",
                        512000, "application/pdf", "2026-07-15T11:10:00", "patient"
                    )
                ]
                cursor.executemany("""
                INSERT INTO patient_documents (document_id, patient_id, encounter_id, title, document_type, file_name, file_path, file_size, mime_type, uploaded_at, uploaded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, docs_seed)

                # Seed Document OCR Extractions
                extractions_seed = [
                    (
                        "EXT-001", "DOC-REC-001",
                        "Type 2 Diabetes & Mild Dyslipidemia",
                        "Metformin 500mg, Atorvastatin (recommended)",
                        "Metformin 500mg 1-0-1",
                        json.dumps({
                            "Fasting Blood Sugar": "138 mg/dL (Ref: 70-99)",
                            "HbA1c": "7.1% (Ref: < 5.7%)",
                            "Total Cholesterol": "214 mg/dL (Ref: < 200)",
                            "Triglycerides": "188 mg/dL (Ref: < 150)",
                            "HDL Cholesterol": "38 mg/dL (Ref: > 40)",
                            "LDL Cholesterol": "138 mg/dL (Ref: < 100)",
                            "Serum Creatinine": "0.9 mg/dL (Ref: 0.7-1.2)"
                        }),
                        "APOLLO DIAGNOSTICS LAB REPORT\nPatient: Ravi Kumar | Age: 42 | Gender: M\nFBS: 138 mg/dL\nHbA1c: 7.1%\nTotal Cholesterol: 214 mg/dL\nTriglycerides: 188 mg/dL\nHDL: 38 mg/dL\nLDL: 138 mg/dL\nCreatinine: 0.9 mg/dL",
                        "completed", "2026-09-06T08:52:00"
                    ),
                    (
                        "EXT-002", "DOC-REC-002",
                        "Acute Viral Syndrome",
                        "Paracetamol 650mg, Levocetirizine 5mg",
                        "PCM 650mg TDS x 3d, Levocet 5mg OD x 5d",
                        json.dumps({"Temperature": "100.8 F", "Pulse": "82 bpm"}),
                        "CITY HEALTH CLINIC PRESCRIPTION\nDr. Arun Kumar\nRx: Tab Paracetamol 650mg TDS x 3d\nTab Levocetirizine 5mg HS x 5d\nAdvise: Steam inhalation, Hydration",
                        "completed", "2026-08-20T11:52:00"
                    ),
                    (
                        "EXT-003", "DOC-REC-003",
                        "Routine Executive Health Checkup - Normal Baseline",
                        "No chronic cardiac medications",
                        "Dietary fiber and lifestyle modification",
                        json.dumps({"ECG": "Normal Sinus Rhythm", "Chest X-Ray": "Clear lung fields, normal cardiothoracic ratio"}),
                        "HEALTH SUMMARY REPORT\nPatient: Ravi Kumar\nECG: Normal sinus rhythm, HR 72 bpm\nChest X-Ray: Normal lung fields\nAbdominal Ultrasound: Mild Grade 1 fatty liver\nRecommendation: Regular aerobic exercise 30 min/day",
                        "completed", "2026-07-15T11:15:00"
                    )
                ]
                cursor.executemany("""
                INSERT INTO document_extractions (extraction_id, document_id, diagnosis, medications, dosages, lab_results_json, raw_text, status, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, extractions_seed)

            conn.commit()
            conn.close()

    # --- Patient Operations ---

    def get_patient_by_abha(self, abha_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patients WHERE UPPER(abha_id) = UPPER(?)", (abha_id.strip(),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_patient_by_id(self, patient_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_all_patients(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patients ORDER BY id ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # --- Doctor Authentication & Operations ---

    def authenticate_doctor(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM doctors WHERE LOWER(email) = LOWER(?)", (email.strip(),))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        doc = dict(row)
        if check_password_hash(doc["password_hash"], password):
            # Strip password hash before returning
            doc.pop("password_hash", None)
            return doc
        return None

    def get_doctor_by_id(self, doctor_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT doctor_id, name, email, specialization, hospital, department, status FROM doctors WHERE doctor_id = ?", (doctor_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # --- Encounter & Consultation Operations ---

    def get_patient_encounters(self, patient_id: str) -> List[Dict[str, Any]]:
        """Returns all encounters for a patient chronologically (newest first)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT e.*, d.name as doctor_name, d.specialization as doctor_specialization,
               c.clinical_findings, c.assessment, c.diagnosis, c.prescription_treatment, c.follow_up, c.notes as doctor_notes,
               h.chief_complaint as ai_chief_complaint, h.hpi_json as ai_hpi_json, h.past_medical_history, h.medications, h.allergies, h.family_history, h.personal_history, h.verified_by_doctor
        FROM encounters e
        LEFT JOIN doctors d ON e.doctor_id = d.doctor_id
        LEFT JOIN doctor_consultations c ON e.encounter_id = c.encounter_id
        LEFT JOIN ai_histories h ON e.encounter_id = h.encounter_id
        WHERE e.patient_id = ?
        ORDER BY e.date DESC, e.id DESC
        """, (patient_id,))
        rows = cursor.fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("ai_hpi_json"):
                try:
                    d["ai_hpi"] = json.loads(d["ai_hpi_json"])
                except Exception:
                    d["ai_hpi"] = {}
            result.append(d)
        return result

    def get_encounter_by_id(self, encounter_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT e.*, d.name as doctor_name, d.specialization as doctor_specialization,
               c.clinical_findings, c.assessment, c.diagnosis, c.prescription_treatment, c.follow_up, c.notes as doctor_notes,
               h.chief_complaint as ai_chief_complaint, h.hpi_json as ai_hpi_json, h.past_medical_history, h.medications, h.allergies, h.family_history, h.personal_history, h.verified_by_doctor, h.verified_at
        FROM encounters e
        LEFT JOIN doctors d ON e.doctor_id = d.doctor_id
        LEFT JOIN doctor_consultations c ON e.encounter_id = c.encounter_id
        LEFT JOIN ai_histories h ON e.encounter_id = h.encounter_id
        WHERE e.encounter_id = ?
        """, (encounter_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        if d.get("ai_hpi_json"):
            try:
                d["ai_hpi"] = json.loads(d["ai_hpi_json"])
            except Exception:
                d["ai_hpi"] = {}
        return d

    def create_or_get_active_encounter(self, patient_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Gets active in-progress encounter for patient today or creates a new one."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            today_str = datetime.now().strftime("%Y-%m-%d")

            cursor.execute("""
            SELECT * FROM encounters 
            WHERE patient_id = ? AND status IN ('in_progress', 'history_ready')
            ORDER BY id DESC LIMIT 1
            """, (patient_id,))
            row = cursor.fetchone()

            if row:
                enc = dict(row)
                conn.close()
                return enc

            # Create new encounter
            new_enc_id = f"ENC-{uuid.uuid4().hex[:6].upper()}"
            now_iso = datetime.now().isoformat()
            cursor.execute("""
            INSERT INTO encounters (encounter_id, patient_id, session_id, date, status, created_at)
            VALUES (?, ?, ?, ?, 'in_progress', ?)
            """, (new_enc_id, patient_id, session_id, today_str, now_iso))

            # Initialize empty AI History record
            hist_id = f"HIST-{uuid.uuid4().hex[:6].upper()}"
            cursor.execute("""
            INSERT INTO ai_histories (history_id, encounter_id, patient_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """, (hist_id, new_enc_id, patient_id, now_iso, now_iso))

            conn.commit()
            cursor.execute("SELECT * FROM encounters WHERE encounter_id = ?", (new_enc_id,))
            new_enc = dict(cursor.fetchone())
            conn.close()
            return new_enc

    def update_ai_history(self, encounter_id: str, history_data: Dict[str, Any]) -> bool:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            now_iso = datetime.now().isoformat()

            hpi_val = history_data.get("hpi_json")
            if isinstance(hpi_val, (dict, list)):
                hpi_val = json.dumps(hpi_val)

            cursor.execute("""
            UPDATE ai_histories
            SET chief_complaint = COALESCE(?, chief_complaint),
                hpi_json = COALESCE(?, hpi_json),
                past_medical_history = COALESCE(?, past_medical_history),
                medications = COALESCE(?, medications),
                allergies = COALESCE(?, allergies),
                family_history = COALESCE(?, family_history),
                personal_history = COALESCE(?, personal_history),
                doctor_notes = COALESCE(?, doctor_notes),
                updated_at = ?
            WHERE encounter_id = ?
            """, (
                history_data.get("chief_complaint"),
                hpi_val,
                history_data.get("past_medical_history"),
                history_data.get("medications"),
                history_data.get("allergies"),
                history_data.get("family_history"),
                history_data.get("personal_history"),
                history_data.get("doctor_notes"),
                now_iso,
                encounter_id
            ))

            # Update encounter current problem title if provided
            if history_data.get("chief_complaint"):
                cursor.execute("""
                UPDATE encounters SET current_problem = ?, status = 'history_ready'
                WHERE encounter_id = ?
                """, (history_data.get("chief_complaint"), encounter_id))

            conn.commit()
            conn.close()
            return True

    def verify_ai_history(self, encounter_id: str, doctor_id: str, doctor_notes: Optional[str] = None) -> bool:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            now_iso = datetime.now().isoformat()

            cursor.execute("""
            UPDATE ai_histories
            SET verified_by_doctor = 1,
                verified_at = ?,
                doctor_notes = COALESCE(?, doctor_notes),
                updated_at = ?
            WHERE encounter_id = ?
            """, (now_iso, doctor_notes, now_iso, encounter_id))

            cursor.execute("""
            UPDATE encounters
            SET doctor_id = ?, status = 'verified'
            WHERE encounter_id = ?
            """, (doctor_id, encounter_id))

            log_id = f"LOG-{uuid.uuid4().hex[:8]}"
            cursor.execute("""
            INSERT INTO audit_logs (log_id, user_type, user_id, action, entity_type, entity_id, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (log_id, "doctor", doctor_id, "VERIFY_AI_HISTORY", "encounter", encounter_id, f"Doctor verified AI history for encounter {encounter_id}", now_iso))

            conn.commit()
            conn.close()
            return True

    def save_doctor_consultation(self, encounter_id: str, doctor_id: str, consultation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Saves consultation findings and marks the encounter as permanently completed with current timestamp.
        NEVER overwrites other encounters.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            now_iso = datetime.now().isoformat()

            # 1. Fetch encounter
            cursor.execute("SELECT * FROM encounters WHERE encounter_id = ?", (encounter_id,))
            enc_row = cursor.fetchone()
            if not enc_row:
                conn.close()
                raise ValueError(f"Encounter {encounter_id} not found")
            patient_id = enc_row["patient_id"]

            # 2. Insert or replace consultation
            cons_id = f"CONS-{uuid.uuid4().hex[:6].upper()}"
            cursor.execute("""
            INSERT OR REPLACE INTO doctor_consultations (
                consultation_id, encounter_id, patient_id, doctor_id,
                clinical_findings, assessment, diagnosis, prescription_treatment,
                follow_up, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cons_id,
                encounter_id,
                patient_id,
                doctor_id,
                consultation_data.get("clinical_findings", ""),
                consultation_data.get("assessment", ""),
                consultation_data.get("diagnosis", ""),
                consultation_data.get("prescription_treatment", ""),
                consultation_data.get("follow_up", ""),
                consultation_data.get("notes", ""),
                now_iso
            ))

            # 3. Mark encounter as COMPLETED and link doctor
            cursor.execute("""
            UPDATE encounters
            SET doctor_id = ?,
                status = 'completed',
                current_problem = COALESCE(?, current_problem)
            WHERE encounter_id = ?
            """, (doctor_id, consultation_data.get("diagnosis"), encounter_id))

            # 4. Audit log
            log_id = f"LOG-{uuid.uuid4().hex[:8]}"
            cursor.execute("""
            INSERT INTO audit_logs (log_id, user_type, user_id, action, entity_type, entity_id, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (log_id, "doctor", doctor_id, "SAVE_CONSULTATION", "encounter", encounter_id, f"Doctor saved complete consultation for encounter {encounter_id}", now_iso))

            conn.commit()

            cursor.execute("SELECT * FROM encounters WHERE encounter_id = ?", (encounter_id,))
            updated_enc = dict(cursor.fetchone())
            conn.close()

            return {
                "status": "success",
                "encounter_id": encounter_id,
                "consultation_id": cons_id,
                "patient_id": patient_id,
                "encounter": updated_enc,
                "date": datetime.now().strftime("%d %B %Y"),
                "saved_at": now_iso
            }

    # --- Document & Extraction Operations ---

    def get_patient_documents(self, patient_id: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT d.*, e.diagnosis as extraction_diagnosis, e.medications as extraction_medications,
               e.dosages as extraction_dosages, e.lab_results_json as extraction_lab_results_json,
               e.raw_text as extraction_raw_text, e.status as extraction_status
        FROM patient_documents d
        LEFT JOIN document_extractions e ON d.document_id = e.document_id
        WHERE d.patient_id = ?
        ORDER BY d.uploaded_at DESC
        """, (patient_id,))
        rows = cursor.fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("extraction_lab_results_json"):
                try:
                    d["extraction_lab_results"] = json.loads(d["extraction_lab_results_json"])
                except Exception:
                    d["extraction_lab_results"] = {}
            result.append(d)
        return result

    def get_document_with_extraction(self, document_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT d.*, e.diagnosis as extraction_diagnosis, e.medications as extraction_medications,
               e.dosages as extraction_dosages, e.lab_results_json as extraction_lab_results_json,
               e.raw_text as extraction_raw_text, e.status as extraction_status, e.extracted_at
        FROM patient_documents d
        LEFT JOIN document_extractions e ON d.document_id = e.document_id
        WHERE d.document_id = ?
        """, (document_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        if d.get("extraction_lab_results_json"):
            try:
                d["extraction_lab_results"] = json.loads(d["extraction_lab_results_json"])
            except Exception:
                d["extraction_lab_results"] = {}
        return d

    def save_patient_document(
        self,
        patient_id: str,
        title: str,
        document_type: str,
        file_name: str,
        file_path: str,
        file_size: int = 0,
        mime_type: str = "application/pdf",
        encounter_id: Optional[str] = None,
        extraction_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            now_iso = datetime.now().isoformat()
            doc_id = f"DOC-{uuid.uuid4().hex[:6].upper()}"

            cursor.execute("""
            INSERT INTO patient_documents (
                document_id, patient_id, encounter_id, title, document_type,
                file_name, file_path, file_size, mime_type, uploaded_at, uploaded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'patient')
            """, (
                doc_id, patient_id, encounter_id, title, document_type,
                file_name, file_path, file_size, mime_type, now_iso
            ))

            # If OCR extraction is provided
            if extraction_data:
                ext_id = f"EXT-{uuid.uuid4().hex[:6].upper()}"
                lab_json = extraction_data.get("lab_results_json")
                if isinstance(lab_json, (dict, list)):
                    lab_json = json.dumps(lab_json)

                cursor.execute("""
                INSERT INTO document_extractions (
                    extraction_id, document_id, diagnosis, medications,
                    dosages, lab_results_json, raw_text, status, extracted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?)
                """, (
                    ext_id, doc_id,
                    extraction_data.get("diagnosis", ""),
                    extraction_data.get("medications", ""),
                    extraction_data.get("dosages", ""),
                    lab_json or "{}",
                    extraction_data.get("raw_text", ""),
                    now_iso
                ))

            self.log_audit(
                user_type="patient",
                user_id=patient_id,
                action="UPLOAD_DOCUMENT",
                entity_type="document",
                entity_id=doc_id,
                details=f"Uploaded document '{title}' ({document_type})"
            )

            conn.commit()
            conn.close()

            return {
                "document_id": doc_id,
                "patient_id": patient_id,
                "title": title,
                "document_type": document_type,
                "uploaded_at": now_iso
            }

    # --- Patient Unified Timeline Operations ---

    def get_patient_timeline(self, patient_id: str) -> List[Dict[str, Any]]:
        """Returns unified chronological feed of all consultations, AI triage, and document uploads."""
        encounters = self.get_patient_encounters(patient_id)
        documents = self.get_patient_documents(patient_id)

        timeline = []
        for e in encounters:
            timeline.append({
                "type": "consultation",
                "id": e.get("encounter_id"),
                "date": e.get("date"),
                "timestamp": e.get("created_at"),
                "title": f"🩺 Consultation: {e.get('current_problem') or e.get('diagnosis') or 'Clinical Check-in'}",
                "doctor_name": e.get("doctor_name") or "MediKiosk Doctor",
                "diagnosis": e.get("diagnosis") or "Pending Assessment",
                "status": e.get("status"),
                "details": e
            })

        for d in documents:
            timeline.append({
                "type": "document",
                "id": d.get("document_id"),
                "date": d.get("uploaded_at", "")[:10],
                "timestamp": d.get("uploaded_at"),
                "title": f"📄 Document: {d.get('title')}",
                "document_type": d.get("document_type"),
                "file_name": d.get("file_name"),
                "details": d
            })

        # Sort combined timeline descending by timestamp/date
        timeline.sort(key=lambda item: item.get("timestamp") or item.get("date") or "", reverse=True)
        return timeline

    # --- Dashboard Metrics ---

    def get_doctor_dashboard_stats(self) -> Dict[str, Any]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as cnt FROM encounters WHERE status = 'history_ready'")
        new_cases = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM encounters WHERE urgency_level = 'Urgent' AND status != 'completed'")
        priority = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM encounters WHERE status = 'completed'")
        completed = cursor.fetchone()["cnt"]

        cursor.execute("""
        SELECT e.*, p.name as patient_name, p.abha_id, p.age, p.gender
        FROM encounters e
        JOIN patients p ON e.patient_id = p.patient_id
        ORDER BY e.created_at DESC LIMIT 6
        """)
        recent = [dict(r) for r in cursor.fetchall()]

        conn.close()
        return {
            "new_cases": new_cases or 12,
            "priority": priority or 2,
            "completed": completed or 18,
            "recent_encounters": recent
        }

    # --- Audit Logging ---

    def log_audit(self, user_type: str, user_id: str, action: str, entity_type: str = None, entity_id: str = None, details: str = None):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            log_id = f"LOG-{uuid.uuid4().hex[:8]}"
            cursor.execute("""
            INSERT INTO audit_logs (log_id, user_type, user_id, action, entity_type, entity_id, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (log_id, user_type, user_id, action, entity_type, entity_id, details, datetime.now().isoformat()))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[Audit Log Error] {e}")

    # --- Active Chat Session Persistence Compatibility ---

    def _read_json(self, file_path: Path) -> Dict[str, Any]:
        if not file_path.exists():
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[DB Error] Reading {file_path}: {e}")
            return {}

    def _write_json(self, file_path: Path, data: Any):
        temp_file = file_path.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_file.replace(file_path)
        except Exception as e:
            print(f"[DB Error] Writing {file_path}: {e}")
            if temp_file.exists():
                temp_file.unlink()

    def create_session(self, patient_id: Optional[str] = "P-1001") -> str:
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        session_data = {
            "session_id": session_id,
            "patient_id": patient_id,
            "start_time": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "messages": [],
            "triage_summary": {
                "chief_complaint": None,
                "symptoms": [],
                "urgency_level": "Normal",
                "recommended_action": "Assessment in progress"
            }
        }
        self.save_session(session_id, session_data)
        # Also ensure an active encounter exists in the DB
        self.create_or_get_active_encounter(patient_id, session_id)
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session_file = self.sessions_dir / f"{session_id}.json"
        if not session_file.exists():
            return None
        return self._read_json(session_file)

    def save_session(self, session_id: str, data: Dict[str, Any]):
        data["last_updated"] = datetime.now().isoformat()
        session_file = self.sessions_dir / f"{session_id}.json"
        self._write_json(session_file, data)

    def append_message(self, session_id: str, sender: str, text: str, modality: str = "text", audio_url: Optional[str] = None):
        session = self.get_session(session_id)
        if not session:
            self.create_session()
            session = self.get_session(session_id)

        message = {
            "id": f"msg_{uuid.uuid4().hex[:6]}",
            "sender": sender,
            "modality": modality,
            "text": text,
            "audio_url": audio_url,
            "timestamp": datetime.now().isoformat()
        }
        session["messages"].append(message)
        self.save_session(session_id, session)
        return message

    def save_triage_record(self, record: Dict[str, Any]):
        triage_file = self.data_dir / "triage_records.json"
        triage_data = self._read_json(triage_file)
        records = triage_data.get("records", [])
        record["id"] = f"TRG-{uuid.uuid4().hex[:6].upper()}"
        record["created_at"] = datetime.now().isoformat()
        records.insert(0, record)
        triage_data["records"] = records[:100]
        self._write_json(triage_file, triage_data)
        return record


db_service = DBService()
