import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { getAnalysis, submitReport } from "../api/client.js";

const STEPS = ["정보 확인", "제출 중", "완료"];

const STATUS_LABEL = {
  PENDING: "검토 대기",
  CONFIRMED_PHISHING: "피싱 확정",
  FALSE_POSITIVE: "오탐",
};

const STATUS_CLASS = {
  PENDING: "",
  CONFIRMED_PHISHING: "status-confirmed",
  FALSE_POSITIVE: "status-rejected",
};

export default function ReportPage() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const [analysis, setAnalysis] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [stage, setStage] = useState("confirm"); // confirm | submitting | done
  const [note, setNote] = useState(location.state?.prefill || "");
  const [result, setResult] = useState(null);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    getAnalysis(id)
      .then(setAnalysis)
      .catch(() => setLoadError("분석 결과를 불러오지 못했습니다."));
  }, [id]);

  async function handleSubmit(e) {
    e.preventDefault();
    setStage("submitting");
    setSubmitError("");
    try {
      const saved = await submitReport(analysis.url, note.trim() || undefined, analysis.id);
      setResult(saved);
      setStage("done");
    } catch {
      setSubmitError("제보 접수에 실패했습니다. 잠시 후 다시 시도해주세요.");
      setStage("confirm");
    }
  }

  if (loadError) {
    return (
      <div className="page">
        <p className="error-text">{loadError}</p>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="page">
        <div className="loading-wrap">
          <div className="spinner" />
          <div className="loading-title">불러오는 중…</div>
        </div>
      </div>
    );
  }

  if (analysis.processingStatus === "PROCESSING") {
    return (
      <div className="page">
        <p className="body-muted">아직 분석이 진행 중입니다. 분석이 끝난 뒤 제보해주세요.</p>
        <Link to={`/result/${analysis.id}`} className="btn btn-ghost" style={{ marginTop: 10 }}>
          분석 결과로 돌아가기
        </Link>
      </div>
    );
  }

  const reasons = safeParseReasons(analysis.xaiResult);
  const verdict = analysis.finalResult || "NORMAL";
  const riskScore = analysis.riskScore ?? 0;
  const stepIndex = stage === "confirm" ? 0 : stage === "submitting" ? 1 : 2;

  return (
    <div className="page">
      <Link to={`/result/${analysis.id}`} className="link-btn" style={{ marginBottom: 14 }}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
          <path d="m15 18-6-6 6-6" />
        </svg>
        분석 결과로 돌아가기
      </Link>

      <div className="narrow">
        <div className="steps">
          {STEPS.map((label, i) => (
            <span key={label} className={"step" + (i === stepIndex ? " active" : i < stepIndex ? " done" : "")}>
              <span className="num">{i + 1}</span>
              {label}
            </span>
          ))}
        </div>

        {stage === "confirm" && (
          <form onSubmit={handleSubmit}>
            <div className="confirm-card">
              <div className="confirm-title">이 사이트를 제보하시겠습니까?</div>
              <div className="confirm-sub">분석 결과가 아래에 자동으로 입력됩니다.</div>
              <dl className="info">
                <dt>URL</dt>
                <dd className="mono">{analysis.url}</dd>
                <dt>최종 판정</dt>
                <dd>
                  <span className={"verdict-badge tone-" + toneOf(verdict)}>{verdict}</span> {riskScore}/100
                </dd>
                <dt>탐지 항목</dt>
                <dd>{reasons.length ? reasons.join(" · ") : "없음"}</dd>
              </dl>
            </div>
            <label className="field-label" htmlFor="report-note" style={{ display: "block", marginTop: 12 }}>
              추가 의견 (선택)
            </label>
            <textarea
              id="report-note"
              className="note"
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="해당 사이트에 대한 추가 정보나 경험을 남겨주세요."
              style={{ marginTop: 6 }}
            />
            {submitError && <p className="error-text">{submitError}</p>}
            <div className="privacy-note" style={{ marginTop: 10 }}>
              제보 정보는 Leveragy 위험 정보 DB에 저장되며, 관계 기관 검토 및 신고에 활용될 수 있습니다.
            </div>
            <div className="action-row" style={{ marginTop: 12 }}>
              <Link to={`/result/${analysis.id}`} className="btn btn-ghost">
                취소
              </Link>
              <button type="submit" className="btn btn-danger">
                제보하기
              </button>
            </div>
          </form>
        )}

        {stage === "submitting" && (
          <div className="loading-wrap">
            <div className="spinner" />
            <div className="loading-title">제보를 접수하는 중입니다…</div>
          </div>
        )}

        {stage === "done" && result && (
          <div>
            <div className="done-wrap">
              <div className="done-check">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
                  <path d="M20 6 9 17l-5-5" />
                </svg>
              </div>
              <div className="done-title">제보가 완료되었습니다</div>
              <div className="done-sub">Leveragy에 소중한 제보를 해주셔서 감사합니다.</div>
            </div>
            <dl className="info" style={{ marginTop: 14 }}>
              <dt>제보 번호</dt>
              <dd className="mono">REP-{result.id}</dd>
              <dt>접수 시간</dt>
              <dd className="mono">{formatDate(result.createdAt)}</dd>
              <dt>현재 상태</dt>
              <dd>
                <span className={"status-pill " + (STATUS_CLASS[result.status] || "")}>
                  {STATUS_LABEL[result.status] || result.status}
                </span>
              </dd>
              <dt>동일 URL 제보</dt>
              <dd>현재 총 {result.reportCount}건 (이번 제보 포함)</dd>
            </dl>
            <button className="btn btn-primary btn-block" style={{ marginTop: 14 }} onClick={() => navigate("/")}>
              새로운 URL 분석하기
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function toneOf(verdict) {
  if (verdict === "PHISHING") return "danger";
  if (verdict === "SUSPICIOUS") return "warning";
  return "safe";
}

function safeParseReasons(xaiResult) {
  try {
    const parsed = JSON.parse(xaiResult);
    if (!Array.isArray(parsed)) return [];
    // ml-service는 { feature, reason, contribution, direction } 형태의 SHAP 근거를 반환한다.
    return parsed.map((item) => (typeof item === "string" ? item : item?.reason ?? JSON.stringify(item)));
  } catch {
    return [];
  }
}

function formatDate(iso) {
  if (!iso) return "-";
  return iso.replace("T", " ").slice(0, 19);
}
