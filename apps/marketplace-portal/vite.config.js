import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// API_BASE points at the local FastAPI dev server for now
// (services/api, run with `uvicorn main:app --port 8000`).
// Swap for the real Render URL once deployed -- see services/api/README.md.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
