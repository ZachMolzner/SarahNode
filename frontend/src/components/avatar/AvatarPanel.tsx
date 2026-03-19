import { type CSSProperties, useMemo, useRef } from "react";
import type { AvatarState } from "../../types/avatar";
import { VRMAvatar } from "./VRMAvatar";
import { useStageController } from "../../lib/stageController";

type AvatarPanelProps = {
  avatarState: AvatarState;
};

export function AvatarPanel({ avatarState }: AvatarPanelProps) {
  const stageRef = useRef<HTMLElement | null>(null);
  const stageMotion = useStageController(avatarState.mode, stageRef);

  const glowColor = useMemo(() => {
    if (avatarState.mode === "shutting_down") return "rgba(151, 126, 190, 0.26)";
    if (avatarState.mode === "talking") return "rgba(125, 190, 255, 0.3)";
    if (avatarState.mode === "listening") return "rgba(124, 221, 201, 0.26)";
    if (avatarState.mode === "thinking") return "rgba(186, 169, 255, 0.24)";
    return "rgba(145, 167, 255, 0.2)";
  }, [avatarState.mode]);

  return (
    <section ref={stageRef} style={stageStyle}>
      <div style={backdropLayerStyle} />
      <div style={vignetteLayerStyle} />
      <div
        style={{
          ...spotlightLayerStyle,
          background: `radial-gradient(circle at 50% 50%, ${glowColor} 0%, rgba(10, 13, 24, 0.02) 60%, transparent 78%)`,
          transform: `${stageMotion.transform} translateZ(0)`,
        }}
      />

      <div
        style={{
          ...avatarAnchorStyle,
          transform: `${stageMotion.transform} scaleX(${stageMotion.facingDirection})`,
        }}
      >
        <VRMAvatar avatarState={avatarState} stageMotion={stageMotion} />
      </div>

      <div style={metaStyle}>
        <span>Sarah • {stageMotion.movementState.replace("_", " ")}</span>
      </div>
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

const avatarAnchorStyle: CSSProperties = {
  position: "absolute",
  left: "50%",
  top: "57%",
  width: "min(62vw, 560px)",
  height: "min(84vh, 860px)",
  maxHeight: "86vh",
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
