import { getCurrentWindow } from "@tauri-apps/api/window";
import type { DisplayModeState } from "./displayMode";

export type OverlayInteractionConfig = {
  hitRegionPaddingPx: number;
  hoverEnableDelayMs: number;
  clickThroughRestoreDelayMs: number;
};

const DEFAULT_OVERLAY_CONFIG: OverlayInteractionConfig = {
  hitRegionPaddingPx: 48,
  hoverEnableDelayMs: 45,
  clickThroughRestoreDelayMs: 180,
};

function clampValue(value: number, min: number) {
  return Math.max(min, value);
}

export class OverlayController {
  private readonly mode: DisplayModeState;
  private readonly config: OverlayInteractionConfig;
  private interactionRegion: HTMLElement | null = null;
  private secondaryInteractionRegion: HTMLElement | null = null;
  private started = false;
  private ignoreCursorEvents = false;
  private enableTimer: number | null = null;
  private restoreTimer: number | null = null;
  private forceInteractive = false;

  constructor(mode: DisplayModeState, config?: Partial<OverlayInteractionConfig>) {
    this.mode = mode;
    this.config = {
      hitRegionPaddingPx: clampValue(config?.hitRegionPaddingPx ?? DEFAULT_OVERLAY_CONFIG.hitRegionPaddingPx, 0),
      hoverEnableDelayMs: clampValue(config?.hoverEnableDelayMs ?? DEFAULT_OVERLAY_CONFIG.hoverEnableDelayMs, 0),
      clickThroughRestoreDelayMs: clampValue(
        config?.clickThroughRestoreDelayMs ?? DEFAULT_OVERLAY_CONFIG.clickThroughRestoreDelayMs,
        0
      ),
    };
  }

  setInteractionRegion(element: HTMLElement | null) {
    this.interactionRegion = element;
  }

  setSecondaryInteractionRegion(element: HTMLElement | null) {
    this.secondaryInteractionRegion = element;
  }

  async start(): Promise<void> {
    if (this.started) return;
    this.started = true;

    if (!this.mode.nativeOverlayEnabled) return;

    window.addEventListener("pointermove", this.handlePointerMove);
    window.addEventListener("pointerleave", this.handlePointerLeave);
    window.addEventListener("blur", this.handleBlur);

    await this.setIgnoreCursorEvents(true);
  }

  async stop(): Promise<void> {
    if (!this.started) return;
    this.started = false;

    window.removeEventListener("pointermove", this.handlePointerMove);
    window.removeEventListener("pointerleave", this.handlePointerLeave);
    window.removeEventListener("blur", this.handleBlur);

    this.clearTimers();
    await this.setIgnoreCursorEvents(false);
  }

  async setForceInteractive(active: boolean): Promise<void> {
    this.forceInteractive = active;
    if (!this.mode.nativeOverlayEnabled) return;
    if (active) {
      this.clearTimers();
      await this.setIgnoreCursorEvents(false);
      return;
    }
    await this.setIgnoreCursorEvents(true);
  }

  private clearTimers() {
    if (this.enableTimer !== null) {
      window.clearTimeout(this.enableTimer);
      this.enableTimer = null;
    }

    if (this.restoreTimer !== null) {
      window.clearTimeout(this.restoreTimer);
      this.restoreTimer = null;
    }
  }

  private async setIgnoreCursorEvents(nextValue: boolean): Promise<void> {
    if (!this.mode.nativeOverlayEnabled || this.ignoreCursorEvents === nextValue) return;

    try {
      const appWindow = getCurrentWindow();
      if (nextValue) {
        await appWindow.setIgnoreCursorEvents(true, { forward: true });
      } else {
        await appWindow.setIgnoreCursorEvents(false);
      }
      this.ignoreCursorEvents = nextValue;
    } catch {
      // Keep browser and non-supported runtimes stable.
    }
  }

  private isPointerInsideRegion(clientX: number, clientY: number): boolean {
    const padding = this.config.hitRegionPaddingPx;
    const regions = [this.interactionRegion, this.secondaryInteractionRegion].filter((region): region is HTMLElement => Boolean(region));
    return regions.some((region) => {
      const rect = region.getBoundingClientRect();
      return (
        clientX >= rect.left - padding &&
        clientX <= rect.right + padding &&
        clientY >= rect.top - padding &&
        clientY <= rect.bottom + padding
      );
    });
  }

  private readonly handlePointerMove = (event: PointerEvent) => {
    if (!this.mode.nativeOverlayEnabled) return;
    if (this.forceInteractive) return;

    const inRegion = this.isPointerInsideRegion(event.clientX, event.clientY);

    if (inRegion) {
      if (this.restoreTimer !== null) {
        window.clearTimeout(this.restoreTimer);
        this.restoreTimer = null;
      }

      if (this.ignoreCursorEvents && this.enableTimer === null) {
        this.enableTimer = window.setTimeout(() => {
          this.enableTimer = null;
          void this.setIgnoreCursorEvents(false);
        }, this.config.hoverEnableDelayMs);
      }
      return;
    }

    if (this.enableTimer !== null) {
      window.clearTimeout(this.enableTimer);
      this.enableTimer = null;
    }

    if (!this.ignoreCursorEvents && this.restoreTimer === null) {
      this.restoreTimer = window.setTimeout(() => {
        this.restoreTimer = null;
        void this.setIgnoreCursorEvents(true);
      }, this.config.clickThroughRestoreDelayMs);
    }
  };

  private readonly handlePointerLeave = () => {
    if (!this.mode.nativeOverlayEnabled) return;
    if (this.forceInteractive) return;

    if (this.restoreTimer !== null) {
      window.clearTimeout(this.restoreTimer);
    }

    this.restoreTimer = window.setTimeout(() => {
      this.restoreTimer = null;
      void this.setIgnoreCursorEvents(true);
    }, this.config.clickThroughRestoreDelayMs);
  };

  private readonly handleBlur = () => {
    if (!this.mode.nativeOverlayEnabled) return;
    if (this.forceInteractive) return;
    void this.setIgnoreCursorEvents(true);
  };
}
