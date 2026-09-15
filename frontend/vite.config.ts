import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
        configure: (proxy) => {
          // Set Connection: close so every proxied request doesn't hold
          // a persistent socket open – prevents TIME_WAIT pile-up.
          proxy.on("proxyReq", (proxyReq) => {
            proxyReq.setHeader("Connection", "close");
          });

          // Swallow proxy errors silently (ECONNRESET / ECONNREFUSED when
          // the backend is not yet up) and return a clean 502 instead of
          // crashing or printing a stack trace.
          proxy.on("error", (err, _req, res) => {
            const code = (err as NodeJS.ErrnoException).code ?? "";
            if (!["ECONNRESET", "ECONNREFUSED", "ETIMEDOUT"].includes(code)) {
              console.warn("[proxy]", err.message);
            }
            if (res && "writeHead" in res && !(res as import("http").ServerResponse).headersSent) {
              (res as import("http").ServerResponse).writeHead(502, {
                "Content-Type": "application/json",
              });
              (res as import("http").ServerResponse).end(
                JSON.stringify({ error: "Backend unavailable" })
              );
            }
          });
        },
      },
    },
  },
});
