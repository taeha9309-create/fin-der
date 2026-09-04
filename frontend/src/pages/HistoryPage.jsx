import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAnalyses } from "../api/client.js";
import ErrorState from "../components/ErrorState.jsx";

export default function HistoryPage() {
  const [analyses, setAnalyses] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    listAnalyses()
      .then(setAnalyses)
      .catch(() => setError("분석 이력을 불러오지 못했습니다."));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="page">
        <ErrorState message={error} onRetry={load} />
      </div>
    );
  }

  if (!analyses) {
    return (
      <div className="page">
        <div className="loading-wrap">
          <div className="spinner" />
          <div className="loading-title">불러오는 중…</div>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <h1 className="page-title">분석 이력</h1>
      <p className="subtitle">지금까지 검사한 URL과 결과를 다시 볼 수 있습니다.</p>

      {analyses.length === 0 ? (
        <p className="empty-text">아직 검사한 URL이 없습니다.</p>
      ) : (
        <ul className="history-list">
          {analyses.map((item) => (
            <li key={item.id} className="panel-card">
              <Link to={`/result/${item.id}`} className="history-link">
                <div className="history-main">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 4h6v6M20 4 10 14M9 5H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-3" />
                  </svg>
                  <div>
                    <div className="history-url mono">{item.url}</div>
                    <div className="history-date mono">{formatDate(item.createdAt)}</div>
                  </div>
                </div>
                <div className="history-meta">
                  {item.processingStatus === "PROCESSING" ? (
                    <span className="status-pill">분석 중</span>
                  ) : item.processingStatus === "FAILED" ? (
                    <span className="status-pill status-rejected">분석 실패</span>
                  ) : (
                    <>
                      <span className={"verdict-badge tone-" + toneOf(item.finalResult)}>{item.finalResult}</span>
                      <span className="history-score">{item.riskScore}/100</span>
                    </>
                  )}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function toneOf(verdict) {
  if (verdict === "PHISHING") return "danger";
  if (verdict === "SUSPICIOUS") return "warning";
  return "safe";
}

function formatDate(iso) {
  if (!iso) return "-";
  return iso.replace("T", " ").slice(0, 19);
}
