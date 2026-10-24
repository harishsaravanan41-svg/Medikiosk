from flask import Blueprint, request, jsonify
import uuid
from datetime import datetime

from app.services.db_service import db_service
from app.services.memory_service import memory_service

session_bp = Blueprint("session", __name__)


@session_bp.route("/api/session/new", methods=["POST"])
def new_session():
    data = request.get_json() or {}
    patient_id = data.get("patient_id", "P-1001")
    session_id = db_service.create_session(patient_id)
    return jsonify({
        "session_id": session_id,
        "patient_id": patient_id
    })


@session_bp.route("/api/session/<session_id>", methods=["GET"])
def get_session(session_id):
    session = db_service.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session)


@session_bp.route("/api/session/complete", methods=["POST"])
def complete_session():
    data = request.get_json() or {}
    session_id = data.get("session_id")
    session = db_service.get_session(session_id) if session_id else None

    if session and session.get("triage_summary"):
        record = {
            "session_id": session_id,
            "patient_id": session.get("patient_id", "P-1001"),
            "summary": session["triage_summary"],
            "message_count": len(session.get("messages", []))
        }
        saved_record = db_service.save_triage_record(record)
        return jsonify({"status": "saved", "record": saved_record})

    return jsonify({"status": "noop"})


@session_bp.route("/api/patient/new", methods=["POST"])
def create_new_patient():
    """
    Creates a new isolated patient ID (e.g. P-1002, P-1003) and starts a new session.
    """
    data = request.get_json() or {}
    patient_name = data.get("name", "New Patient")
    
    # Generate sequential or unique patient ID
    existing_store = memory_service._read_json()
    existing_nums = []
    for pid in existing_store.keys():
        if pid.startswith("P-") and pid[2:].isdigit():
            existing_nums.append(int(pid[2:]))
    
    next_num = max(existing_nums) + 1 if existing_nums else 1001
    new_pid = f"P-{next_num}"

    # Initialize isolated memory for this new patient
    new_mem = memory_service.get_user_memory(new_pid)
    new_mem["profile"]["name"] = patient_name
    memory_service.save_user_memory(new_pid, new_mem)

    session_id = db_service.create_session(new_pid)

    return jsonify({
        "status": "success",
        "patient_id": new_pid,
        "session_id": session_id,
        "name": patient_name
    })


@session_bp.route("/api/patient/<patient_id>/memory", methods=["GET"])
def get_patient_memory(patient_id):
    """
    Returns persistent isolated memory for the requested patient_id.
    """
    mem = memory_service.get_user_memory(patient_id)
    return jsonify(mem)


@session_bp.route("/api/triage/history", methods=["GET"])
def triage_history():
    records = db_service.get_recent_triage_records(limit=20)
    return jsonify({"records": records})
