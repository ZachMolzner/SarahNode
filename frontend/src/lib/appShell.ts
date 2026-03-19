import { getCurrentWindow } from "@tauri-apps/api/window";
import { resolveDisplayMode, type DisplayModeState } from "./displayMode";
import { isTauriDesktop, requestTauriAppClose } from "./tauriEnvironment";

export type AppCloseAttemptResult = "closed" | "fallback";

export type AppShell = {
  mode: "browser" | "tauri";
  displayMode: DisplayModeState;
  requestClose: () => Promise<AppCloseAttemptResult>;
  configureWindowForDisplayMode: () => Promise<void>;
};

async function configureTauriWindow(mode: DisplayModeState): Promise<void> {
  if (mode.runtimeMode !== "tauri") return;

  try {
    const appWindow = getCurrentWindow();
    await appWindow.setFullscreen(mode.activeMode === "immersive");
  } catch {
    // Keep window startup stable when native calls are unavailable.
  }
}

export const browserAppShell: AppShell = {
  mode: "browser",
  displayMode: resolveDisplayMode(),
  async requestClose(): Promise<AppCloseAttemptResult> {
    if (typeof window === "undefined") return "fallback";

    try {
      window.close();
    } catch {
      return "fallback";
    }

    await new Promise((resolve) => {
      window.setTimeout(resolve, 300);
    });

    return window.closed ? "closed" : "fallback";
  },
  async configureWindowForDisplayMode() {
    // Browser runtime has no native window control equivalent.
  },
};

export const tauriAppShell: AppShell = {
  mode: "tauri",
  displayMode: resolveDisplayMode(),
  async requestClose(): Promise<AppCloseAttemptResult> {
    const nativeCloseRequested = await requestTauriAppClose();
    if (nativeCloseRequested) return "closed";
    return browserAppShell.requestClose();
  },
  async configureWindowForDisplayMode() {
    await configureTauriWindow(this.displayMode);
  },
};

export function createAppShell(): AppShell {
  return isTauriDesktop() ? tauriAppShell : browserAppShell;
}
