import { type CSSProperties } from "react";
import type { AvatarState } from "../../types/avatar";
import { VRMAvatar } from "./VRMAvatar";

type AvatarPanelProps = {
  avatarState: AvatarState;
};

export function AvatarPanel({ avatarState }: AvatarPanelProps) {
  return (
    <section style={stageStyle}>
      <VRMAvatar avatarState={avatarState} />
      <div style={metaStyle}>
        <span>Sarah • {avatarState.mode.replace("_", " ")}</span>
      </div>
    </section>
  );
}

const stageStyle: CSSProperties = {
  width: "100%",
  height: "100%",
  position: "relative",
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
