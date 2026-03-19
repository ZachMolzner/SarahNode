export type InteractionMode = "overlay" | "immersive";

export type DesktopSettings = {
  alwaysOnTop: boolean;
  overlayMode: boolean;
  closeToTrayOnClose: boolean;
  voiceOutputEnabled: boolean;
};

export type UserSettings = DesktopSettings & {
  preferredMode: InteractionMode;
  showSourceFooterCollapsed: boolean;
};

export const DEFAULT_USER_SETTINGS: UserSettings = {
  alwaysOnTop: true,
  overlayMode: true,
  closeToTrayOnClose: true,
  voiceOutputEnabled: true,
  preferredMode: "overlay",
  showSourceFooterCollapsed: true,
};
