import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getAnalysis } from "../api/client.js";
import RiskGauge from "../components/RiskGauge.jsx";
import LoadingOverlay from "../components/LoadingOverlay.jsx";

const POLL_INTERVAL_MS = 1200;

const VERDICT_META = {
  PHISHING: { label: "피싱 사이트로 의심됩니다", tone: "danger" },
  SUSPICIOUS: { label: "의심스러운 사이트입니다", tone: "warning" },
  NORMAL: { label: "안전한 사이트로 보입니다", tone: "safe" },
};

export default function ResultPage() {
  const { id } = useParams();
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState("");
  const [shared, setShared] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let intervalId = null;

    function fetchOnce() {
      getAnalysis(id)
        .then((data) => {
          if (cancelled) return;
          setAnalysis(data);
          if (data.processingStatus !== "PROCESSING" && intervalId) {
            clearInterval(intervalId);
          }
        })
        .catch(() => {
          if (!cancelled) setError("분석 결과를 불러오지 못했습니다.");
          if (intervalId) clearInterval(intervalId);
        });
    }

    fetchOnce();
    intervalId = setInterval(fetchOnce, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [id]);

  async function handleShare() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setShared(true);
      setTimeout(() => setShared(false), 2000);
    } catch {
      // clipboard access unavailable, silently ignore
    }
  }

  if (error) {
    return (
      <div className="page">
        <p className="error-text">{error}</p>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="page">
        <div className="loading-wrap">
          <div className="spinner" />
          <div className="loading-title">분석 결과를 불러오는 중입니다…</div>
        </div>
      </div>
    );
  }

  if (analysis.processingStatus === "PROCESSING") {
    return (
      <div className="page">
        <LoadingOverlay active label="AI가 URL을 분석하고 있습니다…" />
      </div>
    );
  }

  if (analysis.processingStatus === "FAILED") {
    return (
      <div className="page">
        <p className="error-text">분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.</p>
      </div>
    );
  }

  const riskScore = analysis.riskScore ?? 0;
  const pageAnalysis = safeParsePageAnalysis(analysis.multimodalResult);
  const collectionSummary = safeParseCollectionSummary(analysis.multimodalResult);
  const blockedNotice = buildBlockedNotice(pageAnalysis, collectionSummary);

  if (riskScore <= 20) {
    return (
      <div className="page result-page">
        <div className="safe-result">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="safe-result-icon">
            <path d="M20 6 9 17l-5-5" />
          </svg>
          <h1 className="safe-result-title">안전한 사이트입니다</h1>
          <a className="analyzed-url mono" href={analysis.url} target="_blank" rel="noopener noreferrer">
            {analysis.url}
          </a>
          <div className="meta-row mono">
            <span>분석 시간 {formatDate(analysis.createdAt)}</span>
            <span>분석 ID {analysis.id}</span>
          </div>
          {blockedNotice && (
            <div className="risk-banner tone-danger">
              <div className="risk-banner-left">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 9v4m0 4h.01M10.3 3.86 1.8 18a1.5 1.5 0 0 0 1.3 2.25h17.8a1.5 1.5 0 0 0 1.3-2.25L13.7 3.86a1.5 1.5 0 0 0-2.6 0Z" />
                </svg>
                <div className="risk-banner-title">{blockedNotice}</div>
              </div>
            </div>
          )}
          <div className="action-row">
            <a className="btn btn-ghost" href={analysis.url} target="_blank" rel="noopener noreferrer">
              사이트로 이동하기
            </a>
            <Link to={`/report/${analysis.id}`} className="btn btn-danger">
              <span className="btn-icon" aria-hidden="true">🚩</span>이 사이트 제보하기
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const xaiReasons = safeParseReasons(analysis.xaiResult);
  const collectionStatusMessage = buildCollectionStatusMessage(collectionSummary);
  const verdict = analysis.finalResult || "NORMAL";
  const meta = VERDICT_META[verdict] || VERDICT_META.NORMAL;
  const riskSummary = buildRiskSummary(pageAnalysis);
  const reasons = pageAnalysis?.reasons?.length ? pageAnalysis.reasons : xaiReasons;

  return (
    <div className="page result-page">
      <div className="result-header">
        <div>
          <div className="field-label">분석한 URL</div>
          {verdict === "PHISHING" ? (
            <span className="analyzed-url mono">{analysis.url}</span>
          ) : (
            <a className="analyzed-url mono" href={analysis.url} target="_blank" rel="noopener noreferrer">
              {analysis.url}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 4h6v6M20 4 10 14M9 5H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-3" />
              </svg>
            </a>
          )}
          <div className="meta-row mono">
            <span>분석 시간 {formatDate(analysis.createdAt)}</span>
            <span>분석 ID {analysis.id}</span>
          </div>
        </div>
        <button className="btn btn-ghost btn-small" onClick={handleShare}>
          {shared ? "링크 복사됨" : "결과 공유"}
        </button>
      </div>

      <div className={"risk-banner tone-" + meta.tone}>
        <div className="risk-banner-left">
          {meta.tone === "safe" ? (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 6 9 17l-5-5" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 9v4m0 4h.01M10.3 3.86 1.8 18a1.5 1.5 0 0 0 1.3 2.25h17.8a1.5 1.5 0 0 0 1.3-2.25L13.7 3.86a1.5 1.5 0 0 0-2.6 0Z" />
            </svg>
          )}
          <div className="risk-banner-title">
            {meta.label}
            <span className={"verdict-badge tone-" + meta.tone}>{verdict}</span>
          </div>
        </div>
        <RiskGauge score={riskScore} tone={meta.tone} />
      </div>

      {blockedNotice && (
        <div className="risk-banner tone-danger">
          <div className="risk-banner-left">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 9v4m0 4h.01M10.3 3.86 1.8 18a1.5 1.5 0 0 0 1.3 2.25h17.8a1.5 1.5 0 0 0 1.3-2.25L13.7 3.86a1.5 1.5 0 0 0-2.6 0Z" />
            </svg>
            <div className="risk-banner-title">{blockedNotice}</div>
          </div>
        </div>
      )}

      <div className="cols2">
        <div className="panel-card">
          <h4>
            <span className="owner-tag">2번</span> 사이트 미리보기 (분석 당시 화면)
          </h4>
          {analysis.screenshotData ? (
            <div className="site-preview">
              <img src={analysis.screenshotData} alt="분석 당시 페이지 스크린샷" className="fp-screenshot" />
              <div className="preview-caption">* 분석 당시 페이지를 캡처한 이미지입니다.</div>
            </div>
          ) : pageAnalysis ? (
            <div className="site-preview">
              <div className="fp-bar">🏦 {pageAnalysis.impersonation?.brand || "로그인 페이지"}</div>
              <div className="fp-body">
                <div className="fp-title">로그인</div>
                <div className="fp-field">아이디를 입력하세요</div>
                {pageAnalysis.credentialIntent?.types?.includes("PASSWORD") && (
                  <div className="fp-field">비밀번호를 입력하세요</div>
                )}
                {pageAnalysis.credentialIntent?.types?.includes("OTP") && (
                  <div className="fp-field">OTP 인증번호를 입력하세요</div>
                )}
                <div className="fp-btn">로그인</div>
                <div className="fp-footer">
                  <span>인증센터</span>
                  <span>보안센터</span>
                  <span>고객센터</span>
                </div>
              </div>
              <div className="preview-caption">* 실제 스크린샷은 Sandbox 연동 후 제공되는 예시 화면입니다.</div>
            </div>
          ) : (
            <p className="body-muted">{collectionStatusMessage}</p>
          )}
        </div>

        <div className="panel-card">
          <h4>AI 분석 근거 (요약)</h4>
          {reasons.length ? (
            <ol className="ai-reasons">
              {reasons.map((reason, idx) => (
                <li key={idx}>{reason}</li>
              ))}
            </ol>
          ) : (
            <p className="body-muted">표시할 판단 근거가 없습니다.</p>
          )}
        </div>
      </div>

      <div className="cols3">
        <div className="panel-card">
          <h4>
            <span className="owner-tag">2번</span> DOM 분석 결과
          </h4>
          {pageAnalysis?.domSummary ? (
            <>
              <div className="fact-row">
                <RiskIcon type="form" />
                <span>
                  <b>
                    입력 필드 (총{" "}
                    {pageAnalysis.domSummary.passwordFields + pageAnalysis.domSummary.otpFields + pageAnalysis.domSummary.textFields}
                    개)
                  </b>
                  <br />
                  비밀번호 입력 {pageAnalysis.domSummary.passwordFields}개 · OTP 입력 {pageAnalysis.domSummary.otpFields}개 ·
                  일반 텍스트 입력 {pageAnalysis.domSummary.textFields}개
                </span>
              </div>
              <div className="fact-row">
                <RiskIcon type="lock" />
                <span>
                  <b>Form 정보 ({pageAnalysis.domSummary.formCount}개)</b>
                  <br />
                  Method: {pageAnalysis.domSummary.formMethod || "-"} · Action: {pageAnalysis.domSummary.formAction || "-"}
                </span>
              </div>
              <div className="fact-row">
                <RiskIcon type="link" />
                <span>
                  <b>
                    외부 연결 ({pageAnalysis.domSummary.externalDomainLinks + pageAnalysis.domSummary.externalContactLinks}개)
                  </b>
                  <br />
                  외부 도메인 링크 {pageAnalysis.domSummary.externalDomainLinks}개 · 상담 링크{" "}
                  {pageAnalysis.domSummary.externalContactLinks}개
                </span>
              </div>
            </>
          ) : (
            <p className="body-muted">{collectionStatusMessage}</p>
          )}
        </div>

        <div className="panel-card">
          <h4>
            <span className="owner-tag">3번</span> 공식기관 비교 결과
          </h4>
          {pageAnalysis?.impersonation?.brand ? (
            <>
              <div className="domain-line">
                <span className="k">감지된 기관명</span>
                <span className="v">{pageAnalysis.impersonation.brand}</span>
              </div>
              <div className="domain-line">
                <span className="k">현재 도메인</span>
                <span className="v mono">{pageAnalysis.domainAnalysis?.currentDomain || "-"}</span>
              </div>
              <div className="domain-arrow">↓</div>
              <div className="domain-line">
                <span className="k">공식 도메인</span>
                <span className="v mono">{pageAnalysis.domainAnalysis?.officialDomains?.join(", ") || "-"}</span>
                {pageAnalysis.domainAnalysis?.domainBrandMismatch && <span className="mismatch-badge">불일치</span>}
              </div>
              {pageAnalysis.domainAnalysis?.domainBrandMismatch && (
                <p className="domain-note">공식 도메인과 일치하지 않아 사칭 가능성이 매우 높습니다.</p>
              )}
            </>
          ) : pageAnalysis ? (
            <p className="body-muted">기관 사칭 정황이 발견되지 않았습니다.</p>
          ) : (
            <p className="body-muted">접속 도메인과 공식 도메인 비교 결과가 페이지 분석 AI 연동 후 표시됩니다.</p>
          )}
        </div>

        <div className="panel-card">
          <h4>주요 위험 요약</h4>
          {riskSummary.length ? (
            <div className="risk-list">
              {riskSummary.map((item) => (
                <div key={item.title} className="risk-item">
                  <div className="ri-main">
                    <RiskIcon type={item.icon} />
                    <div className="ri-text">
                      <b>{item.title}</b>
                      <small>{item.desc}</small>
                    </div>
                  </div>
                  <span className={"sev sev-" + item.severity}>{item.severity === "danger" ? "위험" : "주의"}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="body-muted">
              {pageAnalysis ? "감지된 위험 신호가 없습니다." : collectionStatusMessage}
            </p>
          )}
        </div>
      </div>

      <div className="action-row">
        <Link to={`/report/${analysis.id}`} className="btn btn-danger">
          🚩 이 사이트 제보하기
        </Link>
        <Link
          to={`/report/${analysis.id}`}
          state={{ prefill: "이 사이트는 안전한 것 같은데 오탐으로 보입니다." }}
          className="btn btn-ghost"
        >
          URL이 안전한가요? 오탐 제보하기
        </Link>
      </div>
    </div>
  );
}

function RiskIcon({ type }) {
  const paths = {
    domain: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18M12 3c2.5 2.5 3.5 5.7 3.5 9s-1 6.5-3.5 9c-2.5-2.5-3.5-5.7-3.5-9s1-6.5 3.5-9Z" />
      </>
    ),
    lock: (
      <>
        <rect x="5" y="11" width="14" height="9" rx="2" />
        <path d="M8 11V7a4 4 0 0 1 8 0v4" />
      </>
    ),
    form: (
      <>
        <path d="M4 4h16v16H4z" />
        <path d="M8 9h8M8 13h5" />
      </>
    ),
    link: <path d="M14 4h6v6M20 4 10 14M9 5H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-3" />,
    alert: <path d="M12 9v4m0 4h.01M10.3 3.86 1.8 18a1.5 1.5 0 0 0 1.3 2.25h17.8a1.5 1.5 0 0 0 1.3-2.25L13.7 3.86a1.5 1.5 0 0 0-2.6 0Z" />,
    shield: <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3Z" />,
    money: <path d="M12 6v12M9 9.5c0-1.5 1.3-2.5 3-2.5s3 1 3 2.5-1.3 2-3 2-3 1-3 2.5 1.3 2.5 3 2.5 3-1 3-2.5" />,
    download: (
      <>
        <path d="M12 3v12" />
        <path d="m7 10 5 5 5-5" />
        <path d="M5 21h14" />
      </>
    ),
  };
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      {paths[type] || paths.link}
    </svg>
  );
}

function buildRiskSummary(pageAnalysis) {
  if (!pageAnalysis) return [];
  const items = [];
  const brand = pageAnalysis.impersonation?.brand;
  const credentialTypes = pageAnalysis.credentialIntent?.types || [];
  const signals = pageAnalysis.detectedSignals || [];

  if (signals.includes("SECURITY_VENDOR_BLOCKED")) {
    items.push({
      icon: "shield",
      title: "보안 업체 차단 이력",
      desc: "Cloudflare·Google Safe Browsing 등 보안 업체가 이미 피싱으로 차단한 사이트입니다.",
      severity: "danger",
    });
  }
  if (pageAnalysis.domainAnalysis?.domainBrandMismatch) {
    items.push({
      icon: "domain",
      title: "비공식 도메인 사용",
      desc: `공식 ${brand || "기관"} 도메인이 아닙니다.`,
      severity: "danger",
    });
  }
  if (credentialTypes.includes("PASSWORD")) {
    items.push({ icon: "lock", title: "비밀번호 입력 요구", desc: "사용자 비밀번호 입력 필드 발견", severity: "danger" });
  }
  if (credentialTypes.includes("OTP")) {
    items.push({ icon: "lock", title: "OTP 입력 요구", desc: "일회용 인증번호 입력 필드 발견", severity: "danger" });
  }
  if (credentialTypes.includes("RESIDENT_NUMBER")) {
    items.push({ icon: "lock", title: "주민등록번호 입력 요구", desc: "주민등록번호 입력 필드 발견", severity: "danger" });
  }
  if (credentialTypes.includes("ACCOUNT_NUMBER")) {
    items.push({ icon: "lock", title: "계좌번호 입력 요구", desc: "계좌번호 입력 필드 발견", severity: "danger" });
  }
  if (credentialTypes.includes("CARD_NUMBER")) {
    items.push({ icon: "lock", title: "카드번호 입력 요구", desc: "카드번호 입력 필드 발견", severity: "danger" });
  }
  if (credentialTypes.includes("PIN")) {
    items.push({ icon: "lock", title: "PIN 입력 요구", desc: "PIN 번호 입력 필드 발견", severity: "danger" });
  }
  if (credentialTypes.includes("PHONE")) {
    items.push({ icon: "lock", title: "휴대폰번호 입력 요구", desc: "휴대폰번호 입력 필드 발견", severity: "warning" });
  }
  if (signals.includes("POST_FORM")) {
    items.push({ icon: "form", title: "정보 전송 가능 Form", desc: "POST 방식으로 정보 전송 가능", severity: "danger" });
  }
  if (signals.includes("EXTERNAL_FORM_ACTION")) {
    items.push({ icon: "form", title: "입력정보 외부 전송", desc: "입력한 정보가 현재 사이트와 다른 외부 도메인으로 전송될 수 있습니다.", severity: "danger" });
  }
  if (signals.includes("EXTERNAL_CONTACT")) {
    items.push({ icon: "link", title: "외부 링크·상담 유도", desc: "외부 상담 채널로 연결되는 링크 발견", severity: "warning" });
  }
  if (signals.includes("DOWNLOAD_REQUEST")) {
    items.push({ icon: "download", title: "파일 다운로드 유도", desc: "프로그램 또는 파일 다운로드를 유도하는 정황이 확인되었습니다.", severity: "warning" });
  }
  if (signals.includes("ACCOUNT_SUSPENSION_MESSAGE")) {
    items.push({ icon: "alert", title: "계정 정지 경고 문구", desc: "계정 또는 계좌 이용 제한을 경고하는 문구가 확인되었습니다.", severity: "danger" });
  }
  if (signals.includes("URGENCY_MESSAGE")) {
    items.push({ icon: "alert", title: "긴급성 유도 문구", desc: "즉시 행동을 요구하는 긴급성 문구가 확인되었습니다.", severity: "warning" });
  }
  if (signals.includes("BENEFIT_LURE")) {
    items.push({ icon: "money", title: "금전적 혜택 유도", desc: "지원금·환급금·대출 등 금전적 혜택을 강조하는 문구가 확인되었습니다.", severity: "warning" });
  }
  if (signals.includes("FINANCIAL_ACTION_REQUEST")) {
    items.push({ icon: "money", title: "금융 행동 요구", desc: "송금·이체·계좌정보 입력 등 금융 행동을 요구합니다.", severity: "danger" });
  }
  return items;
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

function safeParsePageAnalysis(multimodalResult) {
  try {
    const parsed = JSON.parse(multimodalResult);
    return parsed && typeof parsed.pageRiskScore === "number" ? parsed : null;
  } catch {
    return null;
  }
}

function safeParseCollectionSummary(multimodalResult) {
  try {
    const parsed = JSON.parse(multimodalResult);
    return parsed && typeof parsed.collected === "boolean" ? parsed : null;
  } catch {
    return null;
  }
}

function buildCollectionStatusMessage(summary) {
  if (!summary) return "Sandbox 페이지 수집 결과가 없습니다.";
  if (summary.note === "not_required") {
    return "정밀 분석 설정을 켜기 전에 생성된 결과입니다. URL을 다시 분석해주세요.";
  }
  if (summary.collected === false) {
    return summary.note
      ? `Sandbox가 페이지를 수집하지 못했습니다. URL AI 결과만 표시합니다. (${summary.note})`
      : "Sandbox가 페이지를 수집하지 못했습니다. URL AI 결과만 표시합니다.";
  }
  return "Sandbox 페이지 수집은 완료됐지만 표시할 정밀 분석 결과가 없습니다.";
}

// 점수·등급 계산과 무관하게, "이미 차단/접속 불가"라는 사실 자체를 알려준다 -
// 위험도가 낮게 나온 경우에도 이 배너는 그와 별개로 뜬다.
function buildBlockedNotice(pageAnalysis, collectionSummary) {
  if (pageAnalysis?.detectedSignals?.includes("SECURITY_VENDOR_BLOCKED")) {
    return "보안 업체(Cloudflare, Google Safe Browsing 등)가 이미 이 사이트를 피싱으로 신고·차단한 상태입니다.";
  }
  if (collectionSummary?.collected === false && collectionSummary.note !== "not_required") {
    return "현재 이 사이트에 정상적으로 접속할 수 없습니다. 이미 차단되었거나 서비스가 중단된 피싱 사이트일 수 있습니다.";
  }
  return null;
}

function formatDate(iso) {
  if (!iso) return "-";
  return iso.replace("T", " ").slice(0, 19);
}
