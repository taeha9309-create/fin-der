import { useEffect, useState } from "react";

// 백엔드가 진행률을 안 주기 때문에(단일 요청-응답), 실제 파이프라인 순서에
// 맞춰 일정 시간마다 문구만 바꿔준다. 진짜 진행률이 아니라 사용자가 기다리는
// 동안 뭘 하고 있는지 짐작할 수 있게 하는 용도.
const STEPS = [
  "URL 구조 분석 중 (XGBoost)...",
  "의심스러우면 격리 환경에서 페이지 확인 중 (Sandbox)...",
  "AI가 사칭 여부 판단 중 (Multimodal)...",
  "최종 위험도 계산 중...",
];

export default function LoadingOverlay() {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setStepIndex((prev) => Math.min(prev + 1, STEPS.length - 1));
    }, 1800);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="loading-overlay">
      <div className="loading-spinner" aria-hidden="true" />
      <p className="loading-text">{STEPS[stepIndex]}</p>
    </div>
  );
}
