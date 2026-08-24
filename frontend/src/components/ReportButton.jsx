import { useState } from "react";
import { submitReport } from "../api/client.js";

const QUICK_REASONS = [
  "금융기관 로그인 화면 사칭",
  "정부지원금·정책자금 사칭",
  "개인정보·계좌정보 입력 유도",
  "공식 도메인과 불일치",
];

export default function ReportButton({ url }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function appendReason(text) {
    setReason((prev) => (prev ? `${prev}\n${text}` : text));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await submitReport(url, reason);
      setSubmitted(true);
    } catch {
      setError("제보 접수에 실패했습니다. 다시 시도해주세요.");
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return <p className="report-success">제보가 접수되었습니다. 감사합니다.</p>;
  }

  if (!open) {
    return (
      <button className="btn btn-outline" onClick={() => setOpen(true)}>
        이 URL 제보하기
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="report-form">
      <div className="report-quick-reasons">
        {QUICK_REASONS.map((text) => (
          <button
            key={text}
            type="button"
            className="report-chip"
            onClick={() => appendReason(text)}
          >
            {text}
          </button>
        ))}
      </div>
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="제보 사유를 입력해주세요 (선택, 위 버튼으로 빠르게 추가 가능)"
        rows={3}
      />
      {error && <p className="error-text">{error}</p>}
      <div className="report-form-actions">
        <button type="submit" disabled={submitting} className="btn btn-primary">
          {submitting ? "제출 중..." : "제출"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>
          취소
        </button>
      </div>
    </form>
  );
}
