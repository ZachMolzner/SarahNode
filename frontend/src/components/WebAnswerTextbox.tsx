import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { WebAnswerSource } from "../lib/webGroundedAnswer";
import { buildWebAnswerReportLayout } from "../lib/webAnswerPresentation";

export type WebAnswerViewModel = {
  title: string;
  bullets: string[];
  sources: WebAnswerSource[];
  mode: "overlay" | "immersive";
};

export type WebAnswerRevealStage = 0 | 1 | 2 | 3;

type WebAnswerTextboxProps = {
  answer: WebAnswerViewModel | null;
  defaultCollapsedSources: boolean;
  visible: boolean;
  onInteractionChange: (interacting: boolean) => void;
  onSourceExpansionChange: (expanded: boolean) => void;
  onInteractionRegionReady?: (element: HTMLElement | null) => void;
  onRevealStageChange?: (stage: WebAnswerRevealStage) => void;
};

export function WebAnswerTextbox({
  answer,
  defaultCollapsedSources,
  visible,
  onInteractionChange,
  onSourceExpansionChange,
  onInteractionRegionReady,
  onRevealStageChange,
}: WebAnswerTextboxProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsedSources);
  const [hovered, setHovered] = useState(false);
  const [focusedWithin, setFocusedWithin] = useState(false);
  const [touchInteracting, setTouchInteracting] = useState(false);
  const [isMounted, setIsMounted] = useState(visible);
  const [isVisible, setIsVisible] = useState(visible);
  const [answerSnapshot, setAnswerSnapshot] = useState<WebAnswerViewModel | null>(answer);
  const rootRef = useRef<HTMLElement | null>(null);
  const touchTimerRef = useRef<number | null>(null);
  const visibilityTimerRef = useRef<number | null>(null);
  const revealTimersRef = useRef<number[]>([]);
  const [revealStage, setRevealStage] = useState<WebAnswerRevealStage>(0);

  const displayAnswer = answer ?? answerSnapshot;

  useEffect(() => {
    if (answer) setAnswerSnapshot(answer);
  }, [answer]);

  useEffect(() => {
    setCollapsed(defaultCollapsedSources);
  }, [displayAnswer?.title, displayAnswer?.bullets.join("|"), defaultCollapsedSources]);

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
      if (visibilityTimerRef.current) {
        window.clearTimeout(visibilityTimerRef.current);
      }
      revealTimersRef.current.forEach((timer) => window.clearTimeout(timer));
      revealTimersRef.current = [];
    };
  }, []);

  useEffect(() => {
    if (visibilityTimerRef.current) {
      window.clearTimeout(visibilityTimerRef.current);
      visibilityTimerRef.current = null;
    }
    if (visible) {
      setIsMounted(true);
      visibilityTimerRef.current = window.setTimeout(() => setIsVisible(true), 16);
      return;
    }
    setIsVisible(false);
    visibilityTimerRef.current = window.setTimeout(() => {
      setIsMounted(false);
      setHovered(false);
      setFocusedWithin(false);
      setTouchInteracting(false);
    }, WEB_ANSWER_TRANSITION_MS.exitDuration);
  }, [visible]);

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

  useEffect(() => {
    onRevealStageChange?.(revealStage);
  }, [onRevealStageChange, revealStage]);

  useEffect(() => {
    revealTimersRef.current.forEach((timer) => window.clearTimeout(timer));
    revealTimersRef.current = [];

    if (!visible || !displayAnswer) {
      setRevealStage(0);
      return;
    }

    setRevealStage(0);
    revealTimersRef.current.push(window.setTimeout(() => setRevealStage(1), WEB_ANSWER_REVEAL_MS.header));
    revealTimersRef.current.push(window.setTimeout(() => setRevealStage(2), WEB_ANSWER_REVEAL_MS.findings));
    revealTimersRef.current.push(window.setTimeout(() => setRevealStage(3), WEB_ANSWER_REVEAL_MS.settled));
  }, [displayAnswer?.title, displayAnswer?.bullets.join("|"), visible]);

  const reportLayout = useMemo(
    () =>
      displayAnswer
        ? buildWebAnswerReportLayout({
            title: displayAnswer.title,
            bullets: displayAnswer.bullets,
            sources: displayAnswer.sources,
          })
        : null,
    [displayAnswer]
  );

  const modeAwareStyle = useMemo(
    () => (displayAnswer?.mode === "overlay" ? overlayBoxStyle : immersiveBoxStyle),
    [displayAnswer?.mode]
  );

  if (!displayAnswer || !reportLayout || !isMounted) return null;

  return (
    <aside
      ref={rootRef}
      style={{
        ...boxStyle,
        ...modeAwareStyle,
        opacity: isVisible ? 1 : 0,
        transform: `translateY(${isVisible ? "0px" : "8px"})`,
      }}
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
      <div style={badgeStyle}>Search report</div>
      <header style={headerStyle(revealStage >= 1)}>
        <h3 style={titleStyle}>{reportLayout.heading}</h3>
        {reportLayout.lead ? <p style={leadStyle}>{reportLayout.lead}</p> : null}
      </header>

      {reportLayout.findings.length ? (
        <section style={sectionStyle(revealStage >= 2)}>
          <div style={sectionLabelStyle}>Key findings</div>
          <ul style={listStyle}>
            {reportLayout.findings.map((point, index) => (
              <li key={`${point}-${index}`} style={pointStyle}>
                {point}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {reportLayout.sources.length ? (
        <footer style={{ ...footerStyle, ...sectionStyle(revealStage >= 2) }}>
          <button type="button" style={footerToggleStyle} onClick={() => setCollapsed((value) => !value)}>
            {collapsed ? "View" : "Hide"} sources ({reportLayout.sources.length})
          </button>
          {!collapsed ? (
            <ul style={sourceListStyle}>
              {reportLayout.sources.map((source) => (
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

const WEB_ANSWER_TRANSITION_MS = {
  exitDuration: 220,
} as const;

const WEB_ANSWER_REVEAL_MS = {
  header: 45,
  findings: 125,
  settled: 560,
} as const;

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
  left: "calc(50% + min(5.8vw, 64px))",
  top: "34%",
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

const headerStyle = (revealed: boolean): CSSProperties => ({
  marginTop: 7,
  opacity: revealed ? 1 : 0,
  transform: `translateY(${revealed ? "0px" : "4px"})`,
  transition: "opacity 170ms ease, transform 190ms ease",
});

const titleStyle: CSSProperties = {
  margin: "0 0 6px",
  fontSize: 14,
  fontWeight: 620,
};

const leadStyle: CSSProperties = {
  margin: 0,
  fontSize: 12,
  color: "rgba(234, 241, 253, 0.95)",
  display: "-webkit-box",
  WebkitBoxOrient: "vertical",
  WebkitLineClamp: 3,
  overflow: "hidden",
};

const sectionStyle = (revealed: boolean): CSSProperties => ({
  opacity: revealed ? 1 : 0,
  transform: `translateY(${revealed ? "0px" : "6px"})`,
  transition: "opacity 190ms ease, transform 210ms ease",
});

const sectionLabelStyle: CSSProperties = {
  marginTop: 10,
  marginBottom: 6,
  fontSize: 10,
  letterSpacing: 0.35,
  textTransform: "uppercase",
  color: "rgba(188, 207, 235, 0.86)",
};

const listStyle: CSSProperties = {
  margin: 0,
  paddingLeft: 18,
  display: "grid",
  gap: 6,
  fontSize: 12,
};

const pointStyle: CSSProperties = {
  display: "-webkit-box",
  WebkitBoxOrient: "vertical",
  WebkitLineClamp: 2,
  overflow: "hidden",
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
