import { invoke } from "@tauri-apps/api/core";
import { emit, listen } from "@tauri-apps/api/event";
import { isTauriDesktop } from "./tauriEnvironment";
import type { DesktopSettings } from "../types/settings";

export type DesktopCommandEvent = {
  command: "toggle-always-on-top" | "toggle-overlay-mode" | "hidden-to-tray" | "summon-hotkey" | string;
};

type DesktopSettingsListener = (settings: DesktopSettings) => void;
type DesktopCommandListener = (event: DesktopCommandEvent) => void;

export type WindowControlBridge = {
  isNativeDesktop: boolean;
  getDesktopSettings: () => Promise<DesktopSettings | null>;
  updateDesktopSettings: (settings: DesktopSettings) => Promise<DesktopSettings | null>;
  setAlwaysOnTop: (enabled: boolean) => Promise<void>;
  setOverlayMode: (enabled: boolean) => Promise<void>;
  summonWindow: () => Promise<void>;
  hideWindow: () => Promise<void>;
  onDesktopSettingsUpdated: (listener: DesktopSettingsListener) => Promise<() => void>;
  onDesktopCommand: (listener: DesktopCommandListener) => Promise<() => void>;
  signalFrontendReady: () => Promise<void>;
};

async function invokeSafe<T>(command: string, payload?: Record<string, unknown>): Promise<T | null> {
  if (!isTauriDesktop()) return null;
  try {
    return await invoke<T>(command, payload);
  } catch {
    return null;
  }
}

export function createWindowControlBridge(): WindowControlBridge {
  const native = isTauriDesktop();

  return {
    isNativeDesktop: native,
    getDesktopSettings: () => invokeSafe<DesktopSettings>("get_desktop_settings"),
    updateDesktopSettings: (settings) => invokeSafe<DesktopSettings>("update_desktop_settings", { settings }),
    async setAlwaysOnTop(enabled) {
      await invokeSafe<DesktopSettings>("toggle_always_on_top", { enabled });
    },
    async setOverlayMode(enabled) {
      await invokeSafe<DesktopSettings>("set_overlay_mode", { enabled });
    },
    async summonWindow() {
      await invokeSafe("summon_main_window");
    },
    async hideWindow() {
      await invokeSafe("hide_main_window");
    },
    async onDesktopSettingsUpdated(listener) {
      if (!native) return () => {};
      const unlisten = await listen<DesktopSettings>("desktop://settings-updated", (event) => listener(event.payload));
      return unlisten;
    },
    async onDesktopCommand(listener) {
      if (!native) return () => {};
      const unlisten = await listen<DesktopCommandEvent>("desktop://command", (event) => listener(event.payload));
      return unlisten;
    },
    async signalFrontendReady() {
      if (!native) return;
      await emit("desktop://frontend-ready");
    },
  };
}
