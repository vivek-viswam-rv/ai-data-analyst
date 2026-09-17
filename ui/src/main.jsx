import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";

import "./index.css";
import App from "components/App.jsx";
import { Toaster } from "shadcn/sonner.jsx";
import { registerIntercepts } from "apis/axios";
import queryClient from "utils/queryClient.js";

registerIntercepts();

createRoot(document.getElementById("root")).render(
  <QueryClientProvider client={queryClient}>
    <App />
    <Toaster position="bottom-left" />
  </QueryClientProvider>
);
