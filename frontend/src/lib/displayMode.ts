import { isTauriDesktop } from "./tauriEnvironment";

export type DisplayMode = "immersive" | "overlay";
export type RuntimeMode = "browser" | "tauri";

export type DisplayModeState = {
  requestedMode: DisplayMode;
  activeMode: DisplayMode;
  runtimeMode: RuntimeMode;
  nativeOverlayEnabled: boolean;
};

const DEFAULT_DISPLAY_MODE: DisplayMode = "immersive";

function parseDisplayMode(value: unknown): DisplayMode {
  if (typeof value !== "string") return DEFAULT_DISPLAY_MODE;
  const normalized = value.trim().toLowerCase();
  return normalized === "overlay" ? "overlay" : "immersive";
}

export function getRequestedDisplayMode(): DisplayMode {
  return parseDisplayMode(import.meta.env.VITE_DISPLAY_MODE);
}

export function resolveDisplayMode(): DisplayModeState {
  const requestedMode = getRequestedDisplayMode();
  const runtimeMode: RuntimeMode = isTauriDesktop() ? "tauri" : "browser";
  const nativeOverlayEnabled = runtimeMode === "tauri" && requestedMode === "overlay";

  return {
    requestedMode,
    runtimeMode,
    nativeOverlayEnabled,
    activeMode: requestedMode,
  };
}

export function isOverlayMode(state: DisplayModeState): boolean {
  return state.activeMode === "overlay";
}
