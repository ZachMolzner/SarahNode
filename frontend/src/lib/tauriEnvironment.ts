export type TauriMonitorRegion = {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

type TauriWindowWithInternals = Window & {
  __TAURI__?: unknown;
  __TAURI_INTERNALS__?: unknown;
};

function hasTauriGlobals() {
  if (typeof window === "undefined") return false;
  const candidate = window as TauriWindowWithInternals;
  return Boolean(candidate.__TAURI__ || candidate.__TAURI_INTERNALS__);
}

export function isTauriDesktop() {
  return hasTauriGlobals();
}

export async function requestTauriAppClose(): Promise<boolean> {
  if (!hasTauriGlobals()) return false;

  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().close();
    return true;
  } catch {
    return false;
  }
}

export async function getTauriMonitorRegions(): Promise<TauriMonitorRegion[] | null> {
  if (!hasTauriGlobals()) return null;

  try {
    const { availableMonitors } = await import("@tauri-apps/api/window");
    const monitors = await availableMonitors();

    if (!Array.isArray(monitors) || monitors.length === 0) {
      return null;
    }

    return monitors.map((monitor, index) => ({
      id: monitor.name ?? `monitor-${index}`,
      x: monitor.position.x,
      y: monitor.position.y,
      width: monitor.size.width,
      height: monitor.size.height,
    }));
  } catch {
    // TODO(native-multi-monitor): enrich this adapter with work area, scale factor,
    // and active-window routing once SarahNode's movement controller starts
    // consuming monitor metadata directly from native runtimes.
    return null;
  }
}
