import { Routes, Route, Link } from "react-router-dom";
import UrlInputPage from "./pages/UrlInputPage.jsx";
import ResultPage from "./pages/ResultPage.jsx";
import ReportPage from "./pages/ReportPage.jsx";
import HistoryPage from "./pages/HistoryPage.jsx";
import ThreatIntelPage from "./pages/ThreatIntelPage.jsx";
import AdminPage from "./pages/AdminPage.jsx";
import NotFoundPage from "./pages/NotFoundPage.jsx";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <Link to="/" className="brand">
          <span className="mark">L</span>
          <span className="brand-text">
            <span className="name">Leveragy</span>
            <span className="tag">금융 피싱 탐지 플랫폼</span>
          </span>
        </Link>
        <nav className="app-nav">
          <Link to="/history">분석 이력</Link>
          <Link to="/threat-intel">Threat Intelligence</Link>
          <Link to="/admin">관리자</Link>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<UrlInputPage />} />
          <Route path="/result/:id" element={<ResultPage />} />
          <Route path="/report/:id" element={<ReportPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/threat-intel" element={<ThreatIntelPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  );
}
