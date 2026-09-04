import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeUrl } from "../api/client.js";
import LoadingOverlay from "../components/LoadingOverlay.jsx";

const EXAMPLE_URLS = [
  "https://example.com/kb-login-security/verify?otp=1004",
  "https://example.com/verify",
  "https://gov-login.com",
];

export default function UrlInputPage() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    setError("");
    try {
      const result = await analyzeUrl(url.trim());
      navigate(`/result/${result.id}`);
    } catch (err) {
      setError("분석 요청에 실패했습니다. 백엔드 서버 상태를 확인해주세요.");
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="page">
        <LoadingOverlay active />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="narrow">
        <p className="headline">
          의심되는 금융 링크,
          <br />
          AI가 안전한지 분석해 드립니다
        </p>
        <p className="sub">URL을 입력하면 AI가 피싱 여부와 위험 근거를 분석합니다.</p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com"
            className="url-field"
          />
          <button type="submit" className="btn btn-primary btn-block">
            분석하기
          </button>
        </form>
        {error && <p className="error-text">{error}</p>}

        <div className="example-row">
          {EXAMPLE_URLS.map((example) => (
            <button key={example} type="button" className="example-pill" onClick={() => setUrl(example)}>
              {shortLabel(example)}
            </button>
          ))}
        </div>

        <div className="checklist">
          <div className="ci">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
              <path d="M20 6 9 17l-5-5" />
            </svg>
            1차 머신러닝 : URL 구조·도메인 위험도<span className="owner-tag">1번</span>
          </div>
          <div className="ci">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
              <path d="M20 6 9 17l-5-5" />
            </svg>
            2차 샌드박스 : 실제 페이지 접속·수집<span className="owner-tag">2번</span>
          </div>
          <div className="ci">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
              <path d="M20 6 9 17l-5-5" />
            </svg>
            기관 비교 : 공식 도메인과 대조<span className="owner-tag">3번</span>
          </div>
          <div className="ci">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
              <path d="M20 6 9 17l-5-5" />
            </svg>
            결과 저장·표시 및 제보 접수<span className="owner-tag">4번</span>
          </div>
        </div>

        <p className="footnote">입력하신 URL은 분석 결과와 함께 위험 정보 데이터베이스에 저장됩니다.</p>
      </div>
    </div>
  );
}

function shortLabel(url) {
  return url.replace(/^https?:\/\//, "");
}
