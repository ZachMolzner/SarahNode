import { type CSSProperties, useEffect, useState } from "react";
import type { DisplayMode } from "../../lib/displayMode";

type SubtitleCaptionsProps = {
  speaker: "sarah" | "user" | null;
  text: string;
  displayMode?: DisplayMode;
  onVisibilityChange?: (visible: boolean) => void;
};

const CAPTION_TTL_MS = 5200;

export function SubtitleCaptions({ speaker, text, displayMode = "immersive", onVisibilityChange }: SubtitleCaptionsProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!text.trim()) {
      setVisible(false);
      onVisibilityChange?.(false);
      return;
    }

    setVisible(true);
    onVisibilityChange?.(true);
    const hideTimer = window.setTimeout(() => setVisible(false), CAPTION_TTL_MS);
    return () => window.clearTimeout(hideTimer);
  }, [onVisibilityChange, text]);

  useEffect(() => {
    onVisibilityChange?.(visible);
  }, [onVisibilityChange, visible]);

  if (!text.trim()) return null;

  const isOverlay = displayMode === "overlay";

  return (
    <div
      style={{
        ...containerStyle,
        ...(isOverlay ? overlayContainerStyle : null),
        opacity: visible ? 1 : 0,
      }}
      aria-live="polite"
      aria-atomic="true"
    >
      <span style={speakerStyle}>{speaker === "user" ? "You" : "Sarah"}</span>
      <p style={{ ...textStyle, ...(isOverlay ? overlayTextStyle : null) }}>{text}</p>
    </div>
  );
}

const containerStyle: CSSProperties = {
  position: "absolute",
  left: "50%",
  bottom: 92,
  transform: "translateX(-50%)",
  maxWidth: "min(840px, calc(100vw - 36px))",
  padding: "8px 14px 10px",
  borderRadius: 12,
  border: "1px solid rgba(194, 208, 255, 0.25)",
  background: "linear-gradient(180deg, rgba(8, 10, 18, 0.62), rgba(8, 10, 18, 0.42))",
  backdropFilter: "blur(6px)",
  color: "#f2f5ff",
  textAlign: "center",
  transition: "opacity 280ms ease",
  zIndex: 18,
  pointerEvents: "none",
};

const overlayContainerStyle: CSSProperties = {
  maxWidth: "min(620px, calc(100vw - 28px))",
  padding: "6px 10px 8px",
  border: "1px solid rgba(194, 208, 255, 0.14)",
  background: "rgba(8, 10, 18, 0.28)",
  backdropFilter: "blur(3px)",
};

const speakerStyle: CSSProperties = {
  display: "inline-block",
  opacity: 0.75,
  textTransform: "uppercase",
  fontSize: 11,
  letterSpacing: 1.2,
};

const textStyle: CSSProperties = {
  margin: "4px 0 0",
  fontSize: "clamp(14px, 2.2vw, 18px)",
  lineHeight: 1.35,
  textShadow: "0 2px 14px rgba(0,0,0,0.55)",
};

const overlayTextStyle: CSSProperties = {
  textShadow: "0 1px 8px rgba(0,0,0,0.4)",
};
