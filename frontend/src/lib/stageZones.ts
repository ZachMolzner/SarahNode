import type { StagePoint } from "./movementController";

export type StageZoneName =
  | "center_presentation"
  | "left_relaxed"
  | "right_relaxed"
  | "listening_anchor"
  | "caption_friendly"
  | "shutdown_settle";

export type OverlayVisibility = {
  controlsOpen: boolean;
  transcriptOpen: boolean;
  captionsVisible: boolean;
  shutdownVisible: boolean;
};

export type StageBounds = {
  width: number;
  height: number;
};

export type StageZoneMap = Record<StageZoneName, StagePoint>;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function resolveStageZones(bounds: StageBounds, overlays: OverlayVisibility): StageZoneMap {
  const aspect = bounds.width / Math.max(1, bounds.height);
  const isCompact = bounds.width < 760;

  const sidePull = isCompact ? 0.12 : 0.16;
  const centerX = aspect < 1 ? 0.5 : 0.54;

  const rightWeight = overlays.controlsOpen ? 0.08 : 0;
  const leftWeight = overlays.transcriptOpen ? 0.08 : 0;
  const overlayBias = clamp(leftWeight - rightWeight, -0.14, 0.14);

  const captionRise = overlays.captionsVisible ? -0.02 : 0;
  const baseY = isCompact ? 0.6 : 0.58;

  return {
    center_presentation: {
      x: clamp(centerX + overlayBias * 0.35, 0.42, 0.64),
      y: clamp(baseY + captionRise, 0.5, 0.66),
    },
    left_relaxed: {
      x: clamp(centerX - sidePull + overlayBias * 0.22, 0.26, 0.5),
      y: clamp(baseY + 0.02, 0.52, 0.7),
    },
    right_relaxed: {
      x: clamp(centerX + sidePull + overlayBias * 0.22, 0.5, 0.78),
      y: clamp(baseY + 0.02, 0.52, 0.7),
    },
    listening_anchor: {
      x: clamp(centerX + overlayBias * 0.28, 0.42, 0.64),
      y: clamp(baseY + 0.01, 0.52, 0.66),
    },
    caption_friendly: {
      x: clamp(centerX + overlayBias * 0.44, 0.4, 0.66),
      y: clamp(baseY - 0.025, 0.48, 0.62),
    },
    shutdown_settle: {
      x: clamp(centerX + overlayBias * 0.2, 0.42, 0.64),
      y: clamp(baseY + 0.06, 0.58, 0.74),
    },
  };
}
