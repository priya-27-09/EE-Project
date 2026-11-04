/**
 * AI Civic Guardian — Centralized API Client
 * Interacts with FastAPI backend on port 8000
 */

const API_BASE_URL = (typeof window !== "undefined" && window.location.port === "5000")
  ? "http://127.0.0.1:8000"
  : "";

function escapeHtml(text) {
  if (text === null || text === undefined) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
if (typeof window !== "undefined") {
  window.escapeHtml = escapeHtml;
}

const ApiClient = {
  escapeHtml,

  getToken() {
    let token = null;
    try {
      token = localStorage.getItem("auth_token");
    } catch (_) {}
    if (!token && typeof document !== "undefined" && document.cookie) {
      const match = document.cookie.match(/(?:^|;\s*)auth_token=([^;]+)/);
      if (match) {
        token = decodeURIComponent(match[1]);
        try { localStorage.setItem("auth_token", token); } catch (_) {}
      }
    }
    return token;
  },

  setToken(token, user) {
    if (token) {
      try { localStorage.setItem("auth_token", token); } catch (_) {}
      if (typeof document !== "undefined") {
        document.cookie = `auth_token=${encodeURIComponent(token)}; path=/; SameSite=Lax`;
      }
    }
    if (user) {
      try { localStorage.setItem("auth_user", JSON.stringify(user)); } catch (_) {}
    }
    // Background sync with Flask session
    if (token && typeof fetch !== "undefined") {
      try {
        fetch("/api/v1/auth/session-sync", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
          },
          body: JSON.stringify({ token, user: user || null })
        }).catch(() => {});
      } catch (_) {}
    }
  },

  clearToken() {
    try {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("auth_user");
    } catch (_) {}
    if (typeof document !== "undefined") {
      document.cookie = "auth_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    }
    if (typeof fetch !== "undefined") {
      try {
        fetch("/api/v1/auth/session-sync", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ clear: true })
        }).catch(() => {});
      } catch (_) {}
    }
  },

  getCurrentUser() {
    try {
      const u = localStorage.getItem("auth_user");
      return u ? JSON.parse(u) : null;
    } catch {
      return null;
    }
  },

  isAuthenticated() {
    return !!this.getToken();
  },

  async request(endpoint, options = {}) {
    // Default timeout for API calls (ms)
    const DEFAULT_TIMEOUT_MS = 20000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

    const url = `${API_BASE_URL}${endpoint}`;
    const headers = options.headers || {};

    // Auto-attach Bearer token if present
    const token = this.getToken();
    if (token && !headers["Authorization"]) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    options.headers = headers;
    options.signal = controller.signal;

    try {
      const response = await fetch(url, options);
      clearTimeout(timeoutId);

      // Handle session expiration
      if (response.status === 401) {
        this.clearToken();
        if (typeof window !== "undefined" && !window.location.pathname.includes("/login") && !window.location.pathname.includes("/register") && window.location.pathname !== "/") {
          const nextUrl = encodeURIComponent(window.location.pathname + window.location.search);
          window.location.href = `/login?expired=1&next=${nextUrl}`;
        }
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || "Your session has expired. Please log in again.");
      }

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        let message = errData.detail || errData.error || `Request failed with status ${response.status}`;
        if (Array.isArray(message)) {
          // Pydantic validation errors
          message = message.map((m) => m.msg || JSON.stringify(m)).join(", ");
        }
        throw new Error(message);
      }

      return await response.json();
    } catch (err) {
      if (err.name === "AbortError") {
        throw new Error("Request timed out after 20 seconds. Please try again later.");
      }
      if (err.message.includes("Failed to fetch") || err.name === "TypeError") {
        throw new Error("Unable to connect to AI Civic Guardian backend service. Please ensure the server is running.");
      }
      throw err;
    }
  },

  async fetch(endpoint, options = {}) {
    return await this.request(endpoint, options);
  },

  // Auth Endpoints
  async register(name, email, password, preferred_language = "en") {
    return await this.request("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        name,
        email,
        password,
        preferred_language,
        role: "CITIZEN",
      }),
    });
  },

  async login(email, password) {
    const data = await this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    this.setToken(data.access_token, data.user);
    return data;
  },

  async getMe() {
    return await this.request("/auth/me", { method: "GET" });
  },

  async updateMe(payload) {
    return await this.request("/auth/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  logout() {
    this.clearToken();
    window.location.href = "/login";
  },

  // Complaint Endpoints
  async createComplaint(payload) {
    return await this.request("/api/v1/complaints", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async uploadEvidence(complaintId, file) {
    const formData = new FormData();
    formData.append("file", file);

    return await this.request(`/api/v1/complaints/${encodeURIComponent(complaintId)}/evidence`, {
      method: "POST",
      body: formData,
    });
  },

  async listComplaints() {
    return await this.request("/api/v1/complaints", { method: "GET" });
  },

  async getComplaint(complaintId) {
    return await this.request(`/api/v1/complaints/${encodeURIComponent(complaintId)}`, {
      method: "GET",
    });
  },

  async classifyText(description, language = "en") {
    return await this.request("/api/v1/complaints/classify-text", {
      method: "POST",
      body: JSON.stringify({ description, language }),
    });
  },

  async searchLocation(query) {
    return await this.request(`/api/v1/complaints/search-location?q=${encodeURIComponent(query)}`, {
      method: "GET",
    });
  },

  async reverseGeocode(latitude, longitude) {
    return await this.request(`/api/v1/complaints/reverse-geocode?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`, {
      method: "GET",
    });
  },


  // Admin Dataset Endpoints
  async listDatasets(skip = 0, limit = 50) {
    return await this.request(`/api/v1/admin/datasets?skip=${skip}&limit=${limit}`, {
      method: "GET",
    });
  },

  async getDataset(datasetVersion) {
    return await this.request(`/api/v1/admin/datasets/${encodeURIComponent(datasetVersion)}`, {
      method: "GET",
    });
  },

  async uploadDataset(formData) {
    return await this.request("/api/v1/admin/datasets", {
      method: "POST",
      body: formData,
    });
  },

  async validateDataset(datasetVersion) {
    return await this.request(`/api/v1/admin/datasets/${encodeURIComponent(datasetVersion)}/validate`, {
      method: "POST",
    });
  },

  async getDatasetReport(datasetVersion) {
    return await this.request(`/api/v1/admin/datasets/${encodeURIComponent(datasetVersion)}/report`, {
      method: "GET",
    });
  },

  async getDatasetSources() {
    return await this.request("/api/v1/admin/dataset-sources", { method: "GET" });
  },

  // Admin Model Management Endpoints
  async getHardwareInfo() {
    return await this.request("/api/v1/admin/models/hardware", { method: "GET" });
  },

  async listModels(skip = 0, limit = 50, statusFilter = null) {
    let url = `/api/v1/admin/models?skip=${skip}&limit=${limit}`;
    if (statusFilter) url += `&status_filter=${encodeURIComponent(statusFilter)}`;
    return await this.request(url, { method: "GET" });
  },

  async getActiveModel() {
    return await this.request("/api/v1/admin/models/active", { method: "GET" });
  },

  async getModel(modelVersion) {
    return await this.request(`/api/v1/admin/models/${encodeURIComponent(modelVersion)}`, { method: "GET" });
  },

  async getModelStatus(modelVersion) {
    return await this.request(`/api/v1/admin/models/${encodeURIComponent(modelVersion)}/status`, { method: "GET" });
  },

  async getModelMetrics(modelVersion) {
    return await this.request(`/api/v1/admin/models/${encodeURIComponent(modelVersion)}/metrics`, { method: "GET" });
  },

  async startTraining(payload) {
    return await this.request("/api/v1/admin/models/train", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async activateModel(modelVersion) {
    return await this.request(`/api/v1/admin/models/${encodeURIComponent(modelVersion)}/activate`, {
      method: "POST",
    });
  },

  // AI Inference Endpoint
  async runAIInference(imageFile, confThreshold = 0.25, iouThreshold = 0.45) {
    const formData = new FormData();
    formData.append("file", imageFile);

    return await this.request(
      `/api/v1/ai/inference?confidence_threshold=${confThreshold}&iou_threshold=${iouThreshold}`,
      {
        method: "POST",
        body: formData,
      }
    );
  },

  // Isolated AI Demo Inference Endpoint (Local Testing)
  async runAIDemoInference(imageFile, confThreshold = 0.25, iouThreshold = 0.45) {
    const formData = new FormData();
    formData.append("file", imageFile);

    return await this.request(
      `/api/v1/ai/demo-inference?confidence_threshold=${confThreshold}&iou_threshold=${iouThreshold}&enable_demo=true`,
      {
        method: "POST",
        body: formData,
      }
    );
  },

  // Duplicate Complaint Check Endpoint
  async checkDuplicateComplaint(payload) {
    return await this.request("/api/v1/complaints/check-duplicate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // Coimbatore Boundary & Location Validation
  async getCoimbatoreBoundary() {
    return await this.request("/api/v1/complaints/boundary", { method: "GET" });
  },

  async validateLocation(lat, lon) {
    return await this.request("/api/v1/complaints/validate-location", {
      method: "POST",
      body: JSON.stringify({ latitude: lat, longitude: lon }),
    });
  },

  // Officer Workflow Endpoints
  async getOfficerDashboard() {
    return await this.request("/api/v1/officer/dashboard", { method: "GET" });
  },

  async listOfficerComplaints(params = {}) {
    const qs = new URLSearchParams();
    if (params.status) qs.append("status", params.status);
    if (params.severity) qs.append("severity", params.severity);
    if (params.issue_type) qs.append("issue_type", params.issue_type);
    if (params.search) qs.append("search", params.search);
    if (params.date_from) qs.append("date_from", params.date_from);
    if (params.date_to) qs.append("date_to", params.date_to);
    if (params.page) qs.append("page", params.page);
    if (params.page_size) qs.append("page_size", params.page_size);

    const queryStr = qs.toString() ? `?${qs.toString()}` : "";
    return await this.request(`/api/v1/officer/complaints${queryStr}`, { method: "GET" });
  },

  async getOfficerComplaint(complaintId) {
    return await this.request(`/api/v1/officer/complaints/${encodeURIComponent(complaintId)}`, {
      method: "GET",
    });
  },

  async updateOfficerComplaintStatus(complaintId, status, note = null) {
    return await this.request(`/api/v1/officer/complaints/${encodeURIComponent(complaintId)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, note }),
    });
  },

  async addOfficerNote(complaintId, note) {
    return await this.request(`/api/v1/officer/complaints/${encodeURIComponent(complaintId)}/notes`, {
      method: "POST",
      body: JSON.stringify({ note }),
    });
  },

  async resolveOfficerComplaint(complaintId, resolutionNote) {
    return await this.request(`/api/v1/officer/complaints/${encodeURIComponent(complaintId)}/resolution`, {
      method: "POST",
      body: JSON.stringify({ resolution_note: resolutionNote }),
    });
  },

  async uploadResolutionEvidence(complaintId, file) {
    const formData = new FormData();
    formData.append("file", file);

    return await this.request(`/api/v1/officer/complaints/${encodeURIComponent(complaintId)}/resolution-evidence`, {
      method: "POST",
      body: formData,
    });
  },

  async runResolutionVerification(complaintId) {
    return await this.request(`/api/v1/officer/complaints/${encodeURIComponent(complaintId)}/resolution/verify`, {
      method: "POST",
    });
  },

  async getResolutionVerification(complaintId) {
    return await this.request(`/api/v1/officer/complaints/${encodeURIComponent(complaintId)}/resolution/verification`, {
      method: "GET",
    });
  },

  async reviewResolutionVerification(complaintId, decision, reviewNotes) {
    return await this.request(`/api/v1/officer/complaints/${encodeURIComponent(complaintId)}/resolution/review`, {
      method: "POST",
      body: JSON.stringify({ decision, review_notes: reviewNotes }),
    });
  },

  // Blockchain Audit Trail Endpoint
  async getBlockchainRecords(complaintId) {
    return await this.request(`/api/v1/blockchain/complaints/${encodeURIComponent(complaintId)}`, {
      method: "GET",
    });
  },
};

// Expose globally
window.ApiClient = ApiClient;


