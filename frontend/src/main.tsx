import React from "react";
import ReactDOM from "react-dom/client";
import { OverlayCompanionPage } from "./pages/OverlayCompanionPage";
import { resolveDisplayMode } from "./lib/displayMode";
import { isTauriDesktop } from "./lib/tauriEnvironment";

const displayMode = resolveDisplayMode();

if (typeof document !== "undefined") {
  document.documentElement.dataset.displayMode = displayMode.activeMode;
  document.body.dataset.displayMode = displayMode.activeMode;

  const transparentBackground = displayMode.activeMode === "overlay" ? "transparent" : "#03050c";
  document.documentElement.style.background = transparentBackground;
  document.body.style.background = transparentBackground;
  document.body.style.margin = "0";

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;

    const anchor = target.closest("a[href]");
    if (!(anchor instanceof HTMLAnchorElement)) return;

    const href = anchor.getAttribute("href")?.trim().toLowerCase() ?? "";
    if (href.startsWith("javascript:") || href.startsWith("data:")) {
      event.preventDefault();
    }
  });

  if (isTauriDesktop()) {
    window.open = () => null;
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <OverlayCompanionPage />
  </React.StrictMode>
);
