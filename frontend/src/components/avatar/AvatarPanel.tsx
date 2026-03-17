import { type CSSProperties } from "react";
import type { AvatarState } from "../../types/avatar";
import { VRMAvatar } from "./VRMAvatar";

type AvatarPanelProps = {
  avatarState: AvatarState;
  latestReplyText?: string;
};

export function AvatarPanel({ avatarState, latestReplyText }: AvatarPanelProps) {
  return (
    <section style={panelStyle}>
      <h2 style={{ marginTop: 0 }}>Sarah Avatar</h2>
      <p style={{ marginTop: 0, opacity: 0.85 }}>
        Sarah.vrm loads automatically from <code>/assets/Sarah.vrm</code>. The avatar idles, blinks, and enters a
        talking state during responses.
      </p>

      <VRMAvatar avatarState={avatarState} />

      <div style={metaStyle}>
        <span>Mode: {avatarState.mode}</span>
        <span>Mood: {avatarState.mood}</span>
        <span>Voice: {avatarState.isSpeaking ? "active" : "idle"}</span>
      </div>

      <p style={{ marginBottom: 0, marginTop: 12, opacity: 0.85 }}>
        Latest reply: {typeof latestReplyText === "string" ? latestReplyText : "No reply yet."}
      </p>
    </section>
  );
}

const panelStyle: CSSProperties = {
  border: "1px solid #2a2a2a",
  borderRadius: 12,
  padding: 14,
  background: "#161616",
};

const metaStyle: CSSProperties = {
  display: "flex",
  gap: 12,
  flexWrap: "wrap",
  marginTop: 12,
  fontSize: 14,
  opacity: 0.95,
};
