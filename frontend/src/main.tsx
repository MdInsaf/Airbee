import { createRoot } from "react-dom/client";
import { Amplify } from "aws-amplify";
import App from "./App.tsx";
import { RootErrorBoundary } from "@/components/RootErrorBoundary";
import "./index.css";

const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID || "ap-south-1_XaPmqKaR4";
const userPoolClientId = import.meta.env.VITE_COGNITO_CLIENT_ID || "3cpce14mrt8c041l6epv4tiv2k";
const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element not found");
}

try {
  if (userPoolId && userPoolClientId) {
    Amplify.configure({
      Auth: {
        Cognito: {
          userPoolId,
          userPoolClientId,
          loginWith: { email: true },
        },
      },
    });
  }

  createRoot(rootElement).render(
    <RootErrorBoundary>
      <App />
    </RootErrorBoundary>
  );
} catch (error) {
  console.error("App bootstrap error:", error);
  const message = error instanceof Error ? error.message : String(error);
  rootElement.innerHTML = `
    <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;font-family:'DM Sans',system-ui,sans-serif;background:#faf8f5;color:#1b2230;">
      <div style="width:100%;max-width:720px;background:#fff;border:1px solid #e4e7ec;border-radius:24px;padding:24px;box-shadow:0 8px 30px rgba(15,23,42,0.06);">
        <p style="margin:0 0 8px;font-size:14px;font-weight:700;color:#dc2626;">Application Bootstrap Error</p>
        <h1 style="margin:0 0 16px;font-size:28px;line-height:1.2;">The app failed before React mounted.</h1>
        <pre style="margin:0;white-space:pre-wrap;word-break:break-word;font-size:14px;line-height:1.6;background:#f4f4f5;border-radius:16px;padding:16px;">${message}</pre>
      </div>
    </div>
  `;
}
