import { useEffect, useState } from "react";
import { listReports, updateReportStatus } from "../api/client.js";

const STATUS_LABEL = {
  PENDING: "검토 대기",
  CONFIRMED_PHISHING: "피싱 확정",
  FALSE_POSITIVE: "오탐",
};

export default function AdminPage() {
  const [reports, setReports] = useState(null);
  const [error, setError] = useState("");
  const [updatingId, setUpdatingId] = useState(null);

  useEffect(() => {
    loadReports();
  }, []);

  function loadReports() {
    listReports()
      .then(setReports)
      .catch(() => setError("제보 목록을 불러오지 못했습니다."));
  }

  async function handleUpdate(id, status) {
    setUpdatingId(id);
    try {
      const updated = await updateReportStatus(id, status);
      setReports((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch {
      setError("상태 변경에 실패했습니다.");
    } finally {
      setUpdatingId(null);
    }
  }

  if (error) return <div className="page">{error}</div>;
  if (!reports) return <div className="page">불러오는 중...</div>;

  return (
    <div className="page admin-page">
      <h1>제보 관리자 Dashboard</h1>
      <p className="subtitle">사용자 제보를 확인하고 피싱 여부를 확정합니다.</p>

      {reports.length === 0 && <p>접수된 제보가 없습니다.</p>}

      <ul className="admin-list">
        {reports.map((report) => (
          <li key={report.id} className={`admin-item admin-status-${report.status?.toLowerCase()}`}>
            <div className="admin-item-header">
              <span className="admin-url">{report.url}</span>
              <span className="admin-status-badge">{STATUS_LABEL[report.status] || report.status}</span>
            </div>
            {report.reason && <p className="admin-reason">{report.reason}</p>}
            <p className="admin-date">{formatDate(report.createdAt)}</p>

            <div className="admin-actions">
              <button
                className="btn btn-danger"
                disabled={updatingId === report.id || report.status === "CONFIRMED_PHISHING"}
                onClick={() => handleUpdate(report.id, "CONFIRMED_PHISHING")}
              >
                피싱 확정
              </button>
              <button
                className="btn btn-ghost"
                disabled={updatingId === report.id || report.status === "FALSE_POSITIVE"}
                onClick={() => handleUpdate(report.id, "FALSE_POSITIVE")}
              >
                오탐 처리
              </button>
              {report.status !== "PENDING" && (
                <button
                  className="btn btn-outline"
                  disabled={updatingId === report.id}
                  onClick={() => handleUpdate(report.id, "PENDING")}
                >
                  대기로 되돌리기
                </button>
              )}
            </div>
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
