import { type RefObject, useEffect, useMemo, useRef, useState } from "react";
import { MovementController, type MovementSnapshot, type MovementState } from "./movementController";
import type { OverlayVisibility, StageZoneName } from "./stageZones";
import { createScreenEnvironment } from "./screenEnvironment";
import { usePresenceBehavior, type PresenceSignals } from "../hooks/usePresenceBehavior";
import type { AttentionTarget } from "./presenceController";


export interface StageBoundsProvider {
  getBounds: () => { width: number; height: number };
}

export type StageBehaviorContext = {
  overlays: OverlayVisibility;
  signals: PresenceSignals;
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
};

export function useStageController(
  mode: MovementState,
  stageRef: RefObject<HTMLElement>,
  behaviorContext: StageBehaviorContext
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
  });

  const lastTimeRef = useRef<number>(performance.now());

  const movementState = mode === "walking" ? "walking" : mode;

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

      motionController.current.setTarget(presence.targetPosition);

      const regions = screenEnvironment.getRegions();
      const regionScale = regions.length > 1 ? 0.95 : 1;
      const willingnessScale = 0.85 + presence.movementWillingness;
      const next = motionController.current.update(deltaSeconds * regionScale * willingnessScale, movementState, now);
      setSnapshot(next);
      setPresenceSnapshot({
        attentionTarget: presence.attentionTarget,
        attentionOffset: presence.attentionOffset,
        engagementLevel: presence.engagementLevel,
        preferredZone: presence.preferredZone,
      });

      raf = requestAnimationFrame(animate);
    };

    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, [computePresence, movementState, stageRef]);

  return useMemo(() => {
    const motionMode: MovementState = snapshot.isMoving && mode === "idle" ? "walking" : movementState;
    return {
      transform: `translate(-50%, -50%) translate(${(snapshot.position.x - 0.5) * 100}%, ${(snapshot.position.y - 0.58) * 100}%)`,
      movementState: motionMode,
      facingDirection: snapshot.facingDirection,
      bob: snapshot.bob,
      lean: snapshot.lean,
      pace: snapshot.pace,
      attentionTarget: presenceSnapshot.attentionTarget,
      attentionOffset: presenceSnapshot.attentionOffset,
      engagementLevel: presenceSnapshot.engagementLevel,
      preferredZone: presenceSnapshot.preferredZone,
    };
  }, [movementState, mode, presenceSnapshot, snapshot]);
}
