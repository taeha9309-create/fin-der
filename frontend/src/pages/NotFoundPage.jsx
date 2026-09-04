import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="page not-found-page">
      <h1 className="page-title">404</h1>
      <p className="subtitle">요청하신 페이지를 찾을 수 없습니다.</p>
      <Link to="/" className="btn btn-primary">
        홈으로 돌아가기
      </Link>
    </div>
  );
}
