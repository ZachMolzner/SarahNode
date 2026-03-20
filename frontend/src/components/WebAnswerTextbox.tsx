import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { WebAnswerSource } from "../lib/webGroundedAnswer";

export type WebAnswerViewModel = {
  title: string;
  bullets: string[];
  sources: WebAnswerSource[];
  mode: "overlay" | "immersive";
};

type WebAnswerTextboxProps = {
  answer: WebAnswerViewModel | null;
  defaultCollapsedSources: boolean;
  visible: boolean;
  onInteractionChange: (interacting: boolean) => void;
  onSourceExpansionChange: (expanded: boolean) => void;
  onInteractionRegionReady?: (element: HTMLElement | null) => void;
};

export function WebAnswerTextbox({
  answer,
  defaultCollapsedSources,
  visible,
  onInteractionChange,
  onSourceExpansionChange,
  onInteractionRegionReady,
}: WebAnswerTextboxProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsedSources);
  const [hovered, setHovered] = useState(false);
  const [focusedWithin, setFocusedWithin] = useState(false);
  const [touchInteracting, setTouchInteracting] = useState(false);
  const rootRef = useRef<HTMLElement | null>(null);
  const touchTimerRef = useRef<number | null>(null);

  useEffect(() => {
    setCollapsed(defaultCollapsedSources);
  }, [answer?.title, answer?.bullets.join("|"), defaultCollapsedSources]);

  useEffect(() => {
    onSourceExpansionChange(!collapsed);
  }, [collapsed, onSourceExpansionChange]);

  useEffect(() => {
    onInteractionChange(hovered || focusedWithin || touchInteracting);
  }, [focusedWithin, hovered, onInteractionChange, touchInteracting]);

  useEffect(() => {
    return () => {
      if (touchTimerRef.current) {
        window.clearTimeout(touchTimerRef.current);
      }
    };
  }, []);

  function pulseTouchInteraction() {
    setTouchInteracting(true);
    if (touchTimerRef.current) {
      window.clearTimeout(touchTimerRef.current);
    }
    touchTimerRef.current = window.setTimeout(() => setTouchInteracting(false), 1400);
  }

  useEffect(() => {
    onInteractionRegionReady?.(rootRef.current);
    return () => onInteractionRegionReady?.(null);
  }, [onInteractionRegionReady]);

  const modeAwareStyle = useMemo(() => (answer?.mode === "overlay" ? overlayBoxStyle : immersiveBoxStyle), [answer?.mode]);

  if (!answer || !visible) return null;

  return (
    <aside
      ref={rootRef}
      style={{ ...boxStyle, ...modeAwareStyle }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocusCapture={() => setFocusedWithin(true)}
      onBlurCapture={(event) => {
        const nextTarget = event.relatedTarget as Node | null;
        if (!event.currentTarget.contains(nextTarget)) {
          setFocusedWithin(false);
        }
      }}
      onPointerDown={(event) => event.stopPropagation()}
      onClick={(event) => event.stopPropagation()}
      onTouchStart={() => pulseTouchInteraction()}
    >
      <div style={badgeStyle}>Checked live web</div>
      <h3 style={titleStyle}>{answer.title}</h3>
      <ul style={listStyle}>
        {answer.bullets.slice(0, 5).map((point, index) => (
          <li key={`${point}-${index}`}>{point}</li>
        ))}
      </ul>
      {answer.sources.length ? (
        <footer style={footerStyle}>
          <button type="button" style={footerToggleStyle} onClick={() => setCollapsed((value) => !value)}>
            {collapsed ? "View" : "Hide"} sources ({answer.sources.length})
          </button>
          {!collapsed ? (
            <ul style={sourceListStyle}>
              {answer.sources.map((source) => (
                <li key={`${source.title}-${source.url ?? "no-url"}`} style={sourceItemStyle}>
                  {source.url ? (
                    <a href={source.url} target="_blank" rel="noreferrer" style={sourceLinkStyle}>
                      {source.title}
                    </a>
                  ) : (
                    <span>{source.title}</span>
                  )}
                </li>
              ))}
            </ul>
          ) : null}
        </footer>
      ) : null}
    </aside>
  );
}

const boxStyle: CSSProperties = {
  position: "absolute",
  borderRadius: 14,
  padding: "12px 14px",
  background: "rgba(10, 15, 28, 0.86)",
  border: "1px solid rgba(127, 180, 255, 0.3)",
  color: "#f4f7ff",
  backdropFilter: "blur(10px)",
  boxShadow: "0 18px 48px rgba(2, 5, 12, 0.42)",
  zIndex: 24,
  lineHeight: 1.4,
  transition: "opacity 220ms ease, transform 260ms ease",
  pointerEvents: "auto",
  userSelect: "text",
  overflowY: "auto",
  maxHeight: "min(34vh, 300px)",
};

const overlayBoxStyle: CSSProperties = {
  left: "calc(50% + min(5vw, 56px))",
  top: "36%",
  width: "min(240px, 24vw)",
};

const immersiveBoxStyle: CSSProperties = {
  right: 26,
  top: "28%",
  width: "min(360px, 34vw)",
};

const badgeStyle: CSSProperties = {
  display: "inline-block",
  borderRadius: 999,
  padding: "2px 9px",
  fontSize: 10,
  border: "1px solid rgba(133, 201, 255, 0.35)",
  color: "#cae5fb",
  background: "rgba(40, 88, 132, 0.24)",
  textTransform: "uppercase",
  letterSpacing: 0.4,
};

const titleStyle: CSSProperties = {
  margin: "8px 0 10px",
  fontSize: 14,
  fontWeight: 620,
};

const listStyle: CSSProperties = {
  margin: 0,
  paddingLeft: 18,
  display: "grid",
  gap: 8,
  fontSize: 12,
};

const footerStyle: CSSProperties = {
  marginTop: 12,
  borderTop: "1px solid rgba(156, 175, 222, 0.24)",
  paddingTop: 9,
};

const footerToggleStyle: CSSProperties = {
  borderRadius: 8,
  border: "1px solid rgba(149, 171, 228, 0.34)",
  background: "rgba(31, 44, 79, 0.5)",
  color: "#eaf2ff",
  padding: "4px 9px",
  fontSize: 12,
};

const sourceListStyle: CSSProperties = {
  margin: "8px 0 0",
  paddingLeft: 18,
  display: "grid",
  gap: 4,
};

const sourceItemStyle: CSSProperties = {
  fontSize: 12,
  opacity: 0.82,
};

const sourceLinkStyle: CSSProperties = {
  color: "#cfe7ff",
};
