import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createWindowControlBridge } from "../lib/windowControls";
import { DEFAULT_USER_SETTINGS, type UserSettings } from "../types/settings";

const STORAGE_KEY = "sarahnode.user-settings.v1";

type PersistedUserSettings = Partial<UserSettings> & { version?: number };

function loadStoredSettings(): PersistedUserSettings {
  if (typeof window === "undefined") return {};

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as PersistedUserSettings;
    return parsed ?? {};
  } catch {
    return {};
  }
}

function sanitizeSettings(partial: PersistedUserSettings): UserSettings {
  return {
    ...DEFAULT_USER_SETTINGS,
    ...partial,
    preferredMode:
      partial.preferredMode === "immersive"
        ? "immersive"
        : partial.preferredMode === "overlay"
          ? "overlay"
          : DEFAULT_USER_SETTINGS.preferredMode,
  };
}

function persistSettings(settings: UserSettings) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...settings, version: 1 }));
}

function desktopFromUserSettings(settings: UserSettings) {
  return {
    alwaysOnTop: settings.alwaysOnTop,
    overlayMode: settings.overlayMode,
    closeToTrayOnClose: settings.closeToTrayOnClose,
    voiceOutputEnabled: settings.voiceOutputEnabled,
  };
}

export function useSettingsStore() {
  const storedSettings = useMemo(() => sanitizeSettings(loadStoredSettings()), []);
  const [settings, setSettings] = useState<UserSettings>(storedSettings);
  const [settingsReady, setSettingsReady] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const windowBridge = useMemo(() => createWindowControlBridge(), []);
  const lastDesktopSyncRef = useRef<string>("");
  const settingsRef = useRef(settings);
  const readyRef = useRef(false);

  useEffect(() => {
    settingsRef.current = settings;
    if (!readyRef.current) return;
    persistSettings(settings);
  }, [settings]);

  useEffect(() => {
    if (!windowBridge.isNativeDesktop) {
      readyRef.current = true;
      setSettingsReady(true);
      return;
    }

    let active = true;

    const applyDesktopSettings = (desktopSettings: Partial<UserSettings>) => {
      setSettings((current) => {
        const next = sanitizeSettings({ ...current, ...desktopSettings });
        lastDesktopSyncRef.current = JSON.stringify(desktopFromUserSettings(next));
        return next;
      });
    };

    void windowBridge.signalFrontendReady();

    void windowBridge.getDesktopSettings().then((desktopSettings) => {
      if (!active) return;
      if (desktopSettings) {
        applyDesktopSettings(desktopSettings);
      }
      readyRef.current = true;
      setSettingsReady(true);
    });

    let cleanupSettings = () => {};
    let cleanupCommand = () => {};

    void windowBridge
      .onDesktopSettingsUpdated((desktopSettings) => {
        if (!active) return;
        applyDesktopSettings(desktopSettings);
      })
      .then((unlisten) => {
        cleanupSettings = unlisten;
      });

    void windowBridge
      .onDesktopCommand((event) => {
        if (!active) return;
        if (event.command === "summon-hotkey") {
          setSettingsOpen(true);
        }
      })
      .then((unlisten) => {
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
      setSettings((current) => ({ ...current, ...patch }));

      if (!windowBridge.isNativeDesktop) return;

      const next = sanitizeSettings({ ...settingsRef.current, ...patch });
      const desktopPayload = desktopFromUserSettings(next);
      const signature = JSON.stringify(desktopPayload);
      if (signature === lastDesktopSyncRef.current) return;

      const updated = await windowBridge.updateDesktopSettings(desktopPayload);
      if (updated) {
        lastDesktopSyncRef.current = JSON.stringify(updated);
        setSettings((existing) => sanitizeSettings({ ...existing, ...updated }));
      }
    },
    [windowBridge]
  );

  return {
    settings,
    settingsReady,
    settingsOpen,
    setSettingsOpen,
    updateSettings,
    windowBridge,
  };
}
