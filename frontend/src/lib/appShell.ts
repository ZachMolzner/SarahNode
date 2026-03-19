import { isTauriDesktop, requestTauriAppClose } from "./tauriEnvironment";

export type AppCloseAttemptResult = "closed" | "fallback";

export type AppShell = {
  mode: "browser" | "tauri";
  requestClose: () => Promise<AppCloseAttemptResult>;
};

export const browserAppShell: AppShell = {
  mode: "browser",
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
};

export const tauriAppShell: AppShell = {
  mode: "tauri",
  async requestClose(): Promise<AppCloseAttemptResult> {
    const nativeCloseRequested = await requestTauriAppClose();
    if (nativeCloseRequested) return "closed";
    return browserAppShell.requestClose();
  },
};

export function createAppShell(): AppShell {
  return isTauriDesktop() ? tauriAppShell : browserAppShell;
}
