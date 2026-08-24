import { Component } from "react";

// 렌더링 중 예상 못한 에러(예: 백엔드 응답 형태가 바뀌어서 화면이 하얗게 깨지는 경우)가
// 나도 전체 앱이 빈 화면이 되지 않도록 잡아준다.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error("Unhandled render error:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="page">
          <div className="error-state">
            <span className="error-state-icon" aria-hidden="true">
              ⚠
            </span>
            <p>예상치 못한 오류가 발생했습니다. 새로고침해주세요.</p>
            <button className="btn btn-outline" onClick={() => window.location.reload()}>
              새로고침
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
