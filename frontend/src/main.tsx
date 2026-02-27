
  import { createRoot } from "react-dom/client";
  import App from "./App.tsx";
  import "./index.css";
  import "./styles/globals.css";

createRoot(document.getElementById("root")!).render(<App />);

const bootLoader = document.getElementById("boot-loader");
if (bootLoader) {
  bootLoader.classList.add("boot-loader--done");
  window.setTimeout(() => {
    bootLoader.remove();
  }, 360);
}
  
