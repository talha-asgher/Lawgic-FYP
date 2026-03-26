const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_BASE_URL = BASE_URL.replace(/^http:/, "ws:").replace(/^https:/, "wss:");

export function getWsBaseUrl() {
  return WS_BASE_URL;
}

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

async function parseResponse(res) {
  if (res.status === 204) return null;

  const contentType = res.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return res.json();
  }

  const text = await res.text();
  return text || null;
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData) && options.body && typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  const data = await parseResponse(res);

  if (!res.ok) {
    let detail = `Request failed: ${res.status}`;

    if (data && typeof data === "object") {
      detail = data.detail || data.message || JSON.stringify(data);
    } else if (typeof data === "string" && data.trim()) {
      detail = data;
    }

    throw new Error(detail);
  }

  return data;
}

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

export async function loginUser(email, password) {
  const body = new URLSearchParams({ username: email, password });

  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  const data = await parseResponse(res);

  if (!res.ok) {
    let detail = "Login failed";

    if (data && typeof data === "object") {
      detail = data.detail || data.message || detail;
    } else if (typeof data === "string" && data.trim()) {
      detail = data;
    }

    throw new Error(detail);
  }

  setSession(data.access_token, {
    user_id: data.user?.user_id ?? data.user_id,
    role: data.user?.role ?? data.role,
    name: data.user?.name ?? data.name,
    email: data.user?.email ?? data.email ?? email,
  });

  return data;
}

export async function registerUser(formData) {
  return api.post("/auth/register", {
    name: formData.name,
    email: formData.email,
    password: formData.password,
    phone_num: formData.phone,
    role: "client",
  });
}

export async function getMe() {
  return api.get("/auth/me");
}

export async function getMyProfile() {
  return api.get("/users/me");
}

export async function updateMyProfile(data) {
  return api.patch("/users/me", data);
}

export async function getMyStats() {
  return api.get("/users/me/stats");
}

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

export async function getLawyerReviews(lawyerId) {
  return api.get(`/reviews/lawyer/${lawyerId}`);
}

export async function createReview(lawyerId, stars, comment) {
  return api.post("/reviews/", { lawyer_id: lawyerId, stars, comment });
}

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

export async function inviteLawyerToCase(caseId, lawyerId) {
  return api.post(`/cases/${caseId}/invite`, [lawyerId]);
}

export async function getMyRequests(statusFilter = "pending") {
  return api.get("/cases/requests/my", { status_filter: statusFilter });
}

export async function getClientRequests() {
  return api.get("/cases/client-requests/my");
}

export async function respondToRequest(requestId, status) {
  return api.post(`/cases/requests/${requestId}/respond`, { status });
}

export async function getCaseMessages(caseId) {
  return api.get(`/cases/${caseId}/messages`);
}

export async function sendCaseMessage(caseId, content) {
  return api.post(`/cases/${caseId}/messages`, { content });
}

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

export async function getInstitutions(params = {}) {
  return api.get("/institutions/", params);
}

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

export async function createDocumentAnalysis(fileName, fileSize) {
  const params = new URLSearchParams({ file_name: fileName });
  if (fileSize) params.append("file_size", fileSize);

  const token = getToken();
  const res = await fetch(`${BASE_URL}/doc-analysis/?${params.toString()}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  const data = await parseResponse(res);

  if (!res.ok) {
    let detail = "Analysis failed";

    if (data && typeof data === "object") {
      detail = data.detail || data.message || detail;
    } else if (typeof data === "string" && data.trim()) {
      detail = data;
    }

    throw new Error(detail);
  }

  return data;
}

export async function askAI(question, language = "en", sessionId = null) {
  return api.post("/ai/ask", { question, language, session_id: sessionId });
}

export async function ragAsk(
  query,
  {
    actName = null,
    category = null,
    sectionNumber = null,
    topKRetrieval = 15,
    topKContext = 6,
    searchTables = null,
    searchForms = null,
    signal = undefined,
  } = {}
) {
  const body = {
    query,
    top_k_retrieval: topKRetrieval,
    top_k_context: topKContext,
  };
  if (actName != null) body.act_name = actName;
  if (category != null) body.category = category;
  if (sectionNumber != null) body.section_number = sectionNumber;
  if (searchTables !== null && searchTables !== undefined) body.search_tables = searchTables;
  if (searchForms !== null && searchForms !== undefined) body.search_forms = searchForms;
  return request("/rag/ask", {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
}

export async function getAIHistory(sessionId) {
  return api.get("/ai/history", sessionId ? { session_id: sessionId } : {});
}

export async function getAISessions() {
  return api.get("/ai/sessions");
}

export async function calculateInheritance(data) {
  return api.post("/inheritance/calculate", data);
}

export default api;