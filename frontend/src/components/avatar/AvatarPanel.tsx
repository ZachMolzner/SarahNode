import { type CSSProperties, useEffect, useMemo, useRef } from "react";
import type { AvatarState } from "../../types/avatar";
import type { GesturePerformanceSnapshot } from "../../lib/gestureController";
import { VRMAvatar } from "./VRMAvatar";
import { useStageController } from "../../lib/stageController";
import type { OverlayVisibility } from "../../lib/stageZones";
import type { PresenceSignals } from "../../hooks/usePresenceBehavior";
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
  overlayVisibility,
  presenceSignals,
  gesturePerformance,
  displayMode,
  reducedEffects = false,
  onInteractionRegionReady,
  onDragStateChange,
  debugMotionEnabled = false,
}: AvatarPanelProps) {
  const stageRef = useRef<HTMLElement | null>(null);
  const interactionRegionRef = useRef<HTMLDivElement | null>(null);
  const stageMotion = useStageController(avatarState.mode, stageRef, {
    overlays: overlayVisibility,
    signals: presenceSignals,
    displayMode,
  }, { onDragStateChange });

  useEffect(() => {
    onInteractionRegionReady?.(interactionRegionRef.current);
    return () => onInteractionRegionReady?.(null);
  }, [onInteractionRegionReady]);

  const glowColor = useMemo(() => {
    if (avatarState.reaction === "searching") return "rgba(175, 148, 255, 0.3)";
    if (avatarState.reaction === "confident_result") return "rgba(109, 211, 255, 0.32)";
    if (avatarState.reaction === "uncertain_result") return "rgba(255, 176, 144, 0.3)";
    if (avatarState.reaction === "listening_ready") return "rgba(135, 228, 214, 0.28)";
    if (avatarState.reaction === "interrupted") return "rgba(255, 188, 127, 0.3)";
    if (avatarState.mode === "shutting_down") return "rgba(151, 126, 190, 0.26)";
    if (avatarState.mode === "talking") return "rgba(125, 190, 255, 0.3)";
    if (avatarState.mode === "listening") return "rgba(124, 221, 201, 0.26)";
    if (avatarState.mode === "thinking") return "rgba(186, 169, 255, 0.24)";
    return "rgba(145, 167, 255, 0.2)";
  }, [avatarState.mode, avatarState.reaction]);

  const isOverlayGrounded = displayMode.activeMode === "overlay";
  const overlayScaleBoost = isOverlayGrounded ? 1.08 : 1;
  const dynamicAvatarScale = useMemo(() => {
    if (avatarState.mode === "idle") return 0.78;
    if (avatarState.mode === "listening" || avatarState.mode === "thinking") return 0.83;
    if (avatarState.mode === "talking" || avatarState.mode === "presenting") return 0.88;
    if (avatarState.mode === "presenting_search_results") return 0.9;
    if (avatarState.mode === "shutting_down") return 0.8;
    return 0.83;
  }, [avatarState.mode]);

  const glowIntensity = Math.min(0.35, 0.18 + gesturePerformance.glowBoost * 0.16);

  return (
    <section ref={stageRef} style={stageStyle}>
      <div
        style={{
          ...spotlightLayerStyle,
          background: `radial-gradient(circle at 50% 50%, ${glowColor} 0%, rgba(10, 13, 24, 0.01) 58%, transparent 76%)`,
          opacity: isOverlayGrounded ? 0 : glowIntensity,
          transform: `${stageMotion.transform} scale(0.94) translateZ(0)`,
        }}
      />

      <div
        ref={interactionRegionRef}
          style={{
            ...interactionRegionStyle,
            left: isOverlayGrounded ? "77%" : interactionRegionStyle.left,
            top: isOverlayGrounded ? "72%" : interactionRegionStyle.top,
            width: isOverlayGrounded ? "min(35vw, 380px)" : interactionRegionStyle.width,
            height: isOverlayGrounded ? "min(52vh, 540px)" : reducedEffects ? "min(52vh, 520px)" : interactionRegionStyle.height,
            pointerEvents: isOverlayGrounded ? "auto" : "none",
            cursor: isOverlayGrounded ? (stageMotion.isDragActive ? "grabbing" : "grab") : "default",
          }}
          aria-label="Sarah interaction region"
      >
        <div
          style={{
            ...avatarMotionStyle,
            transform: `${stageMotion.transform} scale(${dynamicAvatarScale * overlayScaleBoost})`,
            transition: "transform 380ms cubic-bezier(0.22, 0.61, 0.36, 1)",
          }}
        >
          <div
            style={{
              ...avatarAnchorStyle,
              transform: `translate(-50%, -50%) scaleX(${stageMotion.facingDirection})`,
            }}
          >
            <VRMAvatar
              avatarState={avatarState}
              stageMotion={stageMotion}
              gesturePerformance={gesturePerformance}
              reducedEffects={reducedEffects}
            />
          </div>
        </div>
      </div>

      {displayMode.activeMode === "immersive" ? (
        <div style={metaStyle}>
          <span>
            Sarah • {stageMotion.movementState.replace("_", " ")} • {stageMotion.idleBehavior.replace("_", " ")} • {stageMotion.preferredZone.replace("_", " ")}
          </span>
        </div>
      ) : null}
      {debugMotionEnabled ? (
        <div style={debugOverlayStyle}>
          motion: {stageMotion.characterMotionState} • presence: {stageMotion.interactionPresenceState} • activity: {stageMotion.activityState} • idle: {stageMotion.idleBehavior} • floor: {stageMotion.floorPosition.x.toFixed(2)}, {stageMotion.floorPosition.y.toFixed(2)} • drag:{" "}
          {stageMotion.isDragActive ? "on" : "off"}
        </div>
      ) : null}
    </section>
  );
}

const stageStyle: CSSProperties = {
  width: "100%",
  height: "100%",
  position: "relative",
  isolation: "isolate",
};

const spotlightLayerStyle: CSSProperties = {
  position: "absolute",
  left: "50%",
  top: "62%",
  width: "min(46vw, 340px)",
  height: "min(46vw, 340px)",
  filter: "blur(6px)",
  pointerEvents: "none",
};

const interactionRegionStyle: CSSProperties = {
  position: "absolute",
  left: "50%",
  top: "64%",
  width: "min(52vw, 460px)",
  height: "min(54vh, 560px)",
  transform: "translate(-50%, -50%)",
  pointerEvents: "none",
};

const avatarMotionStyle: CSSProperties = {
  position: "absolute",
  inset: 0,
};

const avatarAnchorStyle: CSSProperties = {
  position: "absolute",
  left: "50%",
  top: "51%",
  width: "min(24vw, 270px)",
  height: "min(48vh, 450px)",
  maxHeight: "50vh",
};

const metaStyle: CSSProperties = {
  position: "absolute",
  left: 14,
  bottom: 10,
  fontSize: 12,
  opacity: 0.7,
  letterSpacing: 0.3,
  textTransform: "uppercase",
};

const debugOverlayStyle: CSSProperties = {
  position: "absolute",
  left: 12,
  top: 12,
  fontSize: 11,
  color: "rgba(226, 235, 255, 0.9)",
  background: "rgba(8, 12, 22, 0.55)",
  border: "1px solid rgba(118, 145, 220, 0.4)",
  borderRadius: 10,
  padding: "4px 8px",
  pointerEvents: "none",
  zIndex: 22,
};
