export type StagePoint = { x: number; y: number };

export type MovementState =
  | "idle"
  | "walking"
  | "listening"
  | "thinking"
  | "talking"
  | "presenting"
  | "presenting_search_results"
  | "shutting_down";

export type MovementSnapshot = {
  position: StagePoint;
  facingDirection: -1 | 1;
  isMoving: boolean;
  bob: number;
  lean: number;
  pace: number;
};

const EPSILON = 0.001;

export class MovementController {
  private current: StagePoint;
  private target: StagePoint;
  private velocity: StagePoint;
  private facingDirection: -1 | 1 = 1;

  constructor(initial: StagePoint) {
    this.current = { ...initial };
    this.target = { ...initial };
    this.velocity = { x: 0, y: 0 };
  }

  setTarget(target: StagePoint) {
    this.target = { ...target };
  }

  getCurrentPosition(): StagePoint {
    return { ...this.current };
  }

  update(deltaSeconds: number, movementState: MovementState, nowMs: number): MovementSnapshot {
    const accel = movementState === "walking" ? 7.4 : 11;
    const maxSpeed = movementState === "walking" ? 0.34 : 0.2;
    const damping = movementState === "walking" ? 0.8 : 0.68;

    const toTargetX = this.target.x - this.current.x;
    const toTargetY = this.target.y - this.current.y;
    const distance = Math.hypot(toTargetX, toTargetY);

    if (distance > EPSILON) {
      const normX = toTargetX / distance;
      const normY = toTargetY / distance;
      this.velocity.x += normX * accel * deltaSeconds;
      this.velocity.y += normY * accel * deltaSeconds;

      const speed = Math.hypot(this.velocity.x, this.velocity.y);
      if (speed > maxSpeed) {
        const ratio = maxSpeed / speed;
        this.velocity.x *= ratio;
        this.velocity.y *= ratio;
      }
    }

    this.velocity.x *= Math.pow(damping, deltaSeconds * 60);
    this.velocity.y *= Math.pow(damping, deltaSeconds * 60);

    this.current.x += this.velocity.x * deltaSeconds;
    this.current.y += this.velocity.y * deltaSeconds;

    const remainingX = this.target.x - this.current.x;
    const remainingY = this.target.y - this.current.y;
    const remainingDistance = Math.hypot(remainingX, remainingY);

    if (remainingDistance < 0.002) {
      this.current = { ...this.target };
      this.velocity = { x: 0, y: 0 };
    }

    const movementMagnitude = Math.hypot(this.velocity.x, this.velocity.y);
    const isMoving = movementMagnitude > 0.012;

    if (Math.abs(this.velocity.x) > 0.001) {
      this.facingDirection = this.velocity.x >= 0 ? 1 : -1;
    }

    const phase = nowMs / 170;
    const pace = isMoving ? (Math.sin(phase) * 0.5 + 0.5) : 0;
    const bob = isMoving ? Math.sin(phase) * 0.008 : 0;
    const lean = isMoving ? this.facingDirection * Math.min(0.04, movementMagnitude * 0.22) : 0;

    return {
      position: { ...this.current },
      facingDirection: this.facingDirection,
      isMoving,
      bob,
      lean,
      pace,
    };
  }
}
