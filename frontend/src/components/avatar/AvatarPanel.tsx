import { type CSSProperties, useEffect, useRef } from "react";
import type { AvatarState } from "../../types/avatar";
import type { GesturePerformanceSnapshot } from "../../lib/gestureController";
import { VRMAvatar } from "./VRMAvatar";
import type { OverlayVisibility } from "../../lib/stageZones";
import type { PresenceSignals } from "../../lib/presenceSignals";
import type { DisplayModeState } from "../../lib/displayMode";

type AvatarPanelProps = {
  avatarState: AvatarState;
  overlayVisibility: OverlayVisibility;
  presenceSignals: PresenceSignals;
  gesturePerformance: GesturePerformanceSnapshot;
  displayMode: DisplayModeState;
  reducedEffects?: boolean;
  onInteractionRegionReady?: (element: HTMLElement | null) => void;
  onDragStateChange?: (dragging: boolean) => void;
  debugMotionEnabled?: boolean;
};

export function AvatarPanel({
  avatarState,
  gesturePerformance,
  reducedEffects = false,
  onInteractionRegionReady,
}: AvatarPanelProps) {
  const interactionRegionRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    onInteractionRegionReady?.(interactionRegionRef.current);
    return () => onInteractionRegionReady?.(null);
  }, [onInteractionRegionReady]);

  return (
    <section style={stageStyle}>
      <div
        ref={interactionRegionRef}
        style={interactionRegionStyle}
        aria-label="Sarah interaction region"
      >
        <div style={avatarFrameStyle}>
          <VRMAvatar
            avatarState={avatarState}
            stageMotion={{
              transform: "translate3d(0,0,0)",
              bob: 0,
              lean: 0,
              engagementLevel: 0,
              perchDepth: 0,
              recoveryLift: 0,
              isGroundedOverlay: false,
              landingCompression: 0,
              attentionOffset: { x: 0, y: 0 },
              edgeLean: 0,
              landingReaction: 0,
              facingDirection: 1,
              isDragActive: false,
              movementState: "idle",
              idleBehavior: "still",
              preferredZone: "center",
              characterMotionState: "idle",
              interactionPresenceState: "present",
              activityState: "idle",
              floorPosition: { x: 0, y: 0 },
              semanticPresenceMode: "idle",
            }}
            gesturePerformance={gesturePerformance}
            reducedEffects={reducedEffects}
          />
        </div>
      </div>
    </section>
  );
}

const stageStyle: CSSProperties = {
  width: "100%",
  height: "100%",
  minHeight: "100vh",
  position: "relative",
  background: "transparent",
};

const interactionRegionStyle: CSSProperties = {
  position: "absolute",
  left: "50%",
  top: "54%",
  width: "min(440px, 92vw)",
  height: "min(620px, 82vh)",
  transform: "translate(-50%, -50%)",
  zIndex: 20,
};

const avatarFrameStyle: CSSProperties = {
  width: "100%",
  height: "100%",
  background: "transparent",
};