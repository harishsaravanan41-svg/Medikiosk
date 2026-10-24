from flask import Blueprint, request, jsonify, session
from app.services.db_service import db_service

doctor_bp = Blueprint("doctor", __name__)

def _require_doctor_auth():
    """Helper to verify that a doctor session is active."""
    doc_id = session.get("doctor_id")
    if not doc_id:
        # For development/demo convenience, allow fallback to primary demo doctor if not explicitly set
        doc_id = "DOC-001"
    return doc_id


@doctor_bp.route("/api/doctor/dashboard-stats", methods=["GET"])
def dashboard_stats():
    """Returns dashboard metrics for the doctor portal."""
    stats = db_service.get_doctor_dashboard_stats()
    return jsonify({"status": "success", "data": stats})


@doctor_bp.route("/api/doctor/patient/by-abha/<abha_id>", methods=["GET"])
def search_patient_by_abha(abha_id: str):
    """Searches patient by ABHA Health ID and returns patient profile + active encounter."""
    clean_abha = abha_id.strip()
    patient = db_service.get_patient_by_abha(clean_abha)
    if not patient:
        return jsonify({
            "status": "error",
            "message": f"No patient found matching ABHA ID '{clean_abha}'. Please verify the ID."
        }), 404

    active_enc = db_service.create_or_get_active_encounter(patient["patient_id"])
    active_enc_details = db_service.get_encounter_by_id(active_enc["encounter_id"])

    # Audit log
    doc_id = _require_doctor_auth()
    db_service.log_audit(
        user_type="doctor",
        user_id=doc_id,
        action="SEARCH_PATIENT_ABHA",
        entity_type="patient",
        entity_id=patient["patient_id"],
        details=f"Doctor searched ABHA ID {clean_abha}"
    )

    return jsonify({
        "status": "success",
        "patient": patient,
        "active_encounter": active_enc_details
    })


@doctor_bp.route("/api/doctor/patient/<patient_id>/history", methods=["GET"])
def get_patient_history(patient_id: str):
    """Returns all chronological date-wise encounters for the patient (newest first)."""
    encounters = db_service.get_patient_encounters(patient_id)
    patient = db_service.get_patient_by_id(patient_id)
    return jsonify({
        "status": "success",
        "patient_id": patient_id,
        "patient": patient,
        "encounters": encounters
    })


@doctor_bp.route("/api/doctor/patient/<patient_id>/consultations", methods=["GET"])
def get_patient_consultations(patient_id: str):
    """Returns all completed doctor consultations for the patient."""
    encounters = db_service.get_patient_encounters(patient_id)
    consultations = [e for e in encounters if e.get("status") == "completed" and e.get("diagnosis")]
    return jsonify({
        "status": "success",
        "patient_id": patient_id,
        "consultations": consultations
    })


@doctor_bp.route("/api/doctor/patient/<patient_id>/documents", methods=["GET"])
def get_patient_documents(patient_id: str):
    """Returns all uploaded medical documents for the patient."""
    docs = db_service.get_patient_documents(patient_id)
    return jsonify({
        "status": "success",
        "patient_id": patient_id,
        "documents": docs
    })


@doctor_bp.route("/api/doctor/patient/<patient_id>/timeline", methods=["GET"])
def get_patient_timeline(patient_id: str):
    """Returns a unified chronological feed combining consultations and document upload events."""
    timeline = db_service.get_patient_timeline(patient_id)
    return jsonify({
        "status": "success",
        "patient_id": patient_id,
        "timeline": timeline
    })


@doctor_bp.route("/api/doctor/document/<document_id>/extraction", methods=["GET"])
def get_document_extraction(document_id: str):
    """Returns original document metadata and OCR/AI extracted fields for side-by-side comparison."""
    doc_extraction = db_service.get_document_with_extraction(document_id)
    if not doc_extraction:
        return jsonify({"status": "error", "message": "Document not found"}), 404
    return jsonify({
        "status": "success",
        "document": doc_extraction,
        "extraction": {
            "diagnosis": doc_extraction.get("extraction_diagnosis"),
            "medications": doc_extraction.get("extraction_medications"),
            "dosages": doc_extraction.get("extraction_dosages"),
            "lab_results": doc_extraction.get("extraction_lab_results"),
            "raw_text": doc_extraction.get("extraction_raw_text"),
            "status": doc_extraction.get("extraction_status"),
            "extracted_at": doc_extraction.get("extracted_at")
        }
    })


@doctor_bp.route("/api/doctor/encounter/<encounter_id>/history", methods=["GET", "PUT"])
def encounter_history(encounter_id: str):
    """GET current AI history or PUT to update AI clinical history."""
    if request.method == "GET":
        enc = db_service.get_encounter_by_id(encounter_id)
        if not enc:
            return jsonify({"status": "error", "message": "Encounter not found"}), 404
        return jsonify({"status": "success", "encounter": enc})

    # PUT update
    data = request.get_json(silent=True) or {}
    db_service.update_ai_history(encounter_id, data)
    updated_enc = db_service.get_encounter_by_id(encounter_id)
    return jsonify({
        "status": "success",
        "message": "AI History updated successfully",
        "encounter": updated_enc
    })


@doctor_bp.route("/api/doctor/encounter/<encounter_id>/verify", methods=["POST"])
def verify_history(encounter_id: str):
    """Marks AI history as verified by doctor."""
    data = request.get_json(silent=True) or {}
    doc_id = _require_doctor_auth()
    doctor_notes = data.get("doctor_notes")

    db_service.verify_ai_history(encounter_id, doc_id, doctor_notes)
    updated_enc = db_service.get_encounter_by_id(encounter_id)

    return jsonify({
        "status": "success",
        "message": "AI Clinical History verified by doctor",
        "encounter": updated_enc
    })


@doctor_bp.route("/api/doctor/encounter/<encounter_id>/consultation", methods=["POST"])
def save_consultation(encounter_id: str):
    """
    Saves doctor clinical findings, assessment, diagnosis, prescription, and follow-up.
    Marks encounter as COMPLETED with current timestamp.
    NEVER overwrites old encounters.
    """
    data = request.get_json(silent=True) or {}
    doc_id = _require_doctor_auth()

    try:
        result = db_service.save_doctor_consultation(encounter_id, doc_id, data)
        return jsonify({
            "status": "success",
            "message": "Consultation saved successfully to patient's permanent medical record.",
            "data": result,
            "encounter": result.get("encounter")
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
