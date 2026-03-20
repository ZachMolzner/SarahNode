import React from "react";
import ReactDOM from "react-dom/client";
import { OverlayCompanionPage } from "./pages/OverlayCompanionPage";
import { resolveDisplayMode } from "./lib/displayMode";

const displayMode = resolveDisplayMode();

if (typeof document !== "undefined") {
  document.documentElement.dataset.displayMode = displayMode.activeMode;
  document.body.dataset.displayMode = displayMode.activeMode;

  const transparentBackground = displayMode.activeMode === "overlay" ? "transparent" : "#03050c";
  document.documentElement.style.background = transparentBackground;
  document.body.style.background = transparentBackground;
  document.body.style.margin = "0";
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <OverlayCompanionPage />
  </React.StrictMode>
);
