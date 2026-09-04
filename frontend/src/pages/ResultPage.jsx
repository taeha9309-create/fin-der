import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getAnalysis } from "../api/client.js";
import WarningModal from "../components/WarningModal.jsx";
import ReportButton from "../components/ReportButton.jsx";
import RiskGauge from "../components/RiskGauge.jsx";
import ErrorState from "../components/ErrorState.jsx";

export default function ResultPage() {
  const { id } = useParams();
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState("");
  const [blocked, setBlocked] = useState(true);

  const loadAnalysis = useCallback(() => {
    setError("");
    setAnalysis(null);
    getAnalysis(id)
      .then((data) => {
        setAnalysis(data);
        setBlocked(data.finalResult === "PHISHING");
      })
      .catch(() => setError("분석 결과를 불러오지 못했습니다."));
  }, [id]);

  useEffect(() => {
    loadAnalysis();
  }, [loadAnalysis]);

  if (error) return <div className="page"><ErrorState message={error} onRetry={loadAnalysis} /></div>;
  if (!analysis) return <div className="page">불러오는 중...</div>;

  const reasons = safeParseReasons(analysis.xaiResult);
  const pageAnalysis = safeParseMultimodal(analysis.multimodalResult);

  return (
    <div className="page result-page">
      {blocked && (
        <WarningModal
          analysis={analysis}
          onProceed={() => setBlocked(false)}
          onReport={() => setBlocked(false)}
        />
      )}

      <h1>분석 결과</h1>
      <p className="result-url">{analysis.url}</p>

      <div className={`result-badge result-${analysis.finalResult?.toLowerCase()}`}>
        {analysis.finalResult}
      </div>

      <div className="risk-score">
        <span>위험도</span>
        <RiskGauge score={analysis.riskScore} />
      </div>

      <section className="xai-section">
        <h2>판단 근거 (XAI)</h2>
        {reasons.length === 0 ? (
          <p className="empty-text">판단 근거 정보가 없습니다.</p>
        ) : (
          <ul>
            {reasons.map((reason, idx) => (
              <li key={idx}>{formatReason(reason)}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="page-analysis-section">
        <h2>페이지 심층 분석</h2>
        {pageAnalysis?.kind === "full" ? (
          <PageAnalysisDetail data={pageAnalysis.data} />
        ) : pageAnalysis?.kind === "summary" && pageAnalysis.data.collected ? (
          <p className="empty-text">
            2차 정밀 분석 결과를 가져오지 못했습니다{pageAnalysis.data.note ? `: ${pageAnalysis.data.note}` : "."}
          </p>
        ) : (
          <p className="empty-text">1차 위험도가 낮아 2차 정밀 분석(Sandbox·페이지 분석)이 실행되지 않았습니다.</p>
        )}
      </section>

      <ReportButton url={analysis.url} analysisId={analysis.id} />
    </div>
  );
}

function PageAnalysisDetail({ data }) {
  const officialDomains = data.domainAnalysis?.officialDomains || [];
  return (
    <div className="page-analysis-detail">
      {data.impersonation?.detected && (
        <p>
          <strong>사칭 의심 기관:</strong> {data.impersonation.brand}
          {data.impersonation.category ? ` (${data.impersonation.category})` : ""}
        </p>
      )}
      {data.domainAnalysis?.domainBrandMismatch && (
        <p className="mismatch-note">
          현재 도메인 <code>{data.domainAnalysis.currentDomain}</code>이(가) 공식 도메인
          {officialDomains.length ? ` (${officialDomains.join(", ")})` : ""}과 일치하지 않습니다.
        </p>
      )}
      {data.credentialIntent?.detected && (
        <p>
          <strong>민감정보 입력 요구:</strong> {(data.credentialIntent.types || []).join(", ") || "감지됨"}
        </p>
      )}
      {data.detectedSignals?.length > 0 && (
        <div className="signal-badges">
          {data.detectedSignals.map((signal) => (
            <span key={signal} className="signal-badge">
              {signal}
            </span>
          ))}
        </div>
      )}
      {data.reasons?.length > 0 && (
        <ul>
          {data.reasons.map((reason, idx) => (
            <li key={idx}>{reason}</li>
          ))}
        </ul>
      )}
      {typeof data.confidence === "number" && (
        <p className="confidence-note">AI 신뢰도 {Math.round(data.confidence * 100)}%</p>
      )}
    </div>
  );
}

// multimodalResult는 backend가 저장한 JSON 문자열로, 두 가지 모양 중 하나다:
// - 2차 정밀 분석이 실행된 경우: multimodal-service의 AnalyzeResponse
//   (impersonation/credentialIntent/domainAnalysis/detectedSignals/reasons/confidence)
// - 실행되지 않았거나 실패한 경우: { collected, htmlSizeBytes, screenshotSizeBytes, note } 요약
function safeParseMultimodal(multimodalResult) {
  try {
    const parsed = JSON.parse(multimodalResult);
    if (!parsed || typeof parsed !== "object") return null;
    if (parsed.impersonation || parsed.domainAnalysis || parsed.detectedSignals) {
      return { kind: "full", data: parsed };
    }
    if ("collected" in parsed) {
      return { kind: "summary", data: parsed };
    }
    return null;
  } catch {
    return null;
  }
}

function safeParseReasons(xaiResult) {
  try {
    const parsed = JSON.parse(xaiResult);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

// db-api 목업의 문자열 배열과 ML 서비스의 SHAP 근거 객체를 모두 표시한다.
function formatReason(reason) {
  if (typeof reason === "string") return reason;
  if (reason && typeof reason === "object" && reason.reason) {
    const arrow = reason.direction === "RISK_UP" ? "↑" : "↓";
    const contribution = Number.isFinite(reason.contribution)
      ? ` (${reason.contribution.toFixed(4)})`
      : "";
    return `${reason.reason} ${arrow}${contribution}`;
  }
  return JSON.stringify(reason);
}
