import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  publicDir: "../styles",
  server: { proxy: { "/api": api, "/media": api } },
});
