import { getTauriMonitorRegions, isTauriDesktop, type TauriMonitorRegion } from "./tauriEnvironment";

export type DisplayRegion = {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

export interface ScreenEnvironment {
  getRegions: () => DisplayRegion[];
  refreshRegions: () => Promise<void>;
}

function createViewportRegion(): DisplayRegion {
  return {
    id: "viewport",
    x: 0,
    y: 0,
    width: window.innerWidth,
    height: window.innerHeight,
  };
}

export function createBrowserScreenEnvironment(): ScreenEnvironment {
  return {
    getRegions: () => {
      const fallback = createViewportRegion();

      const segmented = (window as Window & {
        getWindowSegments?: () => Array<{ left: number; top: number; width: number; height: number }>;
      }).getWindowSegments;

      if (typeof segmented !== "function") {
        return [fallback];
      }

      const segments = segmented();
      if (!Array.isArray(segments) || segments.length === 0) {
        return [fallback];
      }

      return segments.map((segment, index) => ({
        id: `segment-${index}`,
        x: segment.left,
        y: segment.top,
        width: segment.width,
        height: segment.height,
      }));
    },
    refreshRegions: async () => {
      // no-op in browser mode
    },
  };
}

export function createTauriScreenEnvironment(): ScreenEnvironment {
  let monitorRegions: TauriMonitorRegion[] = [];

  return {
    getRegions: () => {
      if (monitorRegions.length > 0) return monitorRegions;
      return [createViewportRegion()];
    },
    refreshRegions: async () => {
      const regions = await getTauriMonitorRegions();
      monitorRegions = Array.isArray(regions) && regions.length > 0 ? regions : [];
    },
  };
}

export function createScreenEnvironment(): ScreenEnvironment {
  return isTauriDesktop() ? createTauriScreenEnvironment() : createBrowserScreenEnvironment();
}
