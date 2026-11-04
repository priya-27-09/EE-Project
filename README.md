# AI Civic Guardian — Smart Civic Issue Detection & Complaint Management System

**AI Civic Guardian** is a government-grade, AI-powered civic issue detection and automated complaint routing platform. Built for municipal governance (Coimbatore City Municipal Corporation service model), the system leverages computer vision to automatically detect, classify, assess severity, and route citizen complaints to responsible municipal departments with end-to-end transparency, SLA tracking, and immutable audit trails.

---

## 🏛️ System Architecture

The platform operates as a unified single-URL application combining an asynchronous FastAPI backend and a responsive Flask web portal:

```
                                 Public HTTP / HTTPS Traffic
                                              │
                           ┌──────────────────┴──────────────────┐
                           │    asgi_app:UnifiedDeploymentApp    │
                           └──────────────────┬──────────────────┘
                                              │
                  ┌───────────────────────────┴───────────────────────────┐
                  ▼                                                       ▼
     API & Documentation Endpoints                             Citizen Web Application
     - /api/v1/auth/...                                        - / (Public Landing & Role Routing)
     - /api/v1/complaints/...                                  - /login & /register
     - /api/v1/ai/...                                          - /dashboard (Citizen Grievance Hub)
     - /api/v1/officer/...                                     - /complaints/new (5-Step Wizard)
     - /api/v1/admin/...                                       - /complaints/<id> (Real-Time Tracking)
     - /api/v1/chatbot/...                                     - /officer/dashboard (Field Officer View)
     - /api/docs (Swagger UI)                                  - /admin/dashboard (Central Operations)
     - /api/health (DB Check)                                  - /static/... (Styles, Scripts, Icons)
```

---

## 🚀 Key Capabilities

1. **AI Image Inference (YOLO11n):**
   - Automatically analyzes uploaded photographic evidence to detect civic issues.
   - Computes deterministic severity (LOW, MEDIUM, HIGH, CRITICAL).
   - Instant manual fallback if AI confidence is below threshold or evidence is text-only.

2. **12 Canonical Civic Issue Categories & Automatic Department Routing:**
   - **0: Garbage Overflow** → Solid Waste Management (Dept ID 6)
   - **1: Illegal Dumping** → Solid Waste Management (Dept ID 6)
   - **2: Pothole** → Roads & Highways (Dept ID 4)
   - **3: Damaged Road** → Roads & Highways (Dept ID 4)
   - **4: Water Leakage** → Water Supply & Sewerage (Dept ID 3)
   - **5: Sewage Overflow** → Water Supply & Sewerage (Dept ID 3)
   - **6: Broken Street Light** → Electricity & Street Lighting (Dept ID 5)
   - **7: Drainage Problem** → Drainage & Flood Management (Dept ID 12)
   - **8: Traffic Issue** → Traffic & Transportation (Dept ID 8)
   - **9: Building Damage** → Building & Construction (Dept ID 10)
   - **10: Park/Public Space Damage** → Parks & Public Spaces (Dept ID 7)
   - **11: Environmental Pollution** → Environmental Protection (Dept ID 9)

3. **High-Accuracy GPS & Interactive Leaflet Maps:**
   - Browser Geolocation API integration with `enableHighAccuracy: true`.
   - Draggable Leaflet map markers with satellite and street layers.
   - Reverse geocoding for automated landmark resolution.

4. **Multi-Role Access Control (RBAC):**
   - **Citizen:** Lodge grievances, track status history, download official PDF acknowledgment letters.
   - **Department Officer:** Department-isolated grievance triage, field remediation evidence upload, SLA monitoring.
   - **Administrator:** System analytics, model registry management, dataset ingestion, and RAG knowledge base.

5. **RAG Civic Knowledge Base Chatbot:**
   - Multi-lingual policy retrieval powered by SentenceTransformers (`all-MiniLM-L6-v2`) and FAISS vector indexing.
   - Answers citizen questions about municipal services, bylaws, and grievance resolution times.

---

## 🛠️ Technology Stack

- **Backend API:** FastAPI, Uvicorn, Pydantic v2
- **Frontend Portal:** Flask, Jinja2, Vanilla JavaScript (ES6+), Leaflet.js
- **Database & ORM:** PostgreSQL 15+, SQLAlchemy 2.0, Alembic Migrations
- **Computer Vision:** Ultralytics YOLO11n (PyTorch CPU / GPU)
- **Vector Search:** FAISS, Sentence-Transformers
- **Deployment:** Render (Single-URL ASGI via `asgi_app.py`), Docker-ready

---

## 📦 Local Quickstart

### Prerequisites
- Python 3.10+ (tested on Python 3.11 and 3.13)
- PostgreSQL running locally or accessible via network

### Installation
```bash
# 1. Clone repository
git clone https://github.com/priya-27-09/EE-Project.git
cd EE-Project

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.render.example .env
# Edit .env with your local PostgreSQL credentials
```

### Running Locally
```bash
# Unified Single-URL Mode (FastAPI + Flask on port 8000)
python asgi_app.py

# Or Legacy Dual-Process Mode (FastAPI on :8000, Flask on :5000)
python run_project.py
```

- **Citizen Web Portal:** `http://127.0.0.1:8000/` (or `:5000` in dual-process mode)
- **Interactive Swagger Docs:** `http://127.0.0.1:8000/api/docs`
- **Database Health Check:** `http://127.0.0.1:8000/api/health`

---

## ☁️ Render Deployment

This repository includes turnkey configuration for Render:

1. Connect your GitHub repository to [Render](https://render.com).
2. Create a new **Web Service** using `render.yaml` (Blueprint) or manual configuration:
   - **Runtime:** `Python`
   - **Build Command:** `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command:** `gunicorn asgi_app:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
3. Configure Environment Variables:
   - `DATABASE_URL`: Your managed PostgreSQL connection URL.
   - `JWT_SECRET_KEY`: A secure 64-character secret.
   - `COIMBATORE_SERVICE_BOUNDARY_ENFORCED`: `false`
4. Mount a persistent disk at `/opt/render/project/src/uploads` (10 GB) for evidence persistence across redeployments.

---

## 🔒 Security & Data Integrity

- Passwords hashed using `bcrypt` (12 rounds).
- Stateless JWT authentication with role-based claim enforcement.
- Input validation on all endpoints preventing SQL injection, XSS, and path traversal.
- Immutable audit logging for all grievance status changes and administrative actions.

