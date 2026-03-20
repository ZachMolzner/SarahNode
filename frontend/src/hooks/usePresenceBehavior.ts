import { useCallback, useRef } from "react";
import type { MovementState, StagePoint } from "../lib/movementController";
import { PresenceController, type PresenceOutput, type SemanticPresenceMode } from "../lib/presenceController";
import type { OverlayVisibility } from "../lib/stageZones";

export type PresenceSignals = {
  transcriptEventAtMs: number;
  userSpokeAtMs: number;
  replyAtMs: number;
  presentingAtMs: number;
  searchHeadingRevealAtMs: number;
  searchFindingsRevealAtMs: number;
  searchSourcesRevealAtMs: number;
  searchSettledAtMs: number;
  semanticMode: SemanticPresenceMode;
};

export type PresenceBehaviorInput = {
  mode: MovementState;
  overlays: OverlayVisibility;
  bounds: { width: number; height: number };
  nowMs: number;
  deltaSeconds: number;
  currentPosition: StagePoint;
  signals: PresenceSignals;
};

export function usePresenceBehavior() {
  const controllerRef = useRef<PresenceController>(new PresenceController());

  return useCallback((input: PresenceBehaviorInput): PresenceOutput => {
    return controllerRef.current.update({
      mode: input.mode,
      overlays: input.overlays,
      bounds: input.bounds,
      currentPosition: input.currentPosition,
      nowMs: input.nowMs,
      deltaSeconds: input.deltaSeconds,
      transcriptEventAtMs: input.signals.transcriptEventAtMs,
      userSpokeAtMs: input.signals.userSpokeAtMs,
      replyAtMs: input.signals.replyAtMs,
      presentingAtMs: input.signals.presentingAtMs,
      searchHeadingRevealAtMs: input.signals.searchHeadingRevealAtMs,
      searchFindingsRevealAtMs: input.signals.searchFindingsRevealAtMs,
      searchSourcesRevealAtMs: input.signals.searchSourcesRevealAtMs,
      searchSettledAtMs: input.signals.searchSettledAtMs,
      semanticMode: input.signals.semanticMode,
    });
  }, []);
}
