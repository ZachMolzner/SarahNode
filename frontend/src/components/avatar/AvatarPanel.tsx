import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Canvas } from "@react-three/fiber";
import { VRMAvatar } from "./VRMAvatar";
import type { AvatarState } from "../../types/avatar";

type AvatarPanelProps = {
  avatarState: AvatarState;
  latestReplyText?: string;
};

export function AvatarPanel({ avatarState, latestReplyText }: AvatarPanelProps) {
  const [modelState, setModelState] = useState<"loading" | "ready" | "error">("loading");
  const canvasWrapRef = useRef<HTMLDivElement | null>(null);
  const pointerTargetRef = useRef({ x: 0, y: 0 });
  const [isNarrowViewport, setIsNarrowViewport] = useState(() =>
    typeof window !== "undefined" ? window.innerWidth <= 860 : false
  );

  const pointerTarget = useMemo(() => pointerTargetRef.current, []);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const mediaQuery = window.matchMedia("(max-width: 860px)");
    const updateViewportMatch = () => {
      setIsNarrowViewport(mediaQuery.matches);
    };

    updateViewportMatch();

    mediaQuery.addEventListener("change", updateViewportMatch);
    return () => {
      mediaQuery.removeEventListener("change", updateViewportMatch);
    };
  }, []);

  const camera = isNarrowViewport
    ? { position: [0, 1.2, 2.6] as [number, number, number], fov: 42 }
    : { position: [0, 1.1, 2.2] as [number, number, number], fov: 36 };

  const updatePointerTarget = (clientX: number, clientY: number) => {
    const bounds = canvasWrapRef.current?.getBoundingClientRect();
    if (!bounds) return;

    const normalizedX = ((clientX - bounds.left) / bounds.width) * 2 - 1;
    const normalizedY = -(((clientY - bounds.top) / bounds.height) * 2 - 1);

    pointerTargetRef.current.x = Math.max(-1, Math.min(1, normalizedX));
    pointerTargetRef.current.y = Math.max(-1, Math.min(1, normalizedY));
  };

  return (
    <section style={panelStyle}>
      <h2 style={{ marginTop: 0 }}>Avatar Panel</h2>
      <p style={{ marginTop: 0, opacity: 0.85 }}>
        Browser-native VRM avatar that reacts to live assistant websocket events.
      </p>

      <div
        ref={canvasWrapRef}
        style={canvasWrapStyle}
        onPointerMove={(event) => updatePointerTarget(event.clientX, event.clientY)}
        onPointerLeave={() => {
          pointerTargetRef.current.x = 0;
          pointerTargetRef.current.y = 0;
        }}
      >
        <Canvas
          camera={camera}
          dpr={[1, 1.5]}
          gl={{ antialias: true, alpha: true, powerPreference: "default" }}
        >
          <hemisphereLight args={["#e9f4ff", "#12141d", 0.72]} />
          <directionalLight color="#ffd9b0" position={[2.4, 3.2, 2]} intensity={1.1} />
          <directionalLight color="#a9bbff" position={[-2.2, 2, -2.6]} intensity={0.3} />
          <VRMAvatar
            avatarState={avatarState}
            onModelStateChange={setModelState}
            pointerTarget={pointerTarget}
            isNarrowViewport={isNarrowViewport}
          />
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
