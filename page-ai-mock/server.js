const http = require("node:http");

const PORT = Number.parseInt(process.env.PORT || "8002", 10);
const MAX_BODY_BYTES = 30 * 1024 * 1024;
const ENABLE_TEST_FAILURES = process.env.ENABLE_TEST_FAILURES === "true";
const TEST_FAILURE_MARKER = "finder_page_ai_fail=1";

function sendJson(response, status, body) {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(body));
}

function analyze(input) {
  const text = `${input.title || ""} ${input.text || ""}`.toLowerCase();
  const inputTypes = (input.inputs || []).map((item) => String(item.type || "").toLowerCase());
  const credentialTypes = [];
  const signals = [];

  if (inputTypes.includes("password")) {
    credentialTypes.push("PASSWORD");
    signals.push("PASSWORD_FIELD");
  }
  if (inputTypes.some((type) => type.includes("otp")) || /otp|인증번호/.test(text)) {
    credentialTypes.push("OTP");
    signals.push("OTP_FIELD");
  }
  if ((input.forms || []).some((form) => form.method === "POST")) {
    signals.push("POST_FORM");
  }
  if (/긴급|즉시|정지|차단|지원금|저금리|대환대출/.test(text)) {
    signals.push("SOCIAL_ENGINEERING_LANGUAGE");
  }
  if (input.network?.downloadDetected) {
    signals.push("DOWNLOAD_REQUEST");
  }

  const uniqueSignals = [...new Set(signals)];
  const score = Math.min(uniqueSignals.length * 20, 80);
  const verdict = score >= 60 ? "SUSPICIOUS" : "UNKNOWN";

  return {
    analysisId: input.analysisId,
    serviceMode: "MOCK",
    pageRiskScore: score,
    verdict,
    impersonatedBrand: null,
    credentialIntent: credentialTypes.length > 0,
    credentialTypes: [...new Set(credentialTypes)],
    domainBrandMismatch: null,
    detectedSignals: uniqueSignals,
    reasons: uniqueSignals.map((signal) => `연동 테스트 신호: ${signal}`),
    confidence: 0.2,
  };
}

const server = http.createServer((request, response) => {
  if (request.method === "GET" && request.url === "/health") {
    return sendJson(response, 200, { status: "UP", service: "page-ai-mock" });
  }

  if (request.method !== "POST" || request.url !== "/analyze") {
    return sendJson(response, 404, { code: "NOT_FOUND", message: "요청 경로를 찾을 수 없습니다." });
  }

  let size = 0;
  const chunks = [];
  request.on("data", (chunk) => {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) {
      sendJson(response, 413, { code: "REQUEST_TOO_LARGE", message: "요청 크기가 제한을 초과했습니다." });
      request.destroy();
      return;
    }
    chunks.push(chunk);
  });
  request.on("end", () => {
    try {
      const input = JSON.parse(Buffer.concat(chunks).toString("utf8"));

      if (
        ENABLE_TEST_FAILURES &&
        String(input.requestedUrl || "").includes(TEST_FAILURE_MARKER)
      ) {
        return sendJson(response, 503, {
          code: "TEST_PAGE_AI_FAILURE",
          message: "테스트를 위해 페이지 AI 실패를 발생시켰습니다.",
        });
      }

      sendJson(response, 200, analyze(input));
    } catch {
      sendJson(response, 400, { code: "INVALID_JSON", message: "JSON 요청 형식이 올바르지 않습니다." });
    }
  });
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(JSON.stringify({ event: "page_ai_mock_started", port: PORT }));
});
