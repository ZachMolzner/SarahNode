import type { StagePoint } from "./movementController";
import type { OverlayVisibility, StageBounds } from "./stageZones";

export type ActivityState = "active" | "idle";
export type IdleBehavior = "none" | "wander" | "corner_rest";

type IdleBehaviorSnapshot = {
  activityState: ActivityState;
  idleBehavior: IdleBehavior;
  targetPosition: StagePoint | null;
  poseTiltDeg: number;
  poseYOffset: number;
  movementWillingness: number | null;
};

export const IDLE_BEHAVIOR_TUNING = {
  idleStartDelayMs: 3800,
  wakeAttend: {
    durationMs: 620,
  },
  safeZones: {
    viewportPaddingX: 0.1,
    viewportPaddingY: 0.33,
    controlsBlockedWidth: 0.2,
    transcriptBlockedWidth: 0.2,
    excludedCorners: {
      topLeft: false,
      topRight: false,
      bottomLeft: false,
      bottomRight: false,
    },
  },
  wander: {
    viewportPaddingX: 0.14,
    viewportPaddingY: 0.38,
    minY: 0.38,
    maxY: 0.74,
    firstMoveHesitationMs: { min: 260, max: 640 },
    minTravelDistance: 0.14,
    targetReachThreshold: 0.028,
    moveDurationMs: { min: 5200, max: 8800 },
    pauseMs: { min: 900, max: 2100 },
    microVariants: {
      antiRepeatBackToBack: true,
      variants: {
        gentle_drift: { weight: 0.34, moveDurationScale: [0.92, 1.08], pauseDurationScale: [0.85, 1.05], tiltDeg: 0.72, yOffset: 0.0012 },
        look_around_pause: { weight: 0.22, moveDurationScale: [0.86, 1], pauseDurationScale: [1, 1.35], tiltDeg: 1.2, yOffset: 0.0018 },
        curious_tilt_hold: { weight: 0.2, moveDurationScale: [0.9, 1.05], pauseDurationScale: [0.9, 1.15], holdTiltDeg: [1.7, 2.4] },
        thoughtful_pause: { weight: 0.14, moveDurationScale: [0.84, 1], pauseDurationScale: [1.35, 1.85], tiltDeg: 0.42, yOffset: -0.0008 },
        soft_drift_alt: { weight: 0.1, moveDurationScale: [1.02, 1.25], pauseDurationScale: [0.85, 1], tiltDeg: 0.64, yOffset: 0.0008 },
      },
    },
  },
  cornerRest: {
    viewportPaddingX: 0.08,
    topY: 0.45,
    bottomY: 0.72,
    settleTiltDeg: 8,
    settleYOffset: 0.012,
    arrivalSettleDurationMs: 680,
    arrivalOvershootYOffset: 0.006,
    arrivalOvershootTiltDeg: 1.8,
    swayTiltDeg: 1.6,
    swayYOffset: 0.0035,
    microVariants: {
      antiRepeatBackToBack: true,
      variants: {
        weight_shift: { weight: 0.34, swayTiltScale: 1.06, swayYOffsetScale: 0.96, extraPhaseSpeed: 1 },
        deep_lean_settle: { weight: 0.2, settleTiltScale: 1.14, settleYOffsetScale: 1.08, arrivalOvershootScale: 1.55 },
        glance_breathe: { weight: 0.22, swayTiltScale: 0.94, swayYOffsetScale: 1.1, glanceYOffset: 0.0026 },
        calm_sway_alt: { weight: 0.24, swayTiltScale: 0.86, swayYOffsetScale: 1.2, extraPhaseSpeed: 0.82 },
      },
    },
    antiRepeatCorners: {
      recentLimit: 2,
    },
  },
  behaviorRepeatLimit: 2,
} as const;


function randomBetween(min: number, max: number) {
  return min + Math.random() * (max - min);
}

function distance(a: StagePoint, b: StagePoint) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function easeOutCubic(value: number) {
  const t = clamp(value, 0, 1);
  return 1 - Math.pow(1 - t, 3);
}

function lerp(from: number, to: number, t: number) {
  return from + (to - from) * t;
}

export class IdleBehaviorManager {
  private activityState: ActivityState = "active";
  private idleBehavior: IdleBehavior = "none";
  private idleStartedAtMs = 0;
  private lastActiveAtMs = 0;
  private behaviorAbortController: AbortController | null = null;
  private behaviorTarget: StagePoint | null = null;
  private behaviorPauseUntilMs = 0;
  private behaviorMoveUntilMs = 0;
  private cornerAnchor: StagePoint | null = null;
  private cornerArrivalAtMs: number | null = null;
  private cornerPhaseOffset = Math.random() * Math.PI;
  private lastBehavior: IdleBehavior = "none";
  private lastBehaviorStreak = 0;
  private wakeAttendUntilMs = 0;
  private wakeFromTiltDeg = 0;
  private wakeFromYOffset = 0;
  private firstWanderMovePending = false;
  private currentWanderVariant: keyof typeof IDLE_BEHAVIOR_TUNING.wander.microVariants.variants = "gentle_drift";
  private currentWanderHoldTiltDeg = 2;
  private lastWanderVariant: keyof typeof IDLE_BEHAVIOR_TUNING.wander.microVariants.variants | null = null;
  private currentCornerRestVariant: keyof typeof IDLE_BEHAVIOR_TUNING.cornerRest.microVariants.variants = "weight_shift";
  private lastCornerRestVariant: keyof typeof IDLE_BEHAVIOR_TUNING.cornerRest.microVariants.variants | null = null;
  private recentCornerIndices: number[] = [];

  update(input: { mode: string; nowMs: number; bounds: StageBounds; overlays: OverlayVisibility; currentPosition: StagePoint }): IdleBehaviorSnapshot {
    const nextActivity: ActivityState = input.mode === "idle" ? "idle" : "active";

    if (nextActivity === "active") {
      this.lastActiveAtMs = input.nowMs;
      if (this.activityState === "idle") {
        const idlePose = this.computeCurrentIdlePose(input.nowMs);
        this.wakeFromTiltDeg = idlePose.poseTiltDeg;
        this.wakeFromYOffset = idlePose.poseYOffset;
        this.wakeAttendUntilMs = input.nowMs + IDLE_BEHAVIOR_TUNING.wakeAttend.durationMs;
        this.cancelBehavior();
      }
      this.activityState = "active";
      const attendBlend =
        this.wakeAttendUntilMs > input.nowMs
          ? 1 - easeOutCubic(1 - (this.wakeAttendUntilMs - input.nowMs) / IDLE_BEHAVIOR_TUNING.wakeAttend.durationMs)
          : 1;
      return {
        activityState: "active",
        idleBehavior: "none",
        targetPosition: null,
        poseTiltDeg: lerp(this.wakeFromTiltDeg, 0, attendBlend),
        poseYOffset: lerp(this.wakeFromYOffset, 0, attendBlend),
        movementWillingness: null,
      };
    }

    if (this.activityState === "active") {
      this.idleStartedAtMs = input.nowMs;
      this.activityState = "idle";
    }

    const idleElapsed = input.nowMs - this.idleStartedAtMs;
    if (this.idleBehavior === "none" && idleElapsed >= IDLE_BEHAVIOR_TUNING.idleStartDelayMs) {
      this.startBehavior(input.nowMs);
    }

    if (this.idleBehavior === "wander") {
      return this.updateWander(input.nowMs, input.currentPosition, input.overlays);
    }

    if (this.idleBehavior === "corner_rest") {
      return this.updateCornerRest(input.nowMs, input.currentPosition, input.overlays);
    }

    return {
      activityState: "idle",
      idleBehavior: "none",
      targetPosition: null,
      poseTiltDeg: 0,
      poseYOffset: 0,
      movementWillingness: null,
    };
  }

  private startBehavior(nowMs: number) {
    this.cancelBehavior();
    this.behaviorAbortController = new AbortController();
    this.idleBehavior = this.pickIdleBehavior();
    this.behaviorPauseUntilMs = nowMs;
    this.behaviorMoveUntilMs = nowMs;
    this.cornerAnchor = null;
    this.cornerArrivalAtMs = null;
    this.cornerPhaseOffset = Math.random() * Math.PI;
    this.firstWanderMovePending = this.idleBehavior === "wander";
    if (this.idleBehavior === "wander") {
      this.currentWanderVariant = this.pickWanderVariant();
    } else if (this.idleBehavior === "corner_rest") {
      this.currentCornerRestVariant = this.pickCornerRestVariant();
    }
    if (this.firstWanderMovePending) {
      this.behaviorPauseUntilMs =
        nowMs +
        randomBetween(IDLE_BEHAVIOR_TUNING.wander.firstMoveHesitationMs.min, IDLE_BEHAVIOR_TUNING.wander.firstMoveHesitationMs.max);
    }
  }

  private cancelBehavior() {
    this.behaviorAbortController?.abort();
    this.behaviorAbortController = null;
    this.idleBehavior = "none";
    this.behaviorTarget = null;
    this.cornerAnchor = null;
    this.cornerArrivalAtMs = null;
    this.behaviorPauseUntilMs = 0;
    this.behaviorMoveUntilMs = 0;
    this.firstWanderMovePending = false;
  }

  private pickIdleBehavior(): IdleBehavior {
    const choices: IdleBehavior[] = ["wander", "corner_rest"];

    if (this.lastBehavior !== "none" && this.lastBehaviorStreak >= IDLE_BEHAVIOR_TUNING.behaviorRepeatLimit) {
      const alternate = choices.find((choice) => choice !== this.lastBehavior) ?? "wander";
      this.recordBehaviorChoice(alternate);
      return alternate;
    }

    const next = Math.random() < 0.5 ? "wander" : "corner_rest";
    this.recordBehaviorChoice(next);
    return next;
  }

  private recordBehaviorChoice(choice: IdleBehavior) {
    if (choice === this.lastBehavior) {
      this.lastBehaviorStreak += 1;
    } else {
      this.lastBehavior = choice;
      this.lastBehaviorStreak = 1;
    }
  }

  private updateWander(nowMs: number, currentPosition: StagePoint, overlays: OverlayVisibility): IdleBehaviorSnapshot {
    if (this.behaviorAbortController?.signal.aborted) {
      this.idleBehavior = "none";
      return {
        activityState: "idle",
        idleBehavior: "none",
        targetPosition: null,
        poseTiltDeg: 0,
        poseYOffset: 0,
        movementWillingness: null,
      };
    }

    if (!this.behaviorTarget || nowMs >= this.behaviorMoveUntilMs || distance(currentPosition, this.behaviorTarget) < IDLE_BEHAVIOR_TUNING.wander.targetReachThreshold) {
      if (nowMs >= this.behaviorPauseUntilMs) {
        this.behaviorTarget = this.pickWanderTarget(currentPosition, overlays);
        this.firstWanderMovePending = false;
        this.currentWanderVariant = this.pickWanderVariant();
        const variant = IDLE_BEHAVIOR_TUNING.wander.microVariants.variants[this.currentWanderVariant];
        this.currentWanderHoldTiltDeg = randomBetween(variant.holdTiltDeg?.[0] ?? 1.7, variant.holdTiltDeg?.[1] ?? 2.4);
        const moveScale = randomBetween(variant.moveDurationScale[0], variant.moveDurationScale[1]);
        const pauseScale = randomBetween(variant.pauseDurationScale[0], variant.pauseDurationScale[1]);
        this.behaviorMoveUntilMs =
          nowMs + randomBetween(IDLE_BEHAVIOR_TUNING.wander.moveDurationMs.min, IDLE_BEHAVIOR_TUNING.wander.moveDurationMs.max) * moveScale;
        this.behaviorPauseUntilMs =
          this.behaviorMoveUntilMs + randomBetween(IDLE_BEHAVIOR_TUNING.wander.pauseMs.min, IDLE_BEHAVIOR_TUNING.wander.pauseMs.max) * pauseScale;
      }
    }

    const variant = IDLE_BEHAVIOR_TUNING.wander.microVariants.variants[this.currentWanderVariant];
    const isPaused = nowMs >= this.behaviorMoveUntilMs && nowMs < this.behaviorPauseUntilMs;
    const wanderPhase = nowMs * 0.0005 + (this.currentWanderVariant === "soft_drift_alt" ? Math.PI * 0.25 : 0);
    let poseTiltDeg = (variant.tiltDeg ?? 0.7) * Math.sin(wanderPhase);
    let poseYOffset = variant.yOffset ?? 0;
    if (this.currentWanderVariant === "look_around_pause" && isPaused) {
      poseTiltDeg = 0.65 * Math.sin(nowMs * 0.0014) + 0.9 * Math.sin(nowMs * 0.00075);
      poseYOffset += 0.001 * Math.cos(nowMs * 0.0011);
    } else if (this.currentWanderVariant === "curious_tilt_hold" && isPaused) {
      poseTiltDeg = this.currentWanderHoldTiltDeg * Math.sin(this.cornerPhaseOffset + 0.8);
    } else if (this.currentWanderVariant === "thoughtful_pause" && isPaused) {
      poseTiltDeg = 0.28 * Math.sin(nowMs * 0.00036);
      poseYOffset -= 0.0015;
    }

    return {
      activityState: "idle",
      idleBehavior: "wander",
      targetPosition: this.behaviorTarget,
      poseTiltDeg,
      poseYOffset,
      movementWillingness: this.firstWanderMovePending ? 0.18 : 0.3,
    };
  }

  private updateCornerRest(nowMs: number, currentPosition: StagePoint, overlays: OverlayVisibility): IdleBehaviorSnapshot {
    if (this.behaviorAbortController?.signal.aborted) {
      this.idleBehavior = "none";
      return {
        activityState: "idle",
        idleBehavior: "none",
        targetPosition: null,
        poseTiltDeg: 0,
        poseYOffset: 0,
        movementWillingness: null,
      };
    }

    if (!this.cornerAnchor) {
      this.cornerAnchor = this.pickCornerAnchor(overlays);
      this.behaviorTarget = this.cornerAnchor;
      this.cornerArrivalAtMs = null;
    }

    if (
      this.cornerArrivalAtMs === null &&
      this.cornerAnchor &&
      distance(currentPosition, this.cornerAnchor) < IDLE_BEHAVIOR_TUNING.wander.targetReachThreshold * 1.2
    ) {
      this.cornerArrivalAtMs = nowMs;
    }

    const variant = IDLE_BEHAVIOR_TUNING.cornerRest.microVariants.variants[this.currentCornerRestVariant];
    const phase = nowMs * 0.0011 * (variant.extraPhaseSpeed ?? 1) + this.cornerPhaseOffset;
    const settleTiltBase = IDLE_BEHAVIOR_TUNING.cornerRest.settleTiltDeg * (variant.settleTiltScale ?? 1);
    const settledTilt = this.cornerAnchor.x < 0.5 ? settleTiltBase : -settleTiltBase;
    const arrivalElapsed = this.cornerArrivalAtMs === null ? 0 : nowMs - this.cornerArrivalAtMs;
    const arrivalProgress =
      this.cornerArrivalAtMs === null
        ? 0
        : clamp(arrivalElapsed / IDLE_BEHAVIOR_TUNING.cornerRest.arrivalSettleDurationMs, 0, 1);
    const settleEase = easeOutCubic(arrivalProgress);
    const settleBlend = this.cornerArrivalAtMs === null ? 0 : 1 - settleEase;
    const settleDirection = this.cornerAnchor.x < 0.5 ? 1 : -1;
    const arrivalOvershootScale = variant.arrivalOvershootScale ?? 1;
    const swayTiltDeg = IDLE_BEHAVIOR_TUNING.cornerRest.swayTiltDeg * (variant.swayTiltScale ?? 1);
    const swayYOffset = IDLE_BEHAVIOR_TUNING.cornerRest.swayYOffset * (variant.swayYOffsetScale ?? 1);
    const settleYOffset = IDLE_BEHAVIOR_TUNING.cornerRest.settleYOffset * (variant.settleYOffsetScale ?? 1);
    const glanceYOffset = variant.glanceYOffset ? Math.sin(nowMs * 0.00055 + this.cornerPhaseOffset * 0.5) * variant.glanceYOffset : 0;

    return {
      activityState: "idle",
      idleBehavior: "corner_rest",
      targetPosition: this.cornerAnchor,
      poseTiltDeg:
        settledTilt +
        settleDirection * IDLE_BEHAVIOR_TUNING.cornerRest.arrivalOvershootTiltDeg * arrivalOvershootScale * settleBlend +
        Math.sin(phase) * swayTiltDeg,
      poseYOffset:
        settleYOffset +
        IDLE_BEHAVIOR_TUNING.cornerRest.arrivalOvershootYOffset * arrivalOvershootScale * settleBlend +
        Math.cos(phase * 0.8) * swayYOffset +
        glanceYOffset,
      movementWillingness: 0.12,
    };
  }

  private pickWanderTarget(currentPosition: StagePoint, overlays: OverlayVisibility): StagePoint {
    const minX = IDLE_BEHAVIOR_TUNING.wander.viewportPaddingX;
    const maxX = 1 - IDLE_BEHAVIOR_TUNING.wander.viewportPaddingX;
    const minY = Math.max(IDLE_BEHAVIOR_TUNING.wander.viewportPaddingY, IDLE_BEHAVIOR_TUNING.wander.minY);
    const maxY = IDLE_BEHAVIOR_TUNING.wander.maxY;
    let fallback: StagePoint = {
      x: randomBetween(minX, maxX),
      y: randomBetween(minY, maxY),
    };

    for (let i = 0; i < 10; i += 1) {
      const candidate = this.applySafeZoneConstraints(
        {
          x: randomBetween(minX, maxX),
          y: randomBetween(minY, maxY),
        },
        overlays,
      );
      fallback = candidate;
      if (distance(candidate, currentPosition) >= IDLE_BEHAVIOR_TUNING.wander.minTravelDistance) {
        return candidate;
      }
    }

    return fallback;
  }

  private pickCornerAnchor(overlays: OverlayVisibility): StagePoint {
    const corners: Array<{ point: StagePoint; index: number }> = [];
    const pushCorner = (x: number, y: number, index: number) => {
      corners.push({ point: this.applySafeZoneConstraints({ x, y }, overlays), index });
    };
    if (!IDLE_BEHAVIOR_TUNING.safeZones.excludedCorners.topLeft) {
      pushCorner(IDLE_BEHAVIOR_TUNING.cornerRest.viewportPaddingX, IDLE_BEHAVIOR_TUNING.cornerRest.topY, 0);
    }
    if (!IDLE_BEHAVIOR_TUNING.safeZones.excludedCorners.topRight) {
      pushCorner(1 - IDLE_BEHAVIOR_TUNING.cornerRest.viewportPaddingX, IDLE_BEHAVIOR_TUNING.cornerRest.topY, 1);
    }
    if (!IDLE_BEHAVIOR_TUNING.safeZones.excludedCorners.bottomLeft) {
      pushCorner(IDLE_BEHAVIOR_TUNING.cornerRest.viewportPaddingX, IDLE_BEHAVIOR_TUNING.cornerRest.bottomY, 2);
    }
    if (!IDLE_BEHAVIOR_TUNING.safeZones.excludedCorners.bottomRight) {
      pushCorner(1 - IDLE_BEHAVIOR_TUNING.cornerRest.viewportPaddingX, IDLE_BEHAVIOR_TUNING.cornerRest.bottomY, 3);
    }
    if (corners.length === 0) {
      return { x: 0.5, y: IDLE_BEHAVIOR_TUNING.cornerRest.bottomY };
    }
    const recentLimit = IDLE_BEHAVIOR_TUNING.cornerRest.antiRepeatCorners.recentLimit;
    const candidates = corners.filter((corner) => !this.recentCornerIndices.slice(-recentLimit).includes(corner.index));
    const pool = candidates.length > 0 ? candidates : corners;
    const choice = pool[Math.floor(Math.random() * pool.length)];
    this.recentCornerIndices.push(choice.index);
    if (this.recentCornerIndices.length > recentLimit + 2) {
      this.recentCornerIndices.shift();
    }
    return choice.point;
  }

  private applySafeZoneConstraints(point: StagePoint, overlays: OverlayVisibility): StagePoint {
    let minX = IDLE_BEHAVIOR_TUNING.safeZones.viewportPaddingX;
    let maxX = 1 - IDLE_BEHAVIOR_TUNING.safeZones.viewportPaddingX;
    if (overlays.controlsOpen) {
      maxX = Math.min(maxX, 1 - IDLE_BEHAVIOR_TUNING.safeZones.controlsBlockedWidth);
    }
    if (overlays.transcriptOpen) {
      minX = Math.max(minX, IDLE_BEHAVIOR_TUNING.safeZones.transcriptBlockedWidth);
    }
    return {
      x: clamp(point.x, minX, maxX),
      y: clamp(point.y, IDLE_BEHAVIOR_TUNING.safeZones.viewportPaddingY, 0.86),
    };
  }

  private computeCurrentIdlePose(nowMs: number): { poseTiltDeg: number; poseYOffset: number } {
    if (this.idleBehavior === "corner_rest" && this.cornerAnchor) {
      const variant = IDLE_BEHAVIOR_TUNING.cornerRest.microVariants.variants[this.currentCornerRestVariant];
      const phase = nowMs * 0.0011 * (variant.extraPhaseSpeed ?? 1) + this.cornerPhaseOffset;
      const settledTiltBase = IDLE_BEHAVIOR_TUNING.cornerRest.settleTiltDeg * (variant.settleTiltScale ?? 1);
      const settledTilt = this.cornerAnchor.x < 0.5 ? settledTiltBase : -settledTiltBase;
      return {
        poseTiltDeg: settledTilt + Math.sin(phase) * IDLE_BEHAVIOR_TUNING.cornerRest.swayTiltDeg * (variant.swayTiltScale ?? 1),
        poseYOffset: IDLE_BEHAVIOR_TUNING.cornerRest.settleYOffset + Math.cos(phase * 0.8) * IDLE_BEHAVIOR_TUNING.cornerRest.swayYOffset * (variant.swayYOffsetScale ?? 1),
      };
    }
    if (this.idleBehavior === "wander") {
      const variant = IDLE_BEHAVIOR_TUNING.wander.microVariants.variants[this.currentWanderVariant];
      return {
        poseTiltDeg: (variant.tiltDeg ?? 0.8) * Math.sin(nowMs * 0.0005),
        poseYOffset: variant.yOffset ?? 0,
      };
    }
    return { poseTiltDeg: 0, poseYOffset: 0 };
  }

  private pickWanderVariant(): keyof typeof IDLE_BEHAVIOR_TUNING.wander.microVariants.variants {
    const choice = this.pickWeightedVariant(IDLE_BEHAVIOR_TUNING.wander.microVariants.variants, this.lastWanderVariant, IDLE_BEHAVIOR_TUNING.wander.microVariants.antiRepeatBackToBack);
    this.lastWanderVariant = choice;
    return choice;
  }

  private pickCornerRestVariant(): keyof typeof IDLE_BEHAVIOR_TUNING.cornerRest.microVariants.variants {
    const choice = this.pickWeightedVariant(
      IDLE_BEHAVIOR_TUNING.cornerRest.microVariants.variants,
      this.lastCornerRestVariant,
      IDLE_BEHAVIOR_TUNING.cornerRest.microVariants.antiRepeatBackToBack,
    );
    this.lastCornerRestVariant = choice;
    return choice;
  }

  private pickWeightedVariant<T extends Record<string, { weight: number }>>(variants: T, previous: keyof T | null, avoidPrevious: boolean): keyof T {
    const entries = Object.entries(variants).map(([key, value]) => ({ key: key as keyof T, weight: value.weight }));
    const filtered = avoidPrevious && previous ? entries.filter((entry) => entry.key !== previous) : entries;
    const pool = filtered.length > 0 ? filtered : entries;
    const totalWeight = pool.reduce((sum, entry) => sum + entry.weight, 0);
    let roll = Math.random() * totalWeight;
    for (const entry of pool) {
      roll -= entry.weight;
      if (roll <= 0) return entry.key;
    }
    return pool[pool.length - 1].key;
  }

  getCurrentState() {
    return {
      activityState: this.activityState,
      idleBehavior: this.idleBehavior,
    };
  }
}
