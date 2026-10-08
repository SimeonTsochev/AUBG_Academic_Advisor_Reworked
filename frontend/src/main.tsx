
  import { createRoot } from "react-dom/client";
  import { Analytics } from "@vercel/analytics/react";
  import { SpeedInsights } from "@vercel/speed-insights/react";
  import App from "./App";
  import "./index.css";
  import "./styles/globals.css";
  import "./styles/components.css";
  import "./styles/plan.css";
  import "./styles/advisor.css";
  import "./styles/onboarding.css";

createRoot(document.getElementById("root")!).render(
  <>
    <App />
    <Analytics />
    <SpeedInsights />
  </>,
);

const bootLoader = document.getElementById("boot-loader");
if (bootLoader) {
  bootLoader.classList.add("boot-loader--done");
  window.setTimeout(() => {
    bootLoader.remove();
  }, 360);
}
  
