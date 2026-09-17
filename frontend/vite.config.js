import { defineConfig, loadEnv } from "vite";
import path from "path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(import.meta.dirname, ".."), "");

  return {
    root: "./ui",
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(import.meta.dirname, "./ui/src"),
        "components": path.resolve(import.meta.dirname, "./ui/src/components"),
        "shadcn": path.resolve(import.meta.dirname, "./ui/src/components/shadcn"),
        "utils": path.resolve(import.meta.dirname, "./ui/src/utils"),
        "hooks": path.resolve(import.meta.dirname, "./ui/src/hooks"),
        "apis": path.resolve(import.meta.dirname, "./ui/src/apis"),
        "constants": path.resolve(import.meta.dirname, "./ui/src/constants"),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: env.VITE_API_URL || "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: "../dist",
      emptyOutDir: true,
    },
  };
});
