import axios from "axios";

const api = axios.create({
  baseURL: "/api",
});

export function analyzeUrl(url) {
  // backend(오케스트레이터) -> ml-service -> (필요시) sandbox -> db-api 저장까지 거침
  return api.post("/v1/url-analysis", { url }).then((res) => res.data);
}

export function getAnalysis(id) {
  return api.get(`/analyze/${id}`).then((res) => res.data);
}

export function submitReport(url, reason) {
  return api.post("/reports", { url, reason }).then((res) => res.data);
}
