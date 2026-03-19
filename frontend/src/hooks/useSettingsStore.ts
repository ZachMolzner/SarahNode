import { useCallback, useEffect, useMemo, useState } from "react";
import { createWindowControlBridge } from "../lib/windowControls";
import { DEFAULT_USER_SETTINGS, type UserSettings } from "../types/settings";

const STORAGE_KEY = "sarahnode.user-settings.v1";

function loadStoredSettings(): UserSettings {
  if (typeof window === "undefined") return DEFAULT_USER_SETTINGS;

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_USER_SETTINGS;
    const parsed = JSON.parse(raw) as Partial<UserSettings>;
    return {
      ...DEFAULT_USER_SETTINGS,
      ...parsed,
      preferredMode: parsed.preferredMode === "immersive" ? "immersive" : parsed.preferredMode === "overlay" ? "overlay" : DEFAULT_USER_SETTINGS.preferredMode,
    };
  } catch {
    return DEFAULT_USER_SETTINGS;
  }
}

function persistSettings(settings: UserSettings) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function useSettingsStore() {
  const [settings, setSettings] = useState<UserSettings>(() => loadStoredSettings());
  const [settingsOpen, setSettingsOpen] = useState(false);
  const windowBridge = useMemo(() => createWindowControlBridge(), []);

  useEffect(() => {
    persistSettings(settings);
  }, [settings]);

  useEffect(() => {
    if (!windowBridge.isNativeDesktop) return;

    void windowBridge.signalFrontendReady();

    let active = true;
    void windowBridge.getDesktopSettings().then((desktopSettings) => {
      if (!active || !desktopSettings) return;
      setSettings((current) => ({
        ...current,
        ...desktopSettings,
      }));
    });

    let cleanupSettings = () => {};
    let cleanupCommand = () => {};

    void windowBridge.onDesktopSettingsUpdated((desktopSettings) => {
      setSettings((current) => ({ ...current, ...desktopSettings }));
    }).then((unlisten) => {
      cleanupSettings = unlisten;
    });

    void windowBridge.onDesktopCommand((event) => {
      if (event.command === "summon-hotkey") {
        setSettingsOpen(true);
      }
    }).then((unlisten) => {
      cleanupCommand = unlisten;
    });

    return () => {
      active = false;
      cleanupSettings();
      cleanupCommand();
    };
  }, [windowBridge]);

  const updateSettings = useCallback(
    async (patch: Partial<UserSettings>) => {
      setSettings((current) => {
        const next = { ...current, ...patch };
        void windowBridge.updateDesktopSettings({
          alwaysOnTop: next.alwaysOnTop,
          overlayMode: next.overlayMode,
          closeToTrayOnClose: next.closeToTrayOnClose,
          voiceOutputEnabled: next.voiceOutputEnabled,
        });
        return next;
      });
    },
    [windowBridge]
  );

  return {
    settings,
    settingsOpen,
    setSettingsOpen,
    updateSettings,
    windowBridge,
  };
}
