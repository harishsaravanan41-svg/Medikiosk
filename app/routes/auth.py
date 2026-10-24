from flask import Blueprint, request, jsonify, session
from app.services.db_service import db_service

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/api/auth/patient/login", methods=["POST"])
def patient_login():
    """
    Demo Patient Login via ABHA ID.
    Authenticates against seeded demo patient database records (DEMO-ABHA-001 through 005).
    """
    data = request.get_json(silent=True) or {}
    abha_id = str(data.get("abha_id", "")).strip()

    if not abha_id:
        return jsonify({"status": "error", "message": "ABHA ID is required"}), 400

    patient = db_service.get_patient_by_abha(abha_id)
    if not patient:
        return jsonify({
            "status": "error",
            "message": f"Patient with ABHA ID '{abha_id}' not found. Please verify or use demo IDs (DEMO-ABHA-001 to 005)."
        }), 404

    # Create session
    session["user_type"] = "patient"
    session["patient_id"] = patient["patient_id"]
    session["abha_id"] = patient["abha_id"]
    session["name"] = patient["name"]

    # Ensure an active encounter exists for today
    active_enc = db_service.create_or_get_active_encounter(patient["patient_id"])

    # Audit log
    db_service.log_audit(
        user_type="patient",
        user_id=patient["patient_id"],
        action="PATIENT_LOGIN",
        entity_type="patient",
        entity_id=patient["patient_id"],
        details=f"Patient {patient['name']} logged in via ABHA {patient['abha_id']}"
    )

    return jsonify({
        "status": "success",
        "message": f"Welcome back, {patient['name']}!",
        "patient": patient,
        "active_encounter": active_enc
    })


@auth_bp.route("/api/auth/doctor/login", methods=["POST"])
def doctor_login():
    """
    Doctor Authentication via Email and Password.
    Authenticates against seeded demo doctor accounts (doctor1@demo.medikiosk).
    """
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip()
    password = str(data.get("password", "")).strip()

    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password are required"}), 400

    doctor = db_service.authenticate_doctor(email, password)
    if not doctor:
        return jsonify({
            "status": "error",
            "message": "Invalid email or password. Please use demo doctor credentials (e.g. doctor1@demo.medikiosk / DemoDoc#123)."
        }), 401

    session["user_type"] = "doctor"
    session["doctor_id"] = doctor["doctor_id"]
    session["doctor_name"] = doctor["name"]
    session["doctor_email"] = doctor["email"]

    db_service.log_audit(
        user_type="doctor",
        user_id=doctor["doctor_id"],
        action="DOCTOR_LOGIN",
        entity_type="doctor",
        entity_id=doctor["doctor_id"],
        details=f"Doctor {doctor['name']} ({doctor['email']}) logged in"
    )

    return jsonify({
        "status": "success",
        "message": f"Welcome, {doctor['name']}!",
        "doctor": doctor
    })


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    user_type = session.get("user_type", "anonymous")
    user_id = session.get("doctor_id") or session.get("patient_id", "guest")
    session.clear()

    db_service.log_audit(
        user_type=user_type,
        user_id=user_id,
        action="LOGOUT",
        details="User logged out"
    )

    return jsonify({"status": "success", "message": "Successfully logged out"})


@auth_bp.route("/api/auth/me", methods=["GET"])
def get_current_user():
    user_type = session.get("user_type")
    if not user_type:
        return jsonify({"authenticated": False})

    if user_type == "patient":
        patient = db_service.get_patient_by_id(session.get("patient_id"))
        return jsonify({"authenticated": True, "user_type": "patient", "user": patient})
    elif user_type == "doctor":
        doctor = db_service.get_doctor_by_id(session.get("doctor_id"))
        return jsonify({"authenticated": True, "user_type": "doctor", "user": doctor})

    return jsonify({"authenticated": False})
