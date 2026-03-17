import { useState, type CSSProperties } from "react";
import { Canvas } from "@react-three/fiber";
import { VRMAvatar } from "./VRMAvatar";
import type { AvatarState } from "../../types/avatar";

type AvatarPanelProps = {
  avatarState: AvatarState;
  latestReplyText?: string;
};

export function AvatarPanel({ avatarState, latestReplyText }: AvatarPanelProps) {
  const [modelState, setModelState] = useState<"loading" | "ready" | "error">("loading");

  return (
    <section style={panelStyle}>
      <h2 style={{ marginTop: 0 }}>Avatar Panel</h2>
      <p style={{ marginTop: 0, opacity: 0.85 }}>
        Browser-native VRM avatar that reacts to live assistant websocket events.
      </p>

      <div style={canvasWrapStyle}>
        <Canvas
          camera={{ position: [0, 1.1, 2.2], fov: 36 }}
          dpr={[1, 1.5]}
          gl={{ antialias: true, alpha: true, powerPreference: "default" }}
        >
          <ambientLight intensity={0.7} />
          <directionalLight position={[2, 3, 2]} intensity={1} />
          <directionalLight position={[-2, 2, -1]} intensity={0.45} />
          <VRMAvatar avatarState={avatarState} onModelStateChange={setModelState} />
        </Canvas>

        {modelState !== "ready" ? (
          <div style={fallbackStyle}>
            {modelState === "loading"
              ? "Loading avatar model..."
              : "No VRM model found yet. Add frontend/public/models/sarah.vrm to enable the avatar."}
          </div>
        ) : null}
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

const canvasWrapStyle: CSSProperties = {
  minHeight: 280,
  borderRadius: 12,
  overflow: "hidden",
  position: "relative",
  border: "1px solid #2a2a2a",
  background: "linear-gradient(180deg, #14161c 0%, #0f1014 100%)",
};

const fallbackStyle: CSSProperties = {
  position: "absolute",
  inset: 0,
  display: "grid",
  placeItems: "center",
  textAlign: "center",
  padding: 20,
  color: "#d8d8d8",
  background: "rgba(10, 10, 10, 0.55)",
};
