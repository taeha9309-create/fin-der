import { useCallback, useEffect, useState } from "react";
import { listReports } from "../api/client.js";
import ErrorState from "../components/ErrorState.jsx";

export default function ThreatIntelPage() {
  const [reports, setReports] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    listReports("CONFIRMED_PHISHING")
      .then(setReports)
      .catch(() => setError("Threat Intelligence 목록을 불러오지 못했습니다."));
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

  if (!reports) {
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
      <h1 className="page-title">Threat Intelligence</h1>
      <p className="subtitle">관리자가 피싱으로 확정한 URL 목록입니다. 아래 URL은 절대 접속하지 마세요.</p>

      {reports.length === 0 ? (
        <p className="empty-text">아직 확정된 피싱 URL이 없습니다.</p>
      ) : (
        <ul className="threat-intel-list">
          {reports.map((report) => (
            <li key={report.id} className="panel-card">
              <div className="threat-item-header">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 9v4m0 4h.01M10.3 3.86 1.8 18a1.5 1.5 0 0 0 1.3 2.25h17.8a1.5 1.5 0 0 0 1.3-2.25L13.7 3.86a1.5 1.5 0 0 0-2.6 0Z" />
                </svg>
                <span className="analyzed-url mono">{report.url}</span>
                {report.reportCount > 1 && <span className="mismatch-badge">제보 {report.reportCount}건</span>}
              </div>
              {report.reason && <p className="body-muted" style={{ whiteSpace: "pre-line" }}>{report.reason}</p>}
              <p className="admin-date mono">확정일 {formatDate(report.createdAt)}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function formatDate(iso) {
  if (!iso) return "-";
  return iso.replace("T", " ").slice(0, 19);
}
