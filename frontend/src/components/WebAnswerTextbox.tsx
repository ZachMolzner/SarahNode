import { useState, type CSSProperties } from "react";

export type WebAnswerViewModel = {
  title: string;
  bullets: string[];
  sourceTitles: string[];
};

type WebAnswerTextboxProps = {
  answer: WebAnswerViewModel | null;
  defaultCollapsedSources: boolean;
};

export function WebAnswerTextbox({ answer, defaultCollapsedSources }: WebAnswerTextboxProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsedSources);

  if (!answer) return null;

  return (
    <aside style={boxStyle}>
      <div style={badgeStyle}>Checked live web</div>
      <h3 style={{ margin: "8px 0 10px", fontSize: 15 }}>{answer.title}</h3>
      <ul style={listStyle}>
        {answer.bullets.slice(0, 5).map((point) => (
          <li key={point}>{point}</li>
        ))}
      </ul>
      {answer.sourceTitles.length ? (
        <footer style={footerStyle}>
          <button type="button" style={footerToggleStyle} onClick={() => setCollapsed((value) => !value)}>
            {collapsed ? "Show" : "Hide"} sources ({answer.sourceTitles.length})
          </button>
          {!collapsed ? (
            <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
              {answer.sourceTitles.map((source) => (
                <li key={source} style={{ fontSize: 12, opacity: 0.84 }}>
                  {source}
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
  right: 18,
  top: "28%",
  width: "min(360px, 40vw)",
  borderRadius: 14,
  padding: "12px 14px",
  background: "rgba(13, 18, 31, 0.85)",
  border: "1px solid rgba(127, 180, 255, 0.32)",
  color: "#f4f7ff",
  backdropFilter: "blur(9px)",
  boxShadow: "0 18px 48px rgba(2, 5, 12, 0.42)",
  zIndex: 24,
};

const badgeStyle: CSSProperties = {
  display: "inline-block",
  borderRadius: 999,
  padding: "3px 9px",
  fontSize: 11,
  border: "1px solid rgba(133, 201, 255, 0.4)",
  color: "#d5ecff",
  background: "rgba(40, 88, 132, 0.35)",
};

const listStyle: CSSProperties = {
  margin: 0,
  paddingLeft: 18,
  display: "grid",
  gap: 6,
  fontSize: 13,
};

const footerStyle: CSSProperties = {
  marginTop: 10,
  borderTop: "1px solid rgba(156, 175, 222, 0.28)",
  paddingTop: 8,
};

const footerToggleStyle: CSSProperties = {
  borderRadius: 8,
  border: "1px solid rgba(149, 171, 228, 0.4)",
  background: "rgba(31, 44, 79, 0.55)",
  color: "#eaf2ff",
  padding: "4px 9px",
  fontSize: 12,
};
