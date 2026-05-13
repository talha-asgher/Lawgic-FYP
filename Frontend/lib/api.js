import { useAuthStore } from "../app/lib/authStore";

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

/** Seconds of leeway vs server clock / latency (matches typical JWT usage). */
const JWT_EXPIRY_SKEW_MS = 15_000;

/**
 * Returns true if JWT `exp` is at or before now (token should be treated as dead).
 * Does not verify signature — use with server validation via verifySession().
 */
export function isAccessTokenExpired(token) {
  if (!token || typeof token !== "string") return true;
  const parts = token.split(".");
  if (parts.length !== 3) return false;
  try {
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const pad = "=".repeat((4 - (b64.length % 4)) % 4);
    const payload = JSON.parse(atob(b64 + pad));
    if (payload.exp == null) return false;
    return payload.exp * 1000 <= Date.now() + JWT_EXPIRY_SKEW_MS;
  } catch {
    return false;
  }
}

/**
 * Confirms the bearer token with GET /auth/me. On 401/403 clears local session.
 * Does not redirect (for app startup). Returns { ok, user?, networkError? }.
 */
export async function verifySession() {
  if (typeof window === "undefined") return { ok: false, user: null };
  const token = localStorage.getItem("lawgic_token");
  if (!token) return { ok: false, user: null };

  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timeoutMs = 12_000;
  const timeoutId =
    controller &&
    typeof window !== "undefined" &&
    setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${BASE_URL}/auth/me`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      signal: controller?.signal,
    });

    if (res.status === 401 || res.status === 403) {
      clearSession();
      try {
        useAuthStore.getState().logout();
      } catch {
        /* */
      }
      return { ok: false, user: null, sessionInvalid: true };
    }

    if (!res.ok) {
      return { ok: false, user: null };
    }

    const data = await res.json();
    const user = {
      user_id: data.user_id,
      role: data.role,
      name: data.name,
      email: data.email,
    };
    setSession(token, user);
    return { ok: true, user };
  } catch (e) {
    if (e?.name === "AbortError") {
      return { ok: false, user: null, networkError: true };
    }
    return { ok: false, user: null, networkError: true };
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
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

function pathWithoutQuery(path) {
  const q = path.indexOf("?");
  return q === -1 ? path : path.slice(0, q);
}

function isPublicAuthRequestPath(path) {
  const p = pathWithoutQuery(path);
  return p === "/auth/login" || p.startsWith("/auth/register");
}

function redirectToLoginSessionExpired() {
  if (typeof window === "undefined") return;
  const next = encodeURIComponent(
    `${window.location.pathname}${window.location.search}`
  );
  window.location.assign(`/login?session=expired&next=${next}`);
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

  if (res.status === 401 && typeof window !== "undefined") {
    if (!isPublicAuthRequestPath(path)) {
      clearSession();
      try {
        useAuthStore.getState().logout();
      } catch {
        /* */
      }
      redirectToLoginSessionExpired();
      throw new Error("Session expired. Please sign in again.");
    }
  }

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

export async function createDocumentAnalysis(file, outputLanguage = "en") {
  const form = new FormData();
  form.append("file", file);
  form.append("output_language", outputLanguage);

  return api.postForm("/doc-analysis/", form);
}

export async function getDocumentAnalysis(analysisId) {
  return api.get(`/doc-analysis/${analysisId}`);
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
    outputLanguage = undefined,
    signal = undefined,
  } = {}
) {
  const body = {
    query,
    top_k_retrieval: topKRetrieval,
    top_k_context: topKContext,
  };
  if (outputLanguage !== undefined && outputLanguage !== null) {
    body.output_language = outputLanguage;
  }
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