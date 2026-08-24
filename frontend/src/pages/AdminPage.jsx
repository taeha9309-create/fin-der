import { useCallback, useEffect, useMemo, useState } from "react";
import { listReports, updateReportStatus } from "../api/client.js";
import ErrorState from "../components/ErrorState.jsx";

const STATUS_LABEL = {
  PENDING: "검토 대기",
  CONFIRMED_PHISHING: "피싱 확정",
  FALSE_POSITIVE: "오탐",
};

const FILTER_TABS = [
  { key: "ALL", label: "전체" },
  { key: "PENDING", label: "검토 대기" },
  { key: "CONFIRMED_PHISHING", label: "피싱 확정" },
  { key: "FALSE_POSITIVE", label: "오탐" },
];

export default function AdminPage() {
  const [reports, setReports] = useState(null);
  const [error, setError] = useState("");
  const [updatingId, setUpdatingId] = useState(null);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [search, setSearch] = useState("");

  const load = useCallback(() => {
    setError("");
    listReports()
      .then(setReports)
      .catch(() => setError("제보 목록을 불러오지 못했습니다."));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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

  const filteredReports = useMemo(() => {
    if (!reports) return [];
    const keyword = search.trim().toLowerCase();
    return reports.filter((report) => {
      const matchesStatus = statusFilter === "ALL" || report.status === statusFilter;
      const matchesSearch = !keyword || report.url?.toLowerCase().includes(keyword);
      return matchesStatus && matchesSearch;
    });
  }, [reports, statusFilter, search]);

  if (error) return <div className="page"><ErrorState message={error} onRetry={load} /></div>;
  if (!reports) return <div className="page">불러오는 중...</div>;

  return (
    <div className="page admin-page">
      <h1>제보 관리자 Dashboard</h1>
      <p className="subtitle">사용자 제보를 확인하고 피싱 여부를 확정합니다.</p>

      <div className="admin-toolbar">
        <div className="admin-filter-tabs">
          {FILTER_TABS.map((tab) => (
            <button
              key={tab.key}
              className={`admin-filter-tab ${statusFilter === tab.key ? "active" : ""}`}
              onClick={() => setStatusFilter(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="URL 검색"
          className="admin-search"
        />
      </div>

      {reports.length === 0 && <p className="empty-text">접수된 제보가 없습니다.</p>}
      {reports.length > 0 && filteredReports.length === 0 && (
        <p className="empty-text">조건에 맞는 제보가 없습니다.</p>
      )}

      <ul className="admin-list">
        {filteredReports.map((report) => (
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
