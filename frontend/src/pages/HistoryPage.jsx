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

  if (error) return <div className="page"><ErrorState message={error} onRetry={load} /></div>;
  if (!analyses) return <div className="page">불러오는 중...</div>;

  return (
    <div className="page history-page">
      <h1>분석 이력</h1>
      <p className="subtitle">지금까지 검사한 URL과 결과를 다시 볼 수 있습니다.</p>

      {analyses.length === 0 ? (
        <p className="empty-text">아직 검사한 URL이 없습니다.</p>
      ) : (
        <ul className="history-list">
          {analyses.map((item) => (
            <li key={item.id} className="history-item">
              <Link to={`/result/${item.id}`} className="history-link">
                <span className="history-url">{item.url}</span>
                <span className={`result-badge result-${item.finalResult?.toLowerCase()}`}>
                  {item.finalResult}
                </span>
                <span className="history-score">{item.riskScore}/100</span>
                <span className="history-date">{formatDate(item.createdAt)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleString("ko-KR");
}
