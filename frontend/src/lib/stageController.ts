import { type RefObject, useEffect, useMemo, useRef, useState } from "react";
import { MovementController, type MovementSnapshot, type MovementState, type StagePoint } from "./movementController";

export type DisplayRegion = {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

export interface ScreenEnvironment {
  getRegions: () => DisplayRegion[];
}

export interface StageBoundsProvider {
  getBounds: () => { width: number; height: number };
}

export type StageMotion = {
  transform: string;
  movementState: MovementState;
  facingDirection: -1 | 1;
  bob: number;
  lean: number;
  pace: number;
};

export function createBrowserScreenEnvironment(): ScreenEnvironment {
  return {
    getRegions: () => {
      const fallback: DisplayRegion = {
        id: "viewport",
        x: 0,
        y: 0,
        width: window.innerWidth,
        height: window.innerHeight,
      };

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
  };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function normalizeTarget(point: StagePoint): StagePoint {
  return {
    x: clamp(point.x, 0.18, 0.82),
    y: clamp(point.y, 0.28, 0.76),
  };
}

function nextIdleTarget(now: number): StagePoint {
  const drift = (Math.sin(now * 0.00013) + 1) * 0.5;
  return normalizeTarget({
    x: 0.35 + drift * 0.3,
    y: 0.56 + Math.cos(now * 0.00017) * 0.06,
  });
}

export function useStageController(mode: MovementState, stageRef: RefObject<HTMLElement>): StageMotion {
  const motionController = useRef<MovementController>(new MovementController({ x: 0.52, y: 0.58 }));
  const [snapshot, setSnapshot] = useState<MovementSnapshot>({
    position: { x: 0.52, y: 0.58 },
    facingDirection: 1,
    isMoving: false,
    bob: 0,
    lean: 0,
    pace: 0,
  });
  const lastTimeRef = useRef<number>(performance.now());
  const idleDeadlineRef = useRef<number>(performance.now() + 6500);

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

    const screenEnvironment = createBrowserScreenEnvironment();

    const animate = () => {
      const now = performance.now();
      const deltaSeconds = Math.min(0.05, (now - lastTimeRef.current) / 1000);
      lastTimeRef.current = now;

      const { width } = boundsProvider.getBounds();
      const centerBias = width < 700 ? 0.5 : 0.56;

      if (movementState === "listening") {
        motionController.current.setTarget({ x: centerBias, y: 0.58 });
      } else if (movementState === "talking") {
        motionController.current.setTarget({ x: centerBias + 0.02, y: 0.58 });
      } else if (movementState === "thinking") {
        motionController.current.setTarget({ x: centerBias + 0.05, y: 0.59 });
      } else if (movementState === "shutting_down") {
        motionController.current.setTarget({ x: centerBias, y: 0.62 });
      } else {
        if (now > idleDeadlineRef.current) {
          motionController.current.setTarget(nextIdleTarget(now));
          idleDeadlineRef.current = now + 9000 + Math.random() * 7000;
        }
      }

      const regions = screenEnvironment.getRegions();
      const regionScale = regions.length > 1 ? 0.95 : 1;
      const next = motionController.current.update(deltaSeconds * regionScale, movementState, now);
      setSnapshot(next);
      raf = requestAnimationFrame(animate);
    };

    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, [movementState, stageRef]);

  return useMemo(() => {
    const motionMode: MovementState = snapshot.isMoving && mode === "idle" ? "walking" : movementState;
    return {
      transform: `translate(-50%, -50%) translate(${(snapshot.position.x - 0.5) * 100}%, ${(snapshot.position.y - 0.58) * 100}%)`,
      movementState: motionMode,
      facingDirection: snapshot.facingDirection,
      bob: snapshot.bob,
      lean: snapshot.lean,
      pace: snapshot.pace,
    };
  }, [movementState, mode, snapshot]);
}
