import { useEffect, useState } from "react";
import { listReports } from "../api/client.js";

export default function ThreatIntelPage() {
  const [reports, setReports] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    listReports("CONFIRMED_PHISHING")
      .then(setReports)
      .catch(() => setError("Threat Intelligence 목록을 불러오지 못했습니다."));
  }, []);

  if (error) return <div className="page">{error}</div>;
  if (!reports) return <div className="page">불러오는 중...</div>;

  return (
    <div className="page threat-intel-page">
      <h1>Threat Intelligence</h1>
      <p className="subtitle">
        관리자가 피싱으로 확정한 URL 목록입니다. 아래 URL은 절대 접속하지 마세요.
      </p>

      {reports.length === 0 && <p>아직 확정된 피싱 URL이 없습니다.</p>}

      <ul className="threat-intel-list">
        {reports.map((report) => (
          <li key={report.id} className="threat-intel-item">
            <span className="warning-url">{report.url}</span>
            {report.reason && <p className="admin-reason">{report.reason}</p>}
            <p className="admin-date">확정일: {formatDate(report.createdAt)}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleString("ko-KR");
}
