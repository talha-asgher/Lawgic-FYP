/**
 * lib/api.js — Central API client for Lawgic frontend.
 *
 * All backend calls go through here.
 * Token is stored in localStorage under the key "lawgic_token".
 * User info (id, role, name) is stored under "lawgic_user".
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Token helpers ─────────────────────────────────────────────────────────────

export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("lawgic_token");
}

export function getUser() {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(localStorage.getItem("lawgic_user") || "null");
  } catch {
    return null;
  }
}

export function setSession(token, user) {
  localStorage.setItem("lawgic_token", token);
  localStorage.setItem("lawgic_user", JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem("lawgic_token");
  localStorage.removeItem("lawgic_user");
}

export function isLoggedIn() {
  return !!getToken();
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────

async function request(path, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Don't set Content-Type for FormData (browser sets it with boundary)
  if (!(options.body instanceof FormData) && options.body && typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    let detail = `Request failed: ${res.status}`;
    try {
      const err = await res.json();
      detail = err.detail || JSON.stringify(err);
    } catch {}
    throw new Error(detail);
  }

  // 204 No Content
  if (res.status === 204) return null;

  return res.json();
}

// Convenience methods
const api = {
  get: (path, params) => {
    const url = params
      ? `${path}?${new URLSearchParams(params).toString()}`
      : path;
    return request(url, { method: "GET" });
  },
  post: (path, body) =>
    request(path, { method: "POST", body: JSON.stringify(body) }),
  patch: (path, body) =>
    request(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: (path) => request(path, { method: "DELETE" }),
  postForm: (path, formData) =>
    request(path, { method: "POST", body: formData }),
};

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function loginUser(email, password) {
  // FastAPI OAuth2 expects application/x-www-form-urlencoded
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Login failed");
  }
  const data = await res.json();
  setSession(data.access_token, {
    user_id: data.user_id,
    role: data.role,
    name: data.name,
  });
  return data;
}

export async function registerUser(name, email, password, phone, role = "client") {
  return api.post("/auth/register", { name, email, password, phone_num: phone, role });
}

export async function getMe() {
  return api.get("/auth/me");
}

// ── Users ─────────────────────────────────────────────────────────────────────

export async function getMyProfile() {
  return api.get("/users/me");
}

export async function updateMyProfile(data) {
  return api.patch("/users/me", data);
}

export async function getMyStats() {
  return api.get("/users/me/stats");
}

// ── Lawyers ───────────────────────────────────────────────────────────────────

export async function searchLawyers(params = {}) {
  return api.get("/lawyers/search", params);
}

export async function getLawyerById(lawyerId) {
  return api.get(`/lawyers/${lawyerId}`);
}

export async function getMyLawyerProfile() {
  return api.get("/lawyers/me");
}

export async function upsertLawyerProfile(data) {
  return api.post("/lawyers/profile", data);
}

// ── Reviews ───────────────────────────────────────────────────────────────────

export async function getLawyerReviews(lawyerId) {
  return api.get(`/reviews/lawyer/${lawyerId}`);
}

export async function createReview(lawyerId, stars, comment) {
  return api.post("/reviews/", { lawyer_id: lawyerId, stars, comment });
}

// ── Cases ─────────────────────────────────────────────────────────────────────

export async function getMyCases(statusFilter) {
  const params = statusFilter ? { status_filter: statusFilter } : {};
  return api.get("/cases/my", params);
}

export async function createCase(data) {
  return api.post("/cases/", data);
}

export async function getCaseById(caseId) {
  return api.get(`/cases/${caseId}`);
}

export async function updateCaseStatus(caseId, status) {
  return api.patch(`/cases/${caseId}/status`, { status });
}

export async function inviteLawyersToCase(caseId, lawyerIds) {
  return api.post(`/cases/${caseId}/invite`, lawyerIds);
}

export async function getMyRequests(statusFilter = "pending") {
  return api.get("/cases/requests/my", { status_filter: statusFilter });
}

export async function respondToRequest(requestId, status) {
  return api.post(`/cases/requests/${requestId}/respond`, { status });
}

// ── Case Messages ─────────────────────────────────────────────────────────────

export async function getCaseMessages(caseId) {
  return api.get(`/cases/${caseId}/messages`);
}

export async function sendCaseMessage(caseId, content) {
  return api.post(`/cases/${caseId}/messages`, { content });
}

// ── Appointments ──────────────────────────────────────────────────────────────

export async function getMyAppointments(params = {}) {
  return api.get("/appointments/my", params);
}

export async function createAppointment(lawyerId, modeOfComm, scheduledAt, notes) {
  return api.post("/appointments/", {
    lawyer_id: lawyerId,
    mode_of_comm: modeOfComm,
    scheduled_at: scheduledAt,
    notes,
  });
}

export async function updateAppointmentStatus(apptId, status) {
  return api.patch(`/appointments/${apptId}/status`, { status });
}

// ── Conversations ─────────────────────────────────────────────────────────────

export async function getMyConversations() {
  return api.get("/conversations/");
}

export async function getOrCreateConversation(otherUserId, caseId, initialMessage) {
  return api.post("/conversations/", {
    other_user_id: otherUserId,
    case_id: caseId || null,
    initial_message: initialMessage || null,
  });
}

export async function getConversationMessages(convId) {
  return api.get(`/conversations/${convId}/messages`);
}

export async function sendConversationMessage(convId, content) {
  return api.post(`/conversations/${convId}/messages`, { content });
}

export async function markConversationRead(convId) {
  return api.patch(`/conversations/${convId}/read`);
}

// ── Institutions ──────────────────────────────────────────────────────────────

export async function getInstitutions(params = {}) {
  return api.get("/institutions/", params);
}

// ── Document Templates & Generation ──────────────────────────────────────────

export async function getDocumentTemplates(params = {}) {
  return api.get("/documents/templates", params);
}

export async function getDocumentTemplate(templateId) {
  return api.get(`/documents/templates/${templateId}`);
}

export async function generateDocument(templateId, title, inputData) {
  return api.post("/documents/generate", {
    template_id: templateId,
    title,
    input_data: inputData,
  });
}

export async function getMyDocuments() {
  return api.get("/documents/my");
}

// ── Document Analysis ─────────────────────────────────────────────────────────

export async function createDocumentAnalysis(fileName, fileSize) {
  const params = new URLSearchParams({ file_name: fileName });
  if (fileSize) params.append("file_size", fileSize);
  const token = getToken();
  const res = await fetch(`${BASE_URL}/doc-analysis/?${params}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Analysis failed");
  }
  return res.json();
}

// ── Ask AI ────────────────────────────────────────────────────────────────────

export async function askAI(question, language = "en", sessionId = null) {
  return api.post("/ai/ask", { question, language, session_id: sessionId });
}

export async function getAIHistory(sessionId) {
  return api.get("/ai/history", sessionId ? { session_id: sessionId } : {});
}

export async function getAISessions() {
  return api.get("/ai/sessions");
}

// ── Inheritance Calculator ─────────────────────────────────────────────────────

export async function calculateInheritance(data) {
  return api.post("/inheritance/calculate", data);
}

export default api;
