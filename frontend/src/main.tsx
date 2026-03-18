
  import { createRoot } from "react-dom/client";
  import { Analytics } from "@vercel/analytics/react";
  import App from "./App.tsx";
  import "./index.css";
  import "./styles/globals.css";

createRoot(document.getElementById("root")!).render(
  <>
    <App />
    <Analytics />
  </>,
);

const bootLoader = document.getElementById("boot-loader");
if (bootLoader) {
  bootLoader.classList.add("boot-loader--done");
  window.setTimeout(() => {
    bootLoader.remove();
  }, 360);
}
  
