import React from "react";
import ReactDOM from "react-dom/client";
import { BasicChatPage } from "./pages/BasicChatPage";

if (typeof document !== "undefined") {
  document.documentElement.style.background = "#0b0d12";
  document.body.style.background = "#0b0d12";
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
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BasicChatPage />
  </React.StrictMode>
);
