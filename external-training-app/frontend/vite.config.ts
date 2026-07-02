import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const backendProxyTarget = process.env.VITE_EXT_TRAINING_BACKEND_PROXY_TARGET ?? "http://localhost:8001";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5183,
    host: true, // 允许外部设备访问
    hmr: {
      host: "localhost", // HMR host 需要字符串，避免 TypeScript 构建失败
    },
    proxy: {
      "/api": {
        target: backendProxyTarget,
        changeOrigin: true,
      },
    },
  },
});
