export function riskLevel(score) {
  if (score <= 20) return "하";
  if (score <= 60) return "중";
  return "상";
}
