import type { CSSProperties } from "react";
import type { AvatarState } from "../../types/avatar";

type VRMAvatarProps = {
  avatarState: AvatarState;
};

export function VRMAvatar({ avatarState }: VRMAvatarProps) {
  return (
    <div style={style}>
      Optional avatar renderer placeholder. Current mode: <strong>{avatarState.mode}</strong>
    </div>
  );
}

const style: CSSProperties = {
  padding: 12,
  borderRadius: 8,
  border: "1px dashed #4a4a4a",
};
