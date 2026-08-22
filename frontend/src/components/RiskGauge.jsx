const RADIUS = 45;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

// finalResult 판정 기준(70/40)과 맞춘 색상 구간
function riskColor(score) {
  if (score >= 70) return "var(--color-danger, #e63946)";
  if (score >= 40) return "var(--color-warning, #a67c00)";
  return "var(--color-safe, #2d6a4f)";
}

export default function RiskGauge({ score }) {
  const clamped = Math.max(0, Math.min(100, score ?? 0));
  const offset = CIRCUMFERENCE * (1 - clamped / 100);
  const color = riskColor(clamped);

  return (
    <div className="risk-gauge">
      <svg viewBox="0 0 100 100" className="risk-gauge-svg" role="img" aria-label={`위험도 ${clamped}/100`}>
        <circle cx="50" cy="50" r={RADIUS} className="risk-gauge-track" />
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          className="risk-gauge-fill"
          style={{
            stroke: color,
            strokeDasharray: CIRCUMFERENCE,
            strokeDashoffset: offset,
          }}
        />
      </svg>
      <div className="risk-gauge-label">
        <strong style={{ color }}>{clamped}</strong>
        <span>/ 100</span>
      </div>
    </div>
  );
}
