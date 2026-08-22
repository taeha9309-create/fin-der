import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeUrl } from "../api/client.js";
import LoadingOverlay from "../components/LoadingOverlay.jsx";

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
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page url-input-page">
      <h1>의심스러운 URL을 검사해보세요</h1>
      <p className="subtitle">금융기관·정부기관 사칭 여부를 AI가 분석합니다.</p>
      <form onSubmit={handleSubmit} className="url-form">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com"
          className="url-input"
        />
        <button type="submit" disabled={loading} className="btn btn-primary">
          {loading ? "분석 중..." : "검사하기"}
        </button>
      </form>
      {error && <p className="error-text">{error}</p>}
      {loading && <LoadingOverlay />}
    </div>
  );
}
