import React, { useEffect, useMemo, useRef, useState } from "react";
import { EventLog } from "../components/EventLog";
import { StatusCards } from "../components/StatusCards";
import { useEvents } from "../hooks/useEvents";
import { sendAssistantMessage } from "../lib/api";
import { AvatarPanel } from "../components/avatar/AvatarPanel";
import { useAvatarState } from "../hooks/useAvatarState";

export function DashboardPage() {
  const { events, connectionState } = useEvents();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const processedTtsKeyRef = useRef<string>("");

  const [username, setUsername] = useState("local-user");
  const [content, setContent] = useState("Give me a quick plan for today.");
  const [priority, setPriority] = useState(1);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAudioPlaying, setIsAudioPlaying] = useState(false);

  const totalEvents = useMemo(() => events.length, [events]);
  const latestReply = events.find((event) => event.type === "reply_selected")?.payload?.["text"];
  const avatarState = useAvatarState(events);

  useEffect(() => {
    const ttsEvent = events.find((event) => event.type === "tts_output");
    if (!ttsEvent) return;

    const audioBase64 = ttsEvent.payload?.["audio_base64"];
    const mimeType = ttsEvent.payload?.["mime_type"];

    if (typeof audioBase64 !== "string" || !audioBase64 || typeof mimeType !== "string") {
      return;
    }

    const ttsEventKey = `${ttsEvent.timestamp}-${audioBase64.length}`;
    if (processedTtsKeyRef.current === ttsEventKey) {
      return;
    }
    processedTtsKeyRef.current = ttsEventKey;

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    const audio = new Audio(`data:${mimeType};base64,${audioBase64}`);
    audioRef.current = audio;
    setIsAudioPlaying(true);

    const onEnded = () => setIsAudioPlaying(false);
    const onError = () => setIsAudioPlaying(false);

    audio.addEventListener("ended", onEnded);
    audio.addEventListener("error", onError);
    void audio.play().catch(() => setIsAudioPlaying(false));

    return () => {
      audio.pause();
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("error", onError);
    };
  }, [events]);

  async function handleSend() {
    setIsSending(true);
    setError(null);

    try {
      await sendAssistantMessage({ username, content, priority });
      setContent("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message to assistant.");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <main style={pageStyle}>
      <div style={containerStyle}>
        <header>
          <h1 style={{ marginBottom: 8 }}>SarahNode Local Assistant Control Center</h1>
          <p style={{ margin: 0, opacity: 0.8 }}>
            WebSocket: <strong>{connectionState}</strong> · Events: <strong>{totalEvents}</strong>
          </p>
        </header>

        <section style={panelStyle}>
          <h2 style={{ marginTop: 0 }}>Conversation</h2>
          <div style={gridInputsStyle}>
            <label style={{ display: "grid", gap: 6 }}>
              <span>Username</span>
              <input value={username} onChange={(event) => setUsername(event.target.value)} style={inputStyle} />
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
            <span>Message</span>
            <textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              rows={4}
              style={{ ...inputStyle, resize: "vertical" }}
            />
          </label>

          <div style={submitRowStyle}>
            <button onClick={handleSend} disabled={isSending || !content.trim()} style={buttonStyle}>
              {isSending ? "Sending..." : "Send Message"}
            </button>
            {error ? <span style={{ color: "#ff8c8c" }}>{error}</span> : null}
          </div>
        </section>

        <StatusCards events={events} connectionState={connectionState} isAudioPlaying={isAudioPlaying} />

        <AvatarPanel avatarState={avatarState} latestReplyText={typeof latestReply === "string" ? latestReply : undefined} />

        <EventLog events={events} />
      </div>
    </main>
  );
}

const pageStyle: React.CSSProperties = {
  minHeight: "100vh",
  background: "#0b0b0b",
  color: "#f5f5f5",
  fontFamily: "Inter, Arial, sans-serif",
  padding: "12px 10px 24px",
};

const containerStyle: React.CSSProperties = {
  maxWidth: 1200,
  margin: "0 auto",
  display: "grid",
  gap: 16,
};

const panelStyle: React.CSSProperties = {
  border: "1px solid #2a2a2a",
  borderRadius: 12,
  padding: 14,
  background: "#161616",
};

const gridInputsStyle: React.CSSProperties = {
  display: "grid",
  gap: 12,
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
};

const submitRowStyle: React.CSSProperties = {
  display: "flex",
  gap: 12,
  alignItems: "center",
  marginTop: 12,
  flexWrap: "wrap",
};


const inputStyle: React.CSSProperties = {
  border: "1px solid #3a3a3a",
  borderRadius: 10,
  padding: "10px 12px",
  background: "#0f0f0f",
  color: "#f5f5f5",
};

const buttonStyle: React.CSSProperties = {
  border: "none",
  borderRadius: 10,
  padding: "10px 16px",
  cursor: "pointer",
  background: "#f5f5f5",
  color: "#111",
  fontWeight: 700,
};
