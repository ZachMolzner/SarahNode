import React from "react";
import type { SystemEvent } from "../types/events";

type EventLogProps = {
  events: SystemEvent[];
};

const cardStyle: React.CSSProperties = {
  border: "1px solid #2a2a2a",
  borderRadius: 12,
  padding: 12,
  background: "#161616",
};

export function EventLog({ events }: EventLogProps) {
  return (
    <section style={cardStyle}>
      <h2 style={{ marginTop: 0 }}>Assistant Event Stream</h2>

      {events.length === 0 ? (
        <p style={{ opacity: 0.8 }}>No events yet.</p>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {events.map((event, index) => (
            <article
              key={`${event.timestamp}-${event.type}-${index}`}
              style={{
                border: "1px solid #303030",
                borderRadius: 10,
                padding: 12,
                background: "#101010",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <strong>{event.type}</strong>
                <span style={{ opacity: 0.7, fontSize: 12 }}>{event.timestamp}</span>
              </div>

              <pre
                style={{
                  margin: "10px 0 0",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  fontSize: 12,
                  lineHeight: 1.45,
                }}
              >
                {JSON.stringify(event.payload, null, 2)}
              </pre>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
