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
      <h2 style={{ marginTop: 0 }}>Presence / Avatar (Optional)</h2>
      <p style={{ marginTop: 0, opacity: 0.85 }}>
        Placeholder presence panel for future avatar integrations. Current mode and mood are driven by live assistant
        events.
      </p>

      <div style={placeholderShellStyle}>
        <VRMAvatar avatarState={avatarState} />
        <div style={orbStyle} aria-hidden>
          <div style={pulseStyle(avatarState.mode)} />
        </div>
        <div style={{ display: "grid", gap: 6 }}>
          <strong>Assistant Presence</strong>
          <span>Mode: {avatarState.mode}</span>
          <span>Mood: {avatarState.mood}</span>
          <span>Voice: {avatarState.isSpeaking ? "active" : "idle"}</span>
        </div>
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

const placeholderShellStyle: CSSProperties = {
  minHeight: 180,
  borderRadius: 12,
  border: "1px solid #2a2a2a",
  background: "linear-gradient(180deg, #14161c 0%, #0f1014 100%)",
  display: "flex",
  gap: 16,
  alignItems: "center",
  padding: 20,
};

const orbStyle: CSSProperties = {
  width: 86,
  height: 86,
  borderRadius: "50%",
  background: "radial-gradient(circle at 30% 30%, #6faaff 0%, #2456b6 55%, #122648 100%)",
  display: "grid",
  placeItems: "center",
  flexShrink: 0,
};

const pulseStyle = (mode: AvatarState["mode"]): CSSProperties => ({
  width: mode === "speaking" ? 56 : mode === "thinking" ? 48 : 40,
  height: mode === "speaking" ? 56 : mode === "thinking" ? 48 : 40,
  borderRadius: "50%",
  background: "rgba(255,255,255,0.75)",
  transition: "all 180ms ease",
});
