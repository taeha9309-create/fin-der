const http = require("node:http");
const { URL } = require("node:url");

const PORT = Number.parseInt(process.env.PORT || "8001", 10);

function respond(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(body));
}

function analyze(rawUrl) {
  const url = new URL(rawUrl);
  const value = rawUrl.toLowerCase();
  const signals = [];
  if (rawUrl.length > 100) signals.push("LONG_URL");
  if (/\d+\.\d+\.\d+\.\d+/.test(url.hostname)) signals.push("IP_HOST");
  if (url.hostname.includes("xn--")) signals.push("PUNYCODE_HOST");
  if (/login|verify|secure|bank|card|loan|kb|shinhan|woori|hana|toss/.test(value)) signals.push("FINANCIAL_OR_AUTH_TERM");
  if ((url.hostname.match(/\./g) || []).length >= 3) signals.push("DEEP_SUBDOMAIN");
  const score = Math.min(signals.length * 20, 80);
  return {
    url: rawUrl,
    stage: "URL_RULE_MOCK",
    serviceMode: "MOCK",
    riskProbability: score / 100,
    riskScore: score,
    label: score >= 70 ? "PHISHING" : score >= 40 ? "SUSPICIOUS" : "NORMAL",
    requiresDeepAnalysis: true,
    xaiReasons: signals.map((reason) => ({ reason, direction: "RISK_UP" })),
    modelVersion: "mock-1.0",
  };
}

http.createServer((req, res) => {
  if (req.method === "GET" && req.url === "/health") return respond(res, 200, { status: "UP", service: "url-ai-mock" });
  if (req.method !== "POST" || req.url !== "/v1/analyze") return respond(res, 404, { code: "NOT_FOUND" });
  const chunks = [];
  req.on("data", (chunk) => chunks.push(chunk));
  req.on("end", () => {
    try {
      const body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
      respond(res, 200, analyze(body.url));
    } catch {
      respond(res, 400, { code: "INVALID_REQUEST", message: "올바른 URL이 필요합니다." });
    }
  });
}).listen(PORT, "0.0.0.0", () => console.log(JSON.stringify({ event: "url_ai_mock_started", port: PORT })));
