import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.FRONTEND_PORT) || 3000,
    proxy: {
      // 분석 요청은 backend(오케스트레이터)가 ml-service/sandbox까지 거쳐 처리
      "/api/v1": {
        target: `http://localhost:${process.env.BACKEND_PORT || 8080}`,
        changeOrigin: true,
      },
      // 결과 조회(id)와 제보는 db-api를 직접 호출
      "/api/analyze": {
        target: `http://localhost:${process.env.DB_API_PORT || 8081}`,
        changeOrigin: true,
      },
      "/api/reports": {
        target: `http://localhost:${process.env.DB_API_PORT || 8081}`,
        changeOrigin: true,
      },
    },
  },
});
