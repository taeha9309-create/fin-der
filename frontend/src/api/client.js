import axios from "axios";

const api = axios.create({
  baseURL: "/api",
});

const ADMIN_TOKEN_KEY = "leveragy_admin_token";

export function getAdminToken() {
  return sessionStorage.getItem(ADMIN_TOKEN_KEY);
}

function setAdminToken(token) {
  sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export function clearAdminToken() {
  sessionStorage.removeItem(ADMIN_TOKEN_KEY);
}

function authHeaders() {
  const token = getAdminToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function analyzeUrl(url) {
  // backend(오케스트레이터) -> ml-service -> (필요시) sandbox -> multimodal -> db-api 저장까지 거침
  return api.post("/v1/url-analysis", { url }).then((res) => res.data);
}

export function getAnalysis(id) {
  return api.get(`/analyze/${id}`).then((res) => res.data);
}

export function listAnalyses() {
  return api.get("/analyze").then((res) => res.data);
}

export function submitReport(url, reason, analysisId) {
  return api.post("/reports", { url, reason, analysisId }).then((res) => res.data);
}

export function listReports(status) {
  return api
    .get("/reports", { params: status ? { status } : {}, headers: authHeaders() })
    .then((res) => res.data);
}

export function updateReportStatus(id, status) {
  return api.patch(`/reports/${id}`, { status }, { headers: authHeaders() }).then((res) => res.data);
}

export async function adminLogin(username, password) {
  const { data } = await api.post("/admin/login", { username, password });
  setAdminToken(data.token);
  return data;
}

export function adminLogout() {
  return api
    .post("/admin/logout", {}, { headers: authHeaders() })
    .catch(() => {})
    .finally(clearAdminToken);
}
