import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  listReports,
  updateReportStatus,
  listAnalyses,
  adminLogin,
  adminLogout,
  getAdminToken,
  clearAdminToken,
} from "../api/client.js";
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
  const [token, setToken] = useState(getAdminToken());

  if (!token) {
    return <AdminLoginForm onLoggedIn={() => setToken(getAdminToken())} />;
  }

  return <AdminDashboard onSessionExpired={() => setToken(null)} />;
}

function AdminLoginForm({ onLoggedIn }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await adminLogin(username.trim(), password);
      onLoggedIn();
    } catch {
      setError("아이디 또는 비밀번호가 올바르지 않습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page">
      <h1>관리자 로그인</h1>
      <p className="subtitle">제보 관리자 Dashboard는 로그인 후 이용할 수 있습니다.</p>
      <form onSubmit={handleSubmit} className="url-form" style={{ flexDirection: "column", alignItems: "stretch" }}>
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="아이디"
          className="url-input"
          autoComplete="username"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="비밀번호"
          className="url-input"
          autoComplete="current-password"
        />
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? "확인 중..." : "로그인"}
        </button>
      </form>
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}

function AdminDashboard({ onSessionExpired }) {
  const [reports, setReports] = useState(null);
  const [analysesById, setAnalysesById] = useState({});
  const [error, setError] = useState("");
  const [updatingId, setUpdatingId] = useState(null);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [search, setSearch] = useState("");

  const load = useCallback(() => {
    setError("");
    Promise.all([listReports(), listAnalyses().catch(() => [])])
      .then(([reportList, analysisList]) => {
        setReports(reportList);
        setAnalysesById(Object.fromEntries(analysisList.map((a) => [a.id, a])));
      })
      .catch((err) => {
        if (err?.response?.status === 401) {
          clearAdminToken();
          onSessionExpired();
          return;
        }
        setError("제보 목록을 불러오지 못했습니다.");
      });
  }, [onSessionExpired]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleUpdate(id, status) {
    setUpdatingId(id);
    try {
      const updated = await updateReportStatus(id, status);
      setReports((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch (err) {
      if (err?.response?.status === 401) {
        clearAdminToken();
        onSessionExpired();
        return;
      }
      setError("상태 변경에 실패했습니다.");
    } finally {
      setUpdatingId(null);
    }
  }

  async function handleLogout() {
    await adminLogout();
    onSessionExpired();
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
      <div className="admin-toolbar">
        <div>
          <h1 style={{ margin: 0 }}>제보 관리자 Dashboard</h1>
          <p className="subtitle" style={{ marginBottom: 0 }}>
            사용자 제보를 확인하고 피싱 여부를 확정합니다.
          </p>
        </div>
        <button className="btn btn-ghost" onClick={handleLogout}>
          로그아웃
        </button>
      </div>

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
            {report.reportCount > 1 && (
              <p className="admin-reason" style={{ fontWeight: 600 }}>
                동일 URL 제보 {report.reportCount}건 통합됨
              </p>
            )}
            {report.reason && <p className="admin-reason" style={{ whiteSpace: "pre-line" }}>{report.reason}</p>}
            <p className="admin-date">{formatDate(report.createdAt)}</p>

            {report.analysisId && analysesById[report.analysisId] ? (
              <p className="admin-date">
                분석 결과: <strong>{analysesById[report.analysisId].finalResult}</strong> (
                {analysesById[report.analysisId].riskScore}/100) ·{" "}
                <Link to={`/result/${report.analysisId}`} target="_blank" rel="noopener noreferrer">
                  상세 보기 ↗
                </Link>
              </p>
            ) : report.analysisId ? (
              <p className="admin-date">연결된 분석을 찾을 수 없습니다 (ID {report.analysisId}).</p>
            ) : (
              <p className="admin-date">연결된 분석 이력이 없는 제보입니다.</p>
            )}

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
