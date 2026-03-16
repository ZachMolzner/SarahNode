import React, { useMemo, useState } from "react";
import { EventLog } from "../components/EventLog";
import { StatusCards } from "../components/StatusCards";
import { useEvents } from "../hooks/useEvents";
import { sendSimpleMockChat } from "../lib/api";

export function DashboardPage() {
  const { events, connectionState } = useEvents();

  const [username, setUsername] = useState("demo-user");
  const [content, setContent] = useState("hello nova!");
  const [priority, setPriority] = useState(2);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalEvents = useMemo(() => events.length, [events]);

  async function handleSend() {
    setIsSending(true);
    setError(null);

    try {
      await sendSimpleMockChat(username, content, priority);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send chat.");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "#0b0b0b",
        color: "#f5f5f5",
        fontFamily: "Inter, Arial, sans-serif",
        padding: 24,
      }}
    >
      <div style={{ maxWidth: 1200, margin: "0 auto", display: "grid", gap: 20 }}>
        <header>
          <h1 style={{ marginBottom: 8 }}>SarahNode Dashboard</h1>
          <p style={{ margin: 0, opacity: 0.8 }}>
            WebSocket status: <strong>{connectionState}</strong> · Total events:{" "}
            <strong>{totalEvents}</strong>
          </p>
        </header>

        <section
          style={{
            border: "1px solid #2a2a2a",
            borderRadius: 12,
            padding: 16,
            background: "#161616",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Send Demo Chat</h2>

          <div
            style={{
              display: "grid",
              gap: 12,
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            }}
          >
            <label style={{ display: "grid", gap: 6 }}>
              <span>Username</span>
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                style={inputStyle}
              />
            </label>

            <label style={{ display: "grid", gap: 6 }}>
              <span>Priority</span>
              <input
                type="number"
                min={0}
                max={10}
                value={priority}
                onChange={(event) => setPriority(Number(event.target.value))}
                style={inputStyle}
              />
            </label>
          </div>

          <label style={{ display: "grid", gap: 6, marginTop: 12 }}>
            <span>Content</span>
            <textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              rows={4}
              style={{ ...inputStyle, resize: "vertical" }}
            />
          </label>

          <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 12 }}>
            <button
              onClick={handleSend}
              disabled={isSending}
              style={{
                border: "none",
                borderRadius: 10,
                padding: "10px 16px",
                cursor: isSending ? "not-allowed" : "pointer",
                background: "#f5f5f5",
                color: "#111",
                fontWeight: 700,
              }}
            >
              {isSending ? "Sending..." : "Send Demo Chat"}
            </button>

            {error ? <span style={{ color: "#ff8c8c" }}>{error}</span> : null}
          </div>
        </section>

        <StatusCards events={events} connectionState={connectionState} />
        <EventLog events={events} />
      </div>
    </main>
  );
}

const inputStyle: React.CSSProperties = {
  border: "1px solid #3a3a3a",
  borderRadius: 10,
  padding: "10px 12px",
  background: "#0f0f0f",
  color: "#f5f5f5",
};
