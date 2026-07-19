import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./theme.css";
import "./i18n";
import App from "./App";

// A new service worker taking over means new app code is live — reload so the
// user actually runs it (sw.js is built with skipWaiting, so it takes over as
// soon as it installs). Skipped when no controller existed at load: that case
// is the very first install claiming this page, which is already current.
if ("serviceWorker" in navigator) {
  const hadController = !!navigator.serviceWorker.controller;
  let reloading = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!hadController || reloading) return;
    reloading = true;
    window.location.reload();
  });
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
