import React, { useEffect, useMemo, useRef, useState } from "react";
import { EventLog } from "../components/EventLog";
import { StatusCards } from "../components/StatusCards";
import { useEvents } from "../hooks/useEvents";
import { emitVoiceEvent, fetchAssistantState, sendAssistantMessage, transcribeAudio } from "../lib/api";
import { AvatarPanel } from "../components/avatar/AvatarPanel";
import { useAvatarState } from "../hooks/useAvatarState";
import { VoiceRecorder } from "../components/voice/VoiceRecorder";
import { browserAppShell } from "../lib/appShell";
import { isShutdownCancellation, isShutdownConfirmation, matchShutdownIntent } from "../lib/shutdownIntent";
import { runShutdownFlow } from "../lib/shutdownController";

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
  const [audioReady, setAudioReady] = useState(false);
  const [llmStatus, setLlmStatus] = useState("loading");
  const [ttsStatus, setTtsStatus] = useState("loading");
  const [voiceStatus, setVoiceStatus] = useState("idle");
  const [isControlsOpen, setIsControlsOpen] = useState(false);
  const [isTranscriptOpen, setIsTranscriptOpen] = useState(false);
  const [shutdownPendingConfirm, setShutdownPendingConfirm] = useState(false);
  const [shutdownPrompt, setShutdownPrompt] = useState<string | null>(null);
  const [shutdownStatus, setShutdownStatus] = useState<"idle" | "starting" | "ended">("idle");

  const totalEvents = useMemo(() => events.length, [events]);
  const latestReply = events.find((event) => event.type === "reply_selected")?.payload?.["text"];
  const baseAvatarState = useAvatarState(events);
  const avatarState =
    shutdownStatus === "starting" || shutdownStatus === "ended"
      ? { ...baseAvatarState, mode: "shutting_down", mood: "goodbye", isSpeaking: false }
      : baseAvatarState;

  useEffect(() => {
    void fetchAssistantState()
      .then((state) => {
        const llm = state.providers?.llm;
        const tts = state.providers?.tts;
        setLlmStatus(`${llm?.active ?? "unknown"} (${llm?.mode ?? "unknown"})`);
        setTtsStatus(`${tts?.active ?? "unknown"} (${tts?.mode ?? "unknown"})`);
      })
      .catch(() => {
        setLlmStatus("unavailable");
        setTtsStatus("unavailable");
      });
  }, []);

  useEffect(() => {
    if (shutdownStatus !== "idle") return;
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
    setAudioReady(true);

    const onEnded = () => setIsAudioPlaying(false);
    const onError = () => setIsAudioPlaying(false);

    audio.addEventListener("ended", onEnded);
    audio.addEventListener("error", onError);
    void audio.play().then(() => setIsAudioPlaying(true)).catch(() => setIsAudioPlaying(false));

    return () => {
      audio.pause();
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("error", onError);
    };
  }, [events, shutdownStatus]);

  useEffect(() => {
    const voiceEvent = events.find((event) => event.type.startsWith("voice:"));
    if (!voiceEvent) return;

    if (voiceEvent.type === "voice:recording_started") setVoiceStatus("listening");
    if (voiceEvent.type === "voice:recording_stopped") setVoiceStatus("recording stopped");
    if (voiceEvent.type === "voice:transcribing") setVoiceStatus("transcribing");
    if (voiceEvent.type === "voice:transcribed") setVoiceStatus("transcribed");
    if (voiceEvent.type === "voice:error") setVoiceStatus("error");
  }, [events]);

  function stopAudioPlayback() {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setIsAudioPlaying(false);
  }

  async function runConfirmedShutdown() {
    setShutdownStatus("starting");
    setShutdownPrompt("Closing session...");

    const result = await runShutdownFlow({
      stopListening: () => setVoiceStatus("stopping"),
      stopAudio: stopAudioPlayback,
      stopAvatarSpeech: () => setIsAudioPlaying(false),
      appShell: browserAppShell,
    });

    if (result === "fallback") {
      setShutdownStatus("ended");
      setShutdownPrompt("Session closed. You can now close this tab.");
      return;
    }

    setShutdownStatus("ended");
    setShutdownPrompt("Session closed.");
  }

  async function maybeHandleShutdownIntent(messageText: string): Promise<boolean> {
    if (shutdownStatus !== "idle") return true;

    if (shutdownPendingConfirm) {
      if (isShutdownConfirmation(messageText)) {
        setShutdownPendingConfirm(false);
        await runConfirmedShutdown();
        return true;
      }

      if (isShutdownCancellation(messageText)) {
        setShutdownPendingConfirm(false);
        setShutdownPrompt("Okay, keeping SarahNode open.");
        window.setTimeout(() => setShutdownPrompt(null), 2500);
        return true;
      }
    }

    const match = matchShutdownIntent(messageText);
    if (!match.matched) return false;

    if (match.requiresConfirmation) {
      setShutdownPendingConfirm(true);
      setShutdownPrompt("Are you sure you want me to close?");
      return true;
    }

    await runConfirmedShutdown();
    return true;
  }

  async function handleSend(messageText = content) {
    if (await maybeHandleShutdownIntent(messageText)) {
      return;
    }

    setIsSending(true);
    setError(null);

    try {
      await sendAssistantMessage({ username, content: messageText, priority });
      setContent("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message to assistant.");
    } finally {
      setIsSending(false);
    }
  }

  async function replayAudio() {
    if (!audioRef.current) return;
    try {
      await audioRef.current.play();
      setIsAudioPlaying(true);
    } catch {
      setIsAudioPlaying(false);
    }
  }

  return (
    <main style={pageStyle}>
      <div style={stageStyle}>
        <AvatarPanel avatarState={avatarState} />

        <div style={topOverlayStyle}>
          <Pill label={`Connection: ${connectionState}`} muted={connectionState !== "open"} />
          <Pill label={`Voice: ${voiceStatus}`} muted={voiceStatus === "idle"} />
          <button type="button" onClick={() => setIsControlsOpen((open) => !open)} style={miniButtonStyle}>
            {isControlsOpen ? "Hide Controls" : "Menu"}
          </button>
          <button type="button" onClick={() => setIsTranscriptOpen((open) => !open)} style={miniButtonStyle}>
            {isTranscriptOpen ? "Hide Transcript" : "Transcript"}
          </button>
        </div>

        <div style={bottomOverlayStyle}>
          <VoiceRecorder
            disabled={isSending || shutdownStatus !== "idle"}
            shouldStop={shutdownStatus !== "idle"}
            onRecordingStarted={() => {
              setVoiceStatus("listening");
              void emitVoiceEvent("voice:recording_started");
            }}
            onRecordingStopped={() => {
              void emitVoiceEvent("voice:recording_stopped");
            }}
            onTranscribe={transcribeAudio}
            onTranscript={async (text) => {
              setContent(text);
              await handleSend(text);
            }}
          />
          {shutdownPrompt ? <p style={shutdownPromptStyle}>{shutdownPrompt}</p> : null}
        </div>

        {isControlsOpen ? (
          <aside style={drawerStyle}>
            <h2 style={{ marginTop: 0 }}>Assistant Controls</h2>
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
              <span>Typed Message</span>
              <textarea
                value={content}
                onChange={(event) => setContent(event.target.value)}
                rows={4}
                style={{ ...inputStyle, resize: "vertical" }}
              />
            </label>

            <div style={submitRowStyle}>
              <button onClick={() => void handleSend()} disabled={isSending || !content.trim()} style={buttonStyle}>
                {isSending ? "Sending..." : "Send Message"}
              </button>
              <button onClick={replayAudio} disabled={!audioReady} style={secondaryButtonStyle}>
                Replay Last Audio
              </button>
            </div>

            {error ? <span style={{ color: "#ff8c8c" }}>{error}</span> : null}

            <div style={{ marginTop: 14, display: "grid", gap: 12 }}>
              <StatusCards
                events={events}
                connectionState={connectionState}
                isAudioPlaying={isAudioPlaying}
                llmStatus={llmStatus}
                ttsStatus={ttsStatus}
              />
            </div>
          </aside>
        ) : null}

        {isTranscriptOpen ? (
          <section style={transcriptOverlayStyle}>
            <header style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
              <strong>Event Transcript</strong>
              <span style={{ opacity: 0.8, fontSize: 12 }}>Events: {totalEvents}</span>
            </header>
            <p style={{ margin: "8px 0 10px", fontSize: 12, opacity: 0.8 }}>
              Latest reply: {typeof latestReply === "string" ? latestReply : "No reply yet."}
            </p>
            <div style={{ maxHeight: "40vh", overflowY: "auto" }}>
              <EventLog events={events.slice(0, 20)} />
            </div>
          </section>
        ) : null}

        {shutdownStatus === "ended" ? (
          <div style={shutdownOverlayStyle}>
            <h2 style={{ marginTop: 0 }}>Session closed</h2>
            <p style={{ marginBottom: 12 }}>{shutdownPrompt ?? "Session ended."}</p>
            <button type="button" onClick={() => window.close()} style={buttonStyle}>
              Try close tab
            </button>
          </div>
        ) : null}
      </div>
    </main>
  );
}

function Pill({ label, muted = false }: { label: string; muted?: boolean }) {
  return <span style={{ ...pillStyle, opacity: muted ? 0.75 : 1 }}>{label}</span>;
}

const pageStyle: React.CSSProperties = {
  minHeight: "100vh",
  background: "radial-gradient(circle at top, #11172b 0%, #05060c 60%)",
  color: "#f5f5f5",
  fontFamily: "Inter, Arial, sans-serif",
};

const stageStyle: React.CSSProperties = {
  width: "100%",
  minHeight: "100vh",
  position: "relative",
  overflow: "hidden",
};

const topOverlayStyle: React.CSSProperties = {
  position: "absolute",
  top: 10,
  left: 10,
  right: 10,
  display: "flex",
  alignItems: "center",
  gap: 8,
  flexWrap: "wrap",
  zIndex: 15,
};

const bottomOverlayStyle: React.CSSProperties = {
  position: "absolute",
  left: 10,
  right: 10,
  bottom: 10,
  display: "grid",
  gap: 8,
  maxWidth: 420,
  zIndex: 15,
};

const miniButtonStyle: React.CSSProperties = {
  border: "1px solid #445277",
  background: "rgba(15, 18, 30, 0.66)",
  color: "#eef1ff",
  borderRadius: 999,
  padding: "6px 12px",
  cursor: "pointer",
};

const drawerStyle: React.CSSProperties = {
  position: "absolute",
  top: 54,
  right: 10,
  width: "min(500px, calc(100vw - 20px))",
  maxHeight: "calc(100vh - 64px)",
  overflowY: "auto",
  padding: 12,
  borderRadius: 14,
  background: "rgba(10, 12, 19, 0.92)",
  border: "1px solid #2f3855",
  backdropFilter: "blur(10px)",
  zIndex: 20,
};

const transcriptOverlayStyle: React.CSSProperties = {
  position: "absolute",
  left: 10,
  bottom: 132,
  width: "min(560px, calc(100vw - 20px))",
  borderRadius: 12,
  padding: 10,
  border: "1px solid #2d3553",
  background: "rgba(6, 8, 14, 0.86)",
  zIndex: 20,
};

const shutdownOverlayStyle: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  background: "rgba(0, 0, 0, 0.65)",
  display: "grid",
  placeItems: "center",
  textAlign: "center",
  padding: 20,
  zIndex: 40,
};

const gridInputsStyle: React.CSSProperties = {
  display: "grid",
  gap: 12,
  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
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

const secondaryButtonStyle: React.CSSProperties = {
  border: "1px solid #575757",
  borderRadius: 10,
  padding: "10px 16px",
  cursor: "pointer",
  background: "transparent",
  color: "#f5f5f5",
};

const shutdownPromptStyle: React.CSSProperties = {
  margin: 0,
  fontSize: 13,
  lineHeight: 1.4,
  padding: "6px 10px",
  borderRadius: 8,
  border: "1px solid #2f3856",
  background: "rgba(7, 9, 16, 0.72)",
};

const pillStyle: React.CSSProperties = {
  border: "1px solid #33416a",
  background: "rgba(8, 11, 18, 0.72)",
  borderRadius: 999,
  padding: "5px 10px",
  fontSize: 12,
  backdropFilter: "blur(8px)",
};
