import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getAnalysis } from "../api/client.js";
import WarningModal from "../components/WarningModal.jsx";
import ReportButton from "../components/ReportButton.jsx";

export default function ResultPage() {
  const { id } = useParams();
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState("");
  const [blocked, setBlocked] = useState(true);

  useEffect(() => {
    getAnalysis(id)
      .then((data) => {
        setAnalysis(data);
        setBlocked(data.finalResult === "PHISHING");
      })
      .catch(() => setError("분석 결과를 불러오지 못했습니다."));
  }, [id]);

  if (error) return <div className="page">{error}</div>;
  if (!analysis) return <div className="page">불러오는 중...</div>;

  const reasons = safeParseReasons(analysis.xaiResult);

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
        <strong>{analysis.riskScore} / 100</strong>
      </div>

      <section className="xai-section">
        <h2>판단 근거 (XAI)</h2>
        <ul>
          {reasons.map((reason, idx) => (
            <li key={idx}>{formatReason(reason)}</li>
          ))}
        </ul>
      </section>

      <ReportButton url={analysis.url} />
    </div>
  );
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
