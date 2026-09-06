import { riskLevel } from "../riskLevel.js";

export default function RiskGauge({ score, tone = "danger", size = 64 }) {
  const strokeWidth = 6;
  const r = (size - strokeWidth) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const offset = c * (1 - clamped / 100);
  const level = riskLevel(clamped);

  return (
    <div className="risk-gauge">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          className="gauge-track"
          strokeWidth={strokeWidth}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          className={`gauge-value tone-${tone}`}
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text x="50%" y="55%" textAnchor="middle" className="gauge-score">
          {level}
        </text>
      </svg>
      <div className="risk-score-label">위험도</div>
    </div>
  );
}
