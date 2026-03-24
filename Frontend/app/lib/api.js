// frontend/lib/api.js

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("lawgic_token");
}

function getUser() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("lawgic_user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function isLoggedIn() {
  return !!(getToken() && getUser());
}

function clearSession() {
  localStorage.removeItem("lawgic_token");
  localStorage.removeItem("lawgic_user");
}

function getWsBaseUrl() {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  return base.replace(/^http/, "ws");
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

export { getToken, getUser, isLoggedIn, clearSession, getWsBaseUrl };

export async function login(email, password) {
  const formData = new URLSearchParams();
  formData.append("username", email);
  formData.append("password", password);

  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData.toString(),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Login failed");
  return data;
}

export const loginUser = login;

export async function registerUser(formData) {
  const res = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: formData.name,
      email: formData.email,
      password: formData.password,
      phone_num: formData.phone,
      role: "client",
    }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "User registration failed");
  return data;
}

export async function registerLawyer(formData) {
  const res = await fetch(`${API_BASE_URL}/auth/register-lawyer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: formData.fullName,
      email: formData.email,
      password: formData.password,
      phone_num: formData.phone,
      specialization: formData.specialization,
      bio_data: formData.bio,
      years_of_experience: Number(formData.experience),
      office_address: formData.officeAddress,
      consultation_fee: Number(formData.hourlyRate),
    }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Lawyer registration failed");
  return data;
}

export function getMyProfile() {
  return apiFetch("/users/me");
}

export function getMyStats() {
  return apiFetch("/users/me/stats");
}

export function getMyLawyerProfile() {
  return apiFetch("/lawyers/me");
}

export function searchLawyers(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return apiFetch(`/lawyers/search${qs ? "?" + qs : ""}`);
}

export function getLawyerById(id) {
  return apiFetch(`/lawyers/${id}`);
}

export function getLawyerReviews(lawyerId) {
  return apiFetch(`/reviews/lawyer/${lawyerId}`);
}

export function getMyCases(statusFilter) {
  const qs = statusFilter ? `?status_filter=${statusFilter}` : "";
  return apiFetch(`/cases/my${qs}`);
}

export function getCaseById(caseId) {
  return apiFetch(`/cases/${caseId}`);
}

export function createCase(caseData) {
  return apiFetch("/cases/", { method: "POST", body: JSON.stringify(caseData) });
}

export function inviteLawyerToCase(caseId, lawyerId) {
  return apiFetch(`/cases/${caseId}/invite`, {
    method: "POST",
    body: JSON.stringify([lawyerId]),
  });
}

export function updateCaseStatus(caseId, status) {
  return apiFetch(`/cases/${caseId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function getMyRequests(statusFilter) {
  const qs = statusFilter ? `?status_filter=${statusFilter}` : "";
  return apiFetch(`/cases/requests/my${qs}`);
}

export function getClientRequests() {
  return apiFetch("/cases/client-requests/my");
}

export function respondToRequest(requestId, status) {
  return apiFetch(`/cases/requests/${requestId}/respond`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

export function getMyAppointments(filters = {}) {
  const qs = new URLSearchParams(
    Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== undefined && v !== null && v !== ""))
  ).toString();
  return apiFetch(`/appointments/my${qs ? "?" + qs : ""}`);
}

export function createAppointment(lawyerId, modeOfComm, scheduledAt, notes) {
  return apiFetch("/appointments/", {
    method: "POST",
    body: JSON.stringify({
      lawyer_id: lawyerId,
      mode_of_comm: modeOfComm,
      scheduled_at: scheduledAt,
      notes: notes || null,
    }),
  });
}

export function updateAppointmentStatus(apptId, status) {
  return apiFetch(`/appointments/${apptId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function getMyConversations(skip = 0, limit = 20) {
  return apiFetch(`/conversations/?skip=${skip}&limit=${limit}`);
}

export function getOrCreateConversation(otherUserId, title, initialMessage) {
  return apiFetch("/conversations/", {
    method: "POST",
    body: JSON.stringify({
      other_user_id: otherUserId,
      title: title || null,
      initial_message: initialMessage || null,
    }),
  });
}

export function getConversationMessages(convId, skip = 0, limit = 50) {
  return apiFetch(`/conversations/${convId}/messages?skip=${skip}&limit=${limit}`);
}

export function sendConversationMessage(convId, content) {
  return apiFetch(`/conversations/${convId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export function markConversationRead(convId) {
  return apiFetch(`/conversations/${convId}/read`, { method: "PATCH" });
}

export function getAISessions() {
  return apiFetch("/ai/sessions");
}
