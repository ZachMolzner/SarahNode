import type { DisplayRegion } from "./screenEnvironment";
import type { MovementState, StagePoint } from "./movementController";
import type { OverlayVisibility } from "./stageZones";

export type DesktopGroundPlane = {
  groundLineY: number;
  leftBoundary: number;
  rightBoundary: number;
  edgeZoneWidth: number;
  leftEdgeZone: { start: number; end: number };
  rightEdgeZone: { start: number; end: number };
  perchCandidates: number[];
};

export type DesktopGroundedMotion = {
  target: StagePoint;
  edgeLean: number;
  perchDepth: number;
  settledAtEdge: boolean;
  presentationBias: number;
  plane: DesktopGroundPlane;
};

export type DesktopGroundInput = {
  baseTarget: StagePoint;
  currentPosition: StagePoint;
  movementState: MovementState;
  engagementLevel: number;
  overlays: OverlayVisibility;
  nowMs: number;
  bounds: { width: number; height: number };
  regions: DisplayRegion[];
};

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function selectActiveRegion(regions: DisplayRegion[], bounds: { width: number; height: number }): DisplayRegion {
  if (regions.length === 0) {
    return { id: "viewport", x: 0, y: 0, width: bounds.width, height: bounds.height };
  }

  return regions.reduce((largest, region) => {
    const currentArea = largest.width * largest.height;
    const nextArea = region.width * region.height;
    return nextArea > currentArea ? region : largest;
  });
}

export function resolveDesktopGroundPlane(regions: DisplayRegion[], bounds: { width: number; height: number }): DesktopGroundPlane {
  const active = selectActiveRegion(regions, bounds);
  const aspect = active.width / Math.max(1, active.height);

  // Approximation only: this uses the monitor/viewport bottom edge as taskbar-like ground.
  // Future native enhancement can swap this for true work-area/taskbar data without changing callers.
  const groundLineY = clamp(aspect < 1 ? 0.78 : 0.74, 0.68, 0.82);
  const boundaryPadding = aspect < 1 ? 0.1 : 0.075;
  const leftBoundary = boundaryPadding;
  const rightBoundary = 1 - boundaryPadding;
  const edgeZoneWidth = clamp((rightBoundary - leftBoundary) * 0.17, 0.085, 0.16);

  return {
    groundLineY,
    leftBoundary,
    rightBoundary,
    edgeZoneWidth,
    leftEdgeZone: {
      start: leftBoundary,
      end: leftBoundary + edgeZoneWidth,
    },
    rightEdgeZone: {
      start: rightBoundary - edgeZoneWidth,
      end: rightBoundary,
    },
    perchCandidates: [leftBoundary + edgeZoneWidth * 0.42, rightBoundary - edgeZoneWidth * 0.42],
  };
}

export function resolveDesktopGroundedMotion(input: DesktopGroundInput): DesktopGroundedMotion {
  const plane = resolveDesktopGroundPlane(input.regions, input.bounds);

  const isEngaged = input.movementState === "talking" || input.movementState === "thinking" || input.movementState === "listening";
  const presentationBias = isEngaged ? 1 : clamp(input.engagementLevel * 0.7, 0, 0.7);

  const centralPresentationX = 0.52;
  const targetXBase = input.baseTarget.x * (1 - presentationBias * 0.34) + centralPresentationX * (presentationBias * 0.34);
  const targetX = clamp(targetXBase, plane.leftBoundary, plane.rightBoundary);

  const modeLift =
    input.movementState === "talking"
      ? 0.026
      : input.movementState === "thinking"
        ? 0.02
        : input.movementState === "listening"
          ? 0.014
          : input.movementState === "shutting_down"
            ? -0.012
            : 0;

  const overlayLift = input.overlays.captionsVisible ? 0.008 : 0;
  const targetY = clamp(plane.groundLineY - modeLift - overlayLift, plane.groundLineY - 0.07, plane.groundLineY + 0.015);

  const leftDistance = Math.abs(targetX - plane.leftBoundary);
  const rightDistance = Math.abs(plane.rightBoundary - targetX);
  const edgeDistance = Math.min(leftDistance, rightDistance);
  const edgeProximity = clamp(1 - edgeDistance / plane.edgeZoneWidth, 0, 1);

  const idleRestWindow = (Math.sin(input.nowMs * 0.00036) + 1) * 0.5;
  const shouldSettle = input.movementState === "idle" && presentationBias < 0.34 && idleRestWindow > 0.55;

  const edgeLeanDirection = targetX <= 0.5 ? -1 : 1;
  const edgeLean = shouldSettle ? edgeLeanDirection * edgeProximity * 0.05 : edgeLeanDirection * edgeProximity * 0.025;

  const perchDepth = shouldSettle ? edgeProximity * 0.05 : 0;
  const settledAtEdge = shouldSettle && edgeProximity > 0.3;

  return {
    target: { x: targetX, y: targetY },
    edgeLean,
    perchDepth,
    settledAtEdge,
    presentationBias,
    plane,
  };
}
