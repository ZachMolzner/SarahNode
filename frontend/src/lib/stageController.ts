import { type RefObject, useEffect, useMemo, useRef, useState } from "react";
import { MovementController, type MovementSnapshot, type MovementState } from "./movementController";
import type { OverlayVisibility, StageZoneName } from "./stageZones";
import { createScreenEnvironment } from "./screenEnvironment";
import { usePresenceBehavior, type PresenceSignals } from "../hooks/usePresenceBehavior";
import type { AttentionTarget, InteractionPresenceState } from "./presenceController";
import type { DisplayModeState } from "./displayMode";
import { resolveDesktopGroundedMotion } from "./desktopGroundController";

export interface StageBoundsProvider {
  getBounds: () => { width: number; height: number };
}

export type StageBehaviorContext = {
  overlays: OverlayVisibility;
  signals: PresenceSignals;
  displayMode: DisplayModeState;
};

export type StageMotion = {
  transform: string;
  movementState: MovementState;
  facingDirection: -1 | 1;
  bob: number;
  lean: number;
  pace: number;
  attentionTarget: AttentionTarget;
  attentionOffset: { x: number; y: number };
  engagementLevel: number;
  preferredZone: StageZoneName;
  groundLineY: number;
  edgeLean: number;
  perchDepth: number;
  settledAtEdge: boolean;
  isGroundedOverlay: boolean;
  characterMotionState: "grounded" | "dragging" | "airborne" | "falling" | "landing" | "recovering" | "idle";
  floorPosition: { x: number; y: number };
  isDragActive: boolean;
  landingCompression: number;
  recoveryLift: number;
  landingReaction: number;
  activityState: "active" | "idle";
  idleBehavior: "none" | "wander" | "corner_rest";
  interactionPresenceState: InteractionPresenceState;
  poseTiltDeg: number;
};

export type DragCallbacks = {
  onDragStateChange?: (dragging: boolean) => void;
};

const FLOOR_REST_X_KEY = "sarahnode.overlay.floor-rest-x.v1";
const floorClamp = { minX: 0.12, maxX: 0.88 };
const gravityPerSecond = 1.7;
const landingLift = 0.024;
const landingMs = 170;
const recoverMs = 260;
const strongDropDistance = 0.2;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function useStageController(
  mode: MovementState,
  stageRef: RefObject<HTMLElement>,
  behaviorContext: StageBehaviorContext,
  dragCallbacks?: DragCallbacks
): StageMotion {
  const motionController = useRef<MovementController>(new MovementController({ x: 0.52, y: 0.58 }));
  const computePresence = usePresenceBehavior();
  const behaviorRef = useRef(behaviorContext);

  useEffect(() => {
    behaviorRef.current = behaviorContext;
  }, [behaviorContext]);

  const [snapshot, setSnapshot] = useState<MovementSnapshot>({
    position: { x: 0.52, y: 0.58 },
    facingDirection: 1,
    isMoving: false,
    bob: 0,
    lean: 0,
    pace: 0,
  });
  const [presenceSnapshot, setPresenceSnapshot] = useState({
    attentionTarget: "idle_neutral" as AttentionTarget,
    attentionOffset: { x: 0, y: 0 },
    engagementLevel: 0.3,
    preferredZone: "right_relaxed" as StageZoneName,
    groundLineY: 0.58,
    edgeLean: 0,
    perchDepth: 0,
    settledAtEdge: false,
    isGroundedOverlay: false,
    characterMotionState: "grounded" as StageMotion["characterMotionState"],
    floorPosition: { x: 0.77, y: 0.74 },
    isDragActive: false,
    landingCompression: 0,
    recoveryLift: 0,
    landingReaction: 0,
    activityState: "active" as const,
    idleBehavior: "none" as const,
    interactionPresenceState: "idle" as const,
    poseTiltDeg: 0,
  });

  const lastTimeRef = useRef<number>(performance.now());
  const cursorOffsetRef = useRef({ x: 0, y: 0 });
  const dragStateRef = useRef({
    pointerId: -1,
    isDragging: false,
    floorX: 0.77,
    x: 0.77,
    y: 0.74,
    velocityY: 0,
    state: "grounded" as StageMotion["characterMotionState"],
    releaseAt: 0,
    fallStartY: 0.74,
    landingStrength: 0,
  });

  const movementState = mode === "walking" ? "walking" : mode;

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = Number(window.localStorage.getItem(FLOOR_REST_X_KEY) ?? "0.77");
    if (Number.isFinite(stored)) {
      const clamped = clamp(stored, floorClamp.minX, floorClamp.maxX);
      dragStateRef.current.floorX = clamped;
      dragStateRef.current.x = clamped;
    }
  }, []);

  useEffect(() => {
    let raf = 0;

    const boundsProvider: StageBoundsProvider = {
      getBounds: () => {
        const el = stageRef.current;
        if (!el) return { width: window.innerWidth, height: window.innerHeight };
        return { width: el.clientWidth, height: el.clientHeight };
      },
    };

    const screenEnvironment = createScreenEnvironment();
    void screenEnvironment.refreshRegions();

    const animate = () => {
      const now = performance.now();
      const deltaSeconds = Math.min(0.05, (now - lastTimeRef.current) / 1000);
      lastTimeRef.current = now;

      const bounds = boundsProvider.getBounds();
      const currentPosition = motionController.current.getCurrentPosition();
      const behavior = behaviorRef.current;
      const presence = computePresence({
        mode: movementState,
        overlays: behavior.overlays,
        bounds,
        nowMs: now,
        deltaSeconds,
        currentPosition,
        signals: behavior.signals,
      });

      const regions = screenEnvironment.getRegions();
      const isGroundedOverlay = behavior.displayMode.activeMode === "overlay";

      const groundedMotion =
        isGroundedOverlay
          ? resolveDesktopGroundedMotion({
              baseTarget: presence.targetPosition,
              currentPosition,
              movementState,
              engagementLevel: presence.engagementLevel,
              overlays: behavior.overlays,
              nowMs: now,
              bounds,
              regions,
            })
          : null;

      const floorY = groundedMotion?.plane.groundLineY ?? 0.74;
      const drag = dragStateRef.current;
      let stateChangedToAirborne = false;
      let landingCompression = 0;
      let recoveryLift = 0;
      let landingReaction = 0;
      if (behavior.displayMode.activeMode === "overlay") {
        if (!drag.isDragging) {
          if (drag.y < floorY - 0.001) {
            if (drag.state !== "airborne" && drag.state !== "falling") {
              stateChangedToAirborne = true;
            }
            drag.state = drag.velocityY > 0 ? "falling" : "airborne";
            drag.velocityY += gravityPerSecond * deltaSeconds;
            drag.y += drag.velocityY * deltaSeconds;
            if (drag.y >= floorY) {
              const dropDistance = Math.max(0, floorY - drag.fallStartY);
              const velocityImpact = Math.min(1, drag.velocityY / 0.75);
              drag.landingStrength = clamp(dropDistance / strongDropDistance + velocityImpact * 0.25, 0, 1);
              drag.y = floorY;
              drag.velocityY = 0;
              drag.releaseAt = now;
              drag.state = "landing";
            }
          } else if (drag.state === "landing") {
            if (now - drag.releaseAt > landingMs) {
              drag.state = "recovering";
            }
          } else if (drag.state === "recovering") {
            if (now - drag.releaseAt > landingMs + recoverMs) {
              drag.state = "idle";
            }
          } else {
            drag.state = mode === "idle" ? "idle" : "grounded";
            drag.landingStrength *= 0.94;
          }
        }
        if (stateChangedToAirborne) {
          drag.fallStartY = drag.y;
        }

        const elapsedSinceLand = Math.max(0, now - drag.releaseAt);
        const landingT = clamp(elapsedSinceLand / landingMs, 0, 1);
        const recoverT = clamp((elapsedSinceLand - landingMs) / recoverMs, 0, 1);
        landingCompression = drag.state === "landing" ? (1 - landingT) * (0.018 + drag.landingStrength * 0.02) : 0;
        recoveryLift =
          drag.state === "recovering" ? Math.sin(recoverT * Math.PI) * (0.006 + drag.landingStrength * 0.008) : 0;
        landingReaction =
          (drag.state === "landing" || drag.state === "recovering") && drag.landingStrength > 0.45
            ? (1 - Math.min(1, elapsedSinceLand / (landingMs + recoverMs * 0.8))) * clamp((drag.landingStrength - 0.45) / 0.55, 0, 1)
            : 0;

        const lift =
          drag.state === "landing" ? -landingLift : drag.state === "recovering" ? -landingLift * 0.4 + recoveryLift : 0;
        const targetX = drag.isDragging ? drag.x : drag.floorX;
        motionController.current.setTarget({
          x: clamp(targetX, floorClamp.minX, floorClamp.maxX),
          y: clamp((drag.isDragging ? drag.y : drag.y) + lift, floorY - 0.38, floorY + 0.02),
        });
      } else {
        motionController.current.setTarget(groundedMotion?.target ?? presence.targetPosition);
      }

      const regionScale = regions.length > 1 ? 0.95 : 1;
      const willingnessScale = 0.85 + presence.movementWillingness;
      const next = motionController.current.update(deltaSeconds * regionScale * willingnessScale, movementState, now);
      setSnapshot(next);
      setPresenceSnapshot({
        attentionTarget: presence.attentionTarget,
        attentionOffset: {
          x: presence.attentionOffset.x + cursorOffsetRef.current.x,
          y: presence.attentionOffset.y + cursorOffsetRef.current.y,
        },
        engagementLevel: presence.engagementLevel,
        preferredZone: presence.preferredZone,
        groundLineY: groundedMotion?.plane.groundLineY ?? 0.58,
        edgeLean: groundedMotion?.edgeLean ?? 0,
        perchDepth: groundedMotion?.perchDepth ?? 0,
        settledAtEdge: groundedMotion?.settledAtEdge ?? false,
        isGroundedOverlay,
        characterMotionState: drag.state,
        floorPosition: { x: drag.floorX, y: floorY },
        isDragActive: drag.isDragging,
        landingCompression,
        recoveryLift,
        landingReaction,
        activityState: presence.activityState,
        idleBehavior: presence.idleBehavior,
        interactionPresenceState: presence.interactionPresenceState,
        poseTiltDeg: presence.poseTiltDeg,
      });

      raf = requestAnimationFrame(animate);
    };

    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, [computePresence, movementState, stageRef]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const handlePointerMove = (event: PointerEvent) => {
      const rect = stage.getBoundingClientRect();
      const nx = clamp((event.clientX - rect.left) / Math.max(1, rect.width), 0, 1) - 0.5;
      const ny = clamp((event.clientY - rect.top) / Math.max(1, rect.height), 0, 1) - 0.5;
      const targetX = nx * 0.03;
      const targetY = ny * 0.02;
      cursorOffsetRef.current.x += (targetX - cursorOffsetRef.current.x) * 0.18;
      cursorOffsetRef.current.y += (targetY - cursorOffsetRef.current.y) * 0.18;
    };
    const handleLeave = () => {
      cursorOffsetRef.current.x *= 0.72;
      cursorOffsetRef.current.y *= 0.72;
    };
    stage.addEventListener("pointermove", handlePointerMove);
    stage.addEventListener("pointerleave", handleLeave);
    return () => {
      stage.removeEventListener("pointermove", handlePointerMove);
      stage.removeEventListener("pointerleave", handleLeave);
    };
  }, [stageRef]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || behaviorContext.displayMode.activeMode !== "overlay") return;

    const handlePointerDown = (event: PointerEvent) => {
      const drag = dragStateRef.current;
      const rect = stage.getBoundingClientRect();
      drag.isDragging = true;
      drag.pointerId = event.pointerId;
      drag.state = "dragging";
      dragCallbacks?.onDragStateChange?.(true);
      stage.setPointerCapture(event.pointerId);
      drag.x = clamp((event.clientX - rect.left) / rect.width, floorClamp.minX, floorClamp.maxX);
      drag.y = clamp((event.clientY - rect.top) / rect.height, 0.32, 0.88);
      drag.velocityY = 0;
    };

    const handlePointerMove = (event: PointerEvent) => {
      const drag = dragStateRef.current;
      if (!drag.isDragging || drag.pointerId !== event.pointerId) return;
      const rect = stage.getBoundingClientRect();
      drag.x = clamp((event.clientX - rect.left) / rect.width, floorClamp.minX, floorClamp.maxX);
      drag.y = clamp((event.clientY - rect.top) / rect.height, 0.2, 0.88);
    };

    const release = (event: PointerEvent) => {
      const drag = dragStateRef.current;
      if (!drag.isDragging || drag.pointerId !== event.pointerId) return;
      drag.isDragging = false;
      drag.pointerId = -1;
      drag.floorX = drag.x;
      drag.state = "airborne";
      drag.velocityY = Math.max(0, drag.velocityY);
      drag.fallStartY = drag.y;
      dragCallbacks?.onDragStateChange?.(false);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(FLOOR_REST_X_KEY, String(drag.floorX));
      }
      stage.releasePointerCapture(event.pointerId);
    };

    stage.addEventListener("pointerdown", handlePointerDown);
    stage.addEventListener("pointermove", handlePointerMove);
    stage.addEventListener("pointerup", release);
    stage.addEventListener("pointercancel", release);
    return () => {
      stage.removeEventListener("pointerdown", handlePointerDown);
      stage.removeEventListener("pointermove", handlePointerMove);
      stage.removeEventListener("pointerup", release);
      stage.removeEventListener("pointercancel", release);
    };
  }, [behaviorContext.displayMode.activeMode, dragCallbacks, stageRef]);

  return useMemo(() => {
    const motionMode: MovementState = snapshot.isMoving && mode === "idle" ? "walking" : movementState;
    const baseY = presenceSnapshot.isGroundedOverlay ? presenceSnapshot.groundLineY : 0.58;

    return {
      transform: `translate(-50%, -50%) translate(${(snapshot.position.x - 0.5) * 100}%, ${(snapshot.position.y - baseY) * 100}%) rotate(${presenceSnapshot.poseTiltDeg.toFixed(2)}deg)`,
      movementState: motionMode,
      facingDirection: snapshot.facingDirection,
      bob: snapshot.bob,
      lean: snapshot.lean + presenceSnapshot.edgeLean,
      pace: snapshot.pace,
      attentionTarget: presenceSnapshot.attentionTarget,
      attentionOffset: presenceSnapshot.attentionOffset,
      engagementLevel: presenceSnapshot.engagementLevel,
      preferredZone: presenceSnapshot.preferredZone,
      groundLineY: presenceSnapshot.groundLineY,
      edgeLean: presenceSnapshot.edgeLean,
      perchDepth: presenceSnapshot.perchDepth,
      settledAtEdge: presenceSnapshot.settledAtEdge,
      isGroundedOverlay: presenceSnapshot.isGroundedOverlay,
      characterMotionState: presenceSnapshot.characterMotionState,
      floorPosition: presenceSnapshot.floorPosition,
      isDragActive: presenceSnapshot.isDragActive,
      landingCompression: presenceSnapshot.landingCompression,
      recoveryLift: presenceSnapshot.recoveryLift,
      landingReaction: presenceSnapshot.landingReaction,
      activityState: presenceSnapshot.activityState,
      idleBehavior: presenceSnapshot.idleBehavior,
      interactionPresenceState: presenceSnapshot.interactionPresenceState,
      poseTiltDeg: presenceSnapshot.poseTiltDeg,
    };
  }, [movementState, mode, presenceSnapshot, snapshot]);
}
