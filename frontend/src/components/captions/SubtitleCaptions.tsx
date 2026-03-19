import { type CSSProperties, useEffect, useState } from "react";

type SubtitleCaptionsProps = {
  speaker: "sarah" | "user" | null;
  text: string;
  onVisibilityChange?: (visible: boolean) => void;
};

const CAPTION_TTL_MS = 5200;

export function SubtitleCaptions({ speaker, text, onVisibilityChange }: SubtitleCaptionsProps) {
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

  return (
    <div style={{ ...containerStyle, opacity: visible ? 1 : 0 }} aria-live="polite" aria-atomic="true">
      <span style={speakerStyle}>{speaker === "user" ? "You" : "Sarah"}</span>
      <p style={textStyle}>{text}</p>
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
