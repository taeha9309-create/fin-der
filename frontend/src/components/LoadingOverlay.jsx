import { useEffect, useState } from "react";

const PIPELINE_STEPS = [
  "1차 URL 분석 (XGBoost)",
  "웹페이지 수집 (Sandbox)",
  "페이지 위험요소 분석",
  "최종 결과 생성",
];

export default function LoadingOverlay({ active, label = "AI가 URL을 분석하고 있습니다…" }) {
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    if (!active) {
      setActiveStep(0);
      return;
    }
    const timer = setInterval(() => {
      setActiveStep((i) => (i + 1) % PIPELINE_STEPS.length);
    }, 1100);
    return () => clearInterval(timer);
  }, [active]);

  if (!active) return null;

  return (
    <div className="loading-wrap">
      <div className="spinner" />
      <div className="loading-title">{label}</div>
      <div className="pipeline">
        {PIPELINE_STEPS.map((step, i) => (
          <div key={step} className={"pstep" + (i === activeStep ? " active" : "")}>
            <span className="pdot" />
            {step}
          </div>
        ))}
      </div>
    </div>
  );
}
