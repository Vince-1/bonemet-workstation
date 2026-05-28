import { defineConfig } from "vite";

// Linux 上 inotify 上限较低时（ENOSPC），用轮询代替原生 watch
const usePolling = process.env.VITE_USE_POLLING === "1";

export default defineConfig({
  server: {
    port: 5173,
    host: process.env.VITE_HOST || "0.0.0.0",
    proxy: {
      "/api": `http://${process.env.VITE_API_HOST || "127.0.0.1"}:${process.env.VITE_API_PORT || "10120"}`,
      "/health": `http://${process.env.VITE_API_HOST || "127.0.0.1"}:${process.env.VITE_API_PORT || "10120"}`,
    },
    watch: usePolling
      ? { usePolling: true, interval: 1000 }
      : undefined,
  },
});
