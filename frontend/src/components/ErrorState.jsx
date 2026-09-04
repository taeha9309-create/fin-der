export default function ErrorState({ message, onRetry }) {
  return (
    <div className="error-state">
      <span className="error-state-icon" aria-hidden="true">
        ⚠
      </span>
      <p>{message}</p>
      {onRetry && (
        <button className="btn btn-outline" onClick={onRetry}>
          다시 시도
        </button>
      )}
    </div>
  );
}
