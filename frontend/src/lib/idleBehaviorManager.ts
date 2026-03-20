import type { StagePoint } from "./movementController";
import type { StageBounds } from "./stageZones";

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
  wander: {
    viewportPaddingX: 0.14,
    minY: 0.38,
    maxY: 0.74,
    targetReachThreshold: 0.028,
    moveDurationMs: { min: 5200, max: 8800 },
    pauseMs: { min: 900, max: 2100 },
  },
  cornerRest: {
    viewportPaddingX: 0.08,
    topY: 0.45,
    bottomY: 0.72,
    settleTiltDeg: 8,
    settleYOffset: 0.012,
    swayTiltDeg: 1.6,
    swayYOffset: 0.0035,
  },
  behaviorRepeatLimit: 2,
} as const;


function randomBetween(min: number, max: number) {
  return min + Math.random() * (max - min);
}

function distance(a: StagePoint, b: StagePoint) {
  return Math.hypot(a.x - b.x, a.y - b.y);
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
  private cornerPhaseOffset = Math.random() * Math.PI;
  private lastBehavior: IdleBehavior = "none";
  private lastBehaviorStreak = 0;

  update(input: { mode: string; nowMs: number; bounds: StageBounds; currentPosition: StagePoint }): IdleBehaviorSnapshot {
    void input.bounds;
    const nextActivity: ActivityState = input.mode === "idle" ? "idle" : "active";

    if (nextActivity === "active") {
      this.lastActiveAtMs = input.nowMs;
      if (this.activityState === "idle") {
        this.cancelBehavior();
      }
      this.activityState = "active";
      return {
        activityState: "active",
        idleBehavior: "none",
        targetPosition: null,
        poseTiltDeg: 0,
        poseYOffset: 0,
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
      return this.updateWander(input.nowMs, input.currentPosition);
    }

    if (this.idleBehavior === "corner_rest") {
      return this.updateCornerRest(input.nowMs);
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
    this.cornerPhaseOffset = Math.random() * Math.PI;
  }

  private cancelBehavior() {
    this.behaviorAbortController?.abort();
    this.behaviorAbortController = null;
    this.idleBehavior = "none";
    this.behaviorTarget = null;
    this.cornerAnchor = null;
    this.behaviorPauseUntilMs = 0;
    this.behaviorMoveUntilMs = 0;
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

  private updateWander(nowMs: number, currentPosition: StagePoint): IdleBehaviorSnapshot {
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
        this.behaviorTarget = {
          x: randomBetween(IDLE_BEHAVIOR_TUNING.wander.viewportPaddingX, 1 - IDLE_BEHAVIOR_TUNING.wander.viewportPaddingX),
          y: randomBetween(IDLE_BEHAVIOR_TUNING.wander.minY, IDLE_BEHAVIOR_TUNING.wander.maxY),
        };
        this.behaviorMoveUntilMs =
          nowMs + randomBetween(IDLE_BEHAVIOR_TUNING.wander.moveDurationMs.min, IDLE_BEHAVIOR_TUNING.wander.moveDurationMs.max);
        this.behaviorPauseUntilMs =
          this.behaviorMoveUntilMs + randomBetween(IDLE_BEHAVIOR_TUNING.wander.pauseMs.min, IDLE_BEHAVIOR_TUNING.wander.pauseMs.max);
      }
    }

    return {
      activityState: "idle",
      idleBehavior: "wander",
      targetPosition: this.behaviorTarget,
      poseTiltDeg: 0.8 * Math.sin(nowMs * 0.0005),
      poseYOffset: 0,
      movementWillingness: 0.3,
    };
  }

  private updateCornerRest(nowMs: number): IdleBehaviorSnapshot {
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
      const top = Math.random() < 0.5;
      const left = Math.random() < 0.5;
      this.cornerAnchor = {
        x: left ? IDLE_BEHAVIOR_TUNING.cornerRest.viewportPaddingX : 1 - IDLE_BEHAVIOR_TUNING.cornerRest.viewportPaddingX,
        y: top ? IDLE_BEHAVIOR_TUNING.cornerRest.topY : IDLE_BEHAVIOR_TUNING.cornerRest.bottomY,
      };
      this.behaviorTarget = this.cornerAnchor;
    }

    const phase = nowMs * 0.0011 + this.cornerPhaseOffset;
    const settledTilt = this.cornerAnchor.x < 0.5 ? IDLE_BEHAVIOR_TUNING.cornerRest.settleTiltDeg : -IDLE_BEHAVIOR_TUNING.cornerRest.settleTiltDeg;

    return {
      activityState: "idle",
      idleBehavior: "corner_rest",
      targetPosition: this.cornerAnchor,
      poseTiltDeg: settledTilt + Math.sin(phase) * IDLE_BEHAVIOR_TUNING.cornerRest.swayTiltDeg,
      poseYOffset: IDLE_BEHAVIOR_TUNING.cornerRest.settleYOffset + Math.cos(phase * 0.8) * IDLE_BEHAVIOR_TUNING.cornerRest.swayYOffset,
      movementWillingness: 0.12,
    };
  }

  getCurrentState() {
    return {
      activityState: this.activityState,
      idleBehavior: this.idleBehavior,
    };
  }
}
