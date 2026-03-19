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
};

export function AvatarPanel({
  avatarState,
  overlayVisibility,
  presenceSignals,
  gesturePerformance,
  displayMode,
  reducedEffects = false,
  onInteractionRegionReady,
}: AvatarPanelProps) {
  const stageRef = useRef<HTMLElement | null>(null);
  const interactionRegionRef = useRef<HTMLDivElement | null>(null);
  const stageMotion = useStageController(avatarState.mode, stageRef, {
    overlays: overlayVisibility,
    signals: presenceSignals,
    displayMode,
  });

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

  const showCinematicBackdrop = displayMode.activeMode === "immersive" && !reducedEffects;
  const isOverlayGrounded = displayMode.activeMode === "overlay";
  const glowIntensity = showCinematicBackdrop ? 1 + gesturePerformance.glowBoost : 0.18;

  return (
    <section ref={stageRef} style={stageStyle}>
      {showCinematicBackdrop ? <div style={backdropLayerStyle} /> : null}
      {showCinematicBackdrop ? <div style={vignetteLayerStyle} /> : null}
      {showCinematicBackdrop ? (
        <div
          style={{
            ...spotlightLayerStyle,
            background: `radial-gradient(circle at 50% 50%, ${glowColor} 0%, rgba(10, 13, 24, 0.02) 60%, transparent 78%)`,
            opacity: Math.min(1, 0.82 * glowIntensity),
            transform: `${stageMotion.transform} scale(${Math.min(1.08, 0.98 + glowIntensity * 0.04)}) translateZ(0)`,
          }}
        />
      ) : null}

      <div
        ref={interactionRegionRef}
          style={{
            ...interactionRegionStyle,
            top: isOverlayGrounded ? "72%" : interactionRegionStyle.top,
            height: isOverlayGrounded ? "min(58vh, 620px)" : reducedEffects ? "min(74vh, 760px)" : interactionRegionStyle.height,
          }}
          aria-label="Sarah interaction region"
      >
        <div
          style={{
            ...avatarAnchorStyle,
            transform: `${stageMotion.transform} scaleX(${stageMotion.facingDirection})`,
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

      {displayMode.activeMode === "immersive" ? (
        <div style={metaStyle}>
          <span>
            Sarah • {stageMotion.movementState.replace("_", " ")} • {stageMotion.preferredZone.replace("_", " ")}
          </span>
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

const backdropLayerStyle: CSSProperties = {
  position: "absolute",
  inset: 0,
  background:
    "linear-gradient(180deg, #141c33 0%, #0b1020 35%, #070a14 65%, #04060d 100%), radial-gradient(circle at 25% 20%, rgba(79, 112, 186, 0.25), transparent 45%)",
};

const vignetteLayerStyle: CSSProperties = {
  position: "absolute",
  inset: 0,
  background: "radial-gradient(circle at 50% 55%, rgba(13, 17, 31, 0.03), rgba(4, 6, 12, 0.72) 85%)",
};

const spotlightLayerStyle: CSSProperties = {
  position: "absolute",
  left: "50%",
  top: "57%",
  width: "min(66vw, 540px)",
  height: "min(66vw, 540px)",
  filter: "blur(5px)",
  pointerEvents: "none",
};

const interactionRegionStyle: CSSProperties = {
  position: "absolute",
  left: "50%",
  top: "57%",
  width: "min(68vw, 640px)",
  height: "min(88vh, 920px)",
  transform: "translate(-50%, -50%)",
  pointerEvents: "none",
};

const avatarAnchorStyle: CSSProperties = {
  position: "absolute",
  left: "50%",
  top: "50%",
  width: "min(62vw, 560px)",
  height: "min(84vh, 860px)",
  maxHeight: "86vh",
  transform: "translate(-50%, -50%)",
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
