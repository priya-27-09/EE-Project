import sys
import os
from pathlib import Path
from flask import Flask, jsonify, request, g, render_template, send_from_directory, session, redirect

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings
from app.db.health import check_db_health
from app.core.auth import flask_jwt_required

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["PROJECT_NAME"] = settings.PROJECT_NAME
app.secret_key = settings.JWT_SECRET_KEY

# UPLOADS directory
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


# --- HTML Web Pages for Citizen Portal ---

@app.route("/", methods=["GET"])
def index():
    """
    Public home page or authenticated role-based dashboard redirection.
    - Logged-out users see the public landing page.
    - Logged-in citizens are redirected to /dashboard.
    - Logged-in officers are redirected to /officer/dashboard.
    - Logged-in admins are redirected to /admin/dashboard.
    - Query param ?public=1 allows authenticated users to view landing page.
    """
    if not request.args.get("public"):
        user = session.get("user")
        if user and isinstance(user, dict):
            role = (user.get("role") or "").upper()
            if role == "ADMIN":
                return redirect("/admin/dashboard")
            elif role == "OFFICER":
                return redirect("/officer/dashboard")
            elif role == "CITIZEN":
                return redirect("/dashboard")
    return render_template("index.html")


@app.route("/logout", methods=["GET"])
def logout():
    """Clear Flask session and redirect to landing page."""
    session.pop("auth_token", None)
    session.pop("user", None)
    return redirect("/?logged_out=1")


@app.route("/register", methods=["GET"])
def register_page():
    """Citizen registration page."""
    return render_template("register.html")


@app.route("/login", methods=["GET"])
def login_page():
    """Citizen login page."""
    return render_template("login.html")


@app.route("/dashboard", methods=["GET"])
def dashboard_page():
    """Citizen dashboard page."""
    return render_template("dashboard.html")


@app.route("/complaints/new", methods=["GET"])
def new_complaint_wizard():
    """Multi-step citizen complaint wizard."""
    return render_template("wizard.html")


@app.route("/complaints/<complaint_id>", methods=["GET"])
def complaint_detail_page(complaint_id):
    """Single complaint detail and status timeline page."""
    return render_template("complaint_detail.html", complaint_id=complaint_id)


@app.route("/track", methods=["GET"])
def track_complaint_page():
    """Citizen complaint tracking page."""
    return render_template("track.html")


@app.route("/profile", methods=["GET"])
def profile_page():
    """Citizen user profile page."""
    return render_template("profile.html")


@app.route("/admin/dashboard", methods=["GET"])
def admin_dashboard_page():
    """Admin Supervision Dashboard page."""
    return render_template("admin_dashboard.html")


@app.route("/admin/datasets", methods=["GET"])
def admin_datasets_page():
    """Admin YOLO dataset management page."""
    return render_template("admin_datasets.html")


@app.route("/admin/datasets/<dataset_version>", methods=["GET"])
def admin_dataset_detail_page(dataset_version):
    """Admin single dataset version details and validation report page."""
    return render_template("admin_dataset_detail.html", dataset_version=dataset_version)


@app.route("/admin/dataset-sources", methods=["GET"])
def admin_dataset_sources_page():
    """Admin civic dataset acquisition, license audit, and normalization page."""
    return render_template("admin_dataset_sources.html")


@app.route("/admin/models", methods=["GET"])
def admin_models_page():
    """Admin AI YOLO Model Management page."""
    return render_template("admin_models.html")


@app.route("/admin/models/<model_version>", methods=["GET"])
def admin_model_detail_page(model_version):
    """Admin single model version details and metrics page."""
    return render_template("admin_model_detail.html", model_version=model_version)


@app.route("/admin/blockchain", methods=["GET"])
def admin_blockchain_page():
    """Admin Blockchain Audit Trail & Integrity page."""
    return render_template("admin_blockchain.html")


@app.route("/chatbot", methods=["GET"])
def chatbot_page():
    """Citizen Multilingual RAG Civic AI Assistant page."""
    return render_template("chatbot.html")


@app.route("/admin/chatbot", methods=["GET"])
def admin_chatbot_page():
    """Admin Knowledge Base & RAG Management page."""
    return render_template("admin_chatbot.html")


@app.route("/officer/dashboard", methods=["GET"])

def officer_dashboard_page():
    """Officer Department Dashboard page."""
    return render_template("officer_dashboard.html")


@app.route("/officer/complaints/<complaint_id>", methods=["GET"])
def officer_complaint_detail_page(complaint_id):
    """Officer Complaint Detail & Workflow management page."""
    return render_template("officer_complaint_detail.html", complaint_id=complaint_id)


@app.route("/uploads/<path:filename>", methods=["GET"])
def serve_upload(filename):
    """Serve uploaded evidence file securely from disk."""

    return send_from_directory(str(UPLOADS_DIR), filename)



# --- Health & Diagnostic APIs ---

@app.route("/health", methods=["GET"])
def health():
    """
    Service health check returning application and PostgreSQL database health.
    Handles database connection issues gracefully with HTTP 503.
    """
    try:
        db_health = check_db_health()
        is_healthy = db_health.get("status") == "healthy"
        status_code = 200 if is_healthy else 503

        response_payload = {
            "status": "healthy" if is_healthy else "unhealthy",
            "service": "Flask Main Application Service",
            "project": settings.PROJECT_NAME,
            "database": db_health,
        }
        return jsonify(response_payload), status_code
    except Exception as exc:
        return jsonify({
            "status": "unhealthy",
            "service": "Flask Main Application Service",
            "project": settings.PROJECT_NAME,
            "error": "Configuration or internal diagnostic error",
            "detail": str(exc),
        }), 500


@app.route("/api/v1/protected", methods=["GET"])
@flask_jwt_required()
def protected_api():
    """Sample protected Flask API endpoint validating FastAPI-issued JWT."""
    return jsonify({
        "status": "success",
        "message": f"Flask API successfully authenticated user via FastAPI-issued JWT.",
        "user_id": g.current_user_id,
        "email": g.current_user_email,
        "role": g.current_user_role,
    }), 200


@app.route("/api/v1/officer/dashboard", methods=["GET"])
@flask_jwt_required(roles=["OFFICER", "ADMIN"])
def officer_dashboard():
    """Protected Flask endpoint restricted to OFFICER or ADMIN roles."""
    return jsonify({
        "status": "success",
        "message": f"Officer dashboard accessible by {g.current_user_email}.",
        "role": g.current_user_role,
    }), 200


@app.route("/api/v1/blockchain/complaints/<complaint_id>", methods=["GET"])
def get_blockchain_trail(complaint_id):
    """Retrieve blockchain audit records for a complaint from PostgreSQL."""
    from app.db.session import SessionLocal
    from app.models.complaint import Complaint
    from app.models.blockchain_record import BlockchainRecord

    db = SessionLocal()
    try:
        clean_id = complaint_id.strip()
        complaint = db.query(Complaint).filter(Complaint.complaint_id == clean_id).first()
        if not complaint and clean_id.isdigit():
            complaint = db.query(Complaint).filter(Complaint.id == int(clean_id)).first()
        if not complaint:
            return jsonify({"error": "Not Found", "message": f"Complaint '{clean_id}' not found."}), 404

        records = (
            db.query(BlockchainRecord)
            .filter(BlockchainRecord.complaint_id == complaint.id)
            .order_by(BlockchainRecord.created_at.asc())
            .all()
        )
        record_briefs = [
            {
                "id": r.id,
                "complaint_id": r.complaint_id,
                "complaint_public_id": complaint.complaint_id,
                "event_type": r.event_type,
                "event_hash": r.event_hash,
                "data_hash": r.data_hash,
                "blockchain_network": r.blockchain_network,
                "chain_id": r.chain_id,
                "contract_address": r.contract_address,
                "transaction_hash": r.transaction_hash,
                "block_number": r.block_number,
                "blockchain_timestamp": r.blockchain_timestamp.isoformat() if r.blockchain_timestamp else None,
                "status": r.status,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "confirmed_at": r.confirmed_at.isoformat() if r.confirmed_at else None,
            }
            for r in records
        ]
        return jsonify({
            "complaint_id": complaint.complaint_id,
            "records": record_briefs,
        }), 200
    except Exception as exc:
        return jsonify({"error": "Internal Error", "message": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/v1/auth/session-sync", methods=["POST"])
def auth_session_sync():
    """Synchronize browser authentication token and user profile with Flask session."""
    data = request.get_json(silent=True) or {}
    token = data.get("token")
    user = data.get("user")
    if token:
        session["auth_token"] = token
        if user:
            session["user"] = user
        return jsonify({"status": "synchronized"}), 200
    else:
        session.pop("auth_token", None)
        session.pop("user", None)
        return jsonify({"status": "cleared"}), 200


@app.route("/api/v1/auth/session-status", methods=["GET"])
def auth_session_status():
    """Diagnostic check for active Flask session token."""
    token = session.get("auth_token") or request.cookies.get("auth_token")
    user = session.get("user")
    return jsonify({
        "authenticated": bool(token),
        "has_token": bool(token),
        "user": user,
    }), 200


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not Found", "message": "The requested resource was not found."}), 404
    return render_template("index.html"), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal Server Error", "message": "An unexpected server error occurred."}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.FLASK_PORT, debug=False)
