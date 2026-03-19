import React, { useEffect, useMemo, useRef, useState } from "react";
import { EventLog } from "../components/EventLog";
import { StatusCards } from "../components/StatusCards";
import { useEvents } from "../hooks/useEvents";
import { emitVoiceEvent, fetchAssistantState, sendAssistantMessage, transcribeAudio } from "../lib/api";
import { AvatarPanel } from "../components/avatar/AvatarPanel";
import { useAvatarState } from "../hooks/useAvatarState";
import { VoiceRecorder } from "../components/voice/VoiceRecorder";
import { createAppShell } from "../lib/appShell";
import { isShutdownCancellation, isShutdownConfirmation, matchShutdownIntent } from "../lib/shutdownIntent";
import { runShutdownFlow } from "../lib/shutdownController";
import { SubtitleCaptions } from "../components/captions/SubtitleCaptions";
import { useGesturePerformance } from "../hooks/useGesturePerformance";
import { createVoiceOrchestrator, type TTSPlaybackPayload } from "../lib/voiceOrchestrator";
import { pickNonRepeatingLine } from "../lib/voiceLines";

export function DashboardPage() {
  const { events, connectionState } = useEvents();
  const processedTtsKeyRef = useRef<string>("");
  const processedReplyKeyRef = useRef<string>("");
  const startupLineRef = useRef<string | null>(null);
  const shutdownLineRef = useRef<string | null>(null);

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
  const [captionText, setCaptionText] = useState("");
  const [captionSpeaker, setCaptionSpeaker] = useState<"sarah" | "user" | null>(null);
  const [isCaptionVisible, setIsCaptionVisible] = useState(false);
  const [lastTranscriptAt, setLastTranscriptAt] = useState(0);
  const [lastUserSpeechAt, setLastUserSpeechAt] = useState(0);
  const [lastReplyAt, setLastReplyAt] = useState(0);
  const [sessionReadyAt, setSessionReadyAt] = useState(0);
  const [startupGreetingRequested, setStartupGreetingRequested] = useState(false);
  const [startupGreetingDelivered, setStartupGreetingDelivered] = useState(false);
  const [shutdownPerformanceDelivered, setShutdownPerformanceDelivered] = useState(false);
  const [listeningStartedAt, setListeningStartedAt] = useState(0);
  const [speakingStartedAt, setSpeakingStartedAt] = useState(0);
  const voiceOrchestratorRef = useRef(
    createVoiceOrchestrator({
      onCaption: (text) => {
        setCaptionSpeaker("sarah");
        setCaptionText(text);
      },
      onPlaybackStateChange: (isPlaying) => setIsAudioPlaying(isPlaying),
    })
  );

  const appShell = useMemo(() => createAppShell(), []);
  const totalEvents = useMemo(() => events.length, [events]);
  const latestReply = events.find((event) => event.type === "reply_selected")?.payload?.["text"];
  const baseAvatarState = useAvatarState(events);
  const isSpeaking = baseAvatarState.isSpeaking || isAudioPlaying;

  const avatarState =
    shutdownStatus === "starting" || shutdownStatus === "ended"
      ? { ...baseAvatarState, mode: "shutting_down", mood: "goodbye", isSpeaking: false, mouthIntensity: 0.05 }
      : {
          ...baseAvatarState,
          mode: isSpeaking ? "talking" : baseAvatarState.mode,
          mood:
            baseAvatarState.mode === "listening"
              ? "listening"
              : baseAvatarState.mode === "thinking"
                ? "focused"
                : isSpeaking
                  ? "warm"
                  : baseAvatarState.mood,
          isSpeaking,
          mouthIntensity: isAudioPlaying ? 0.8 : isSpeaking ? 0.58 : 0.02,
        };
  const latestReplyText = typeof latestReply === "string" ? latestReply : "";

  const gesturePerformance = useGesturePerformance({
    avatarState,
    startupRequested: startupGreetingRequested,
    shutdownRequested: shutdownStatus === "starting" || shutdownStatus === "ended",
    listeningStartedAtMs: listeningStartedAt,
    replyStartedAtMs: lastReplyAt,
    speakingStartedAtMs: speakingStartedAt,
    latestReplyText,
  });

  useEffect(() => {
    const timerId = window.setTimeout(() => {
      setSessionReadyAt(Date.now());
      setStartupGreetingRequested(true);
    }, 850);
    return () => window.clearTimeout(timerId);
  }, []);

  useEffect(() => {
    if (startupGreetingDelivered || !startupGreetingRequested || !sessionReadyAt || shutdownStatus !== "idle") return;
    setStartupGreetingDelivered(true);
    const line = pickNonRepeatingLine("startup", startupLineRef.current);
    startupLineRef.current = line;
    void voiceOrchestratorRef.current.speakText(line, { context: "startup", mood: "cheerful" });
  }, [sessionReadyAt, shutdownStatus, startupGreetingDelivered, startupGreetingRequested]);

  useEffect(() => {
    return () => voiceOrchestratorRef.current.stopSpeaking();
  }, []);

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

    const ttsEventKey = `${ttsEvent.timestamp}-${JSON.stringify(ttsEvent.payload ?? {}).length}`;
    if (processedTtsKeyRef.current === ttsEventKey) {
      return;
    }
    processedTtsKeyRef.current = ttsEventKey;

    const payload = (ttsEvent.payload ?? {}) as TTSPlaybackPayload;
    const sourceText = typeof payload.source_text === "string" ? payload.source_text : "";
    if (!sourceText) return;

    void voiceOrchestratorRef.current.speakText(sourceText, { ttsPayload: payload, context: "reply", mood: "warm" }).then(() => {
      const orchestrationStatus = voiceOrchestratorRef.current.getVoiceStatus();
      setAudioReady(orchestrationStatus.hasReplayableAudio);
      setTtsStatus(
        orchestrationStatus.backendProvider
          ? `${orchestrationStatus.backendProvider}${orchestrationStatus.backendModel ? ` · ${orchestrationStatus.backendModel}` : ""}${
              orchestrationStatus.backendVoice ? ` · ${orchestrationStatus.backendVoice}` : ""
            }`
          : orchestrationStatus.provider
      );
      setLastReplyAt(Date.now());
    });
  }, [events, shutdownStatus]);

  useEffect(() => {
    const replyEvent = events.find((event) => event.type === "reply_selected");
    if (!replyEvent) return;
    const replyText = replyEvent.payload?.["text"];
    if (typeof replyText !== "string" || !replyText.trim()) return;

    const replyKey = `${replyEvent.timestamp}-${replyText.length}`;
    if (processedReplyKeyRef.current === replyKey) return;
    processedReplyKeyRef.current = replyKey;

    setCaptionSpeaker("sarah");
    setCaptionText(replyText);
    setLastReplyAt(Date.now());
    window.setTimeout(() => {
      const latestTts = events.find((event) => event.type === "tts_output");
      const ttsSourceText = latestTts?.payload?.["source_text"];
      if (typeof ttsSourceText === "string" && ttsSourceText === replyText) return;
      void voiceOrchestratorRef.current.speakText(replyText, { context: "reply", mood: "warm" });
    }, 450);
  }, [events]);

  useEffect(() => {
    const voiceEvent = events.find((event) => event.type.startsWith("voice:"));
    if (!voiceEvent) return;

    if (voiceEvent.type === "voice:recording_started") {
      setVoiceStatus("listening");
      setListeningStartedAt(Date.now());
    }
    if (voiceEvent.type === "voice:recording_stopped") setVoiceStatus("recording stopped");
    if (voiceEvent.type === "voice:transcribing") setVoiceStatus("transcribing");
    if (voiceEvent.type === "voice:transcribed") setVoiceStatus("transcribed");
    if (voiceEvent.type === "voice:error") setVoiceStatus("error");
  }, [events]);

  function stopAudioPlayback() {
    voiceOrchestratorRef.current.stopSpeaking();
  }

  async function runConfirmedShutdown() {
    if (!shutdownPerformanceDelivered) {
      setShutdownPerformanceDelivered(true);
      const line = pickNonRepeatingLine("shutdown", shutdownLineRef.current);
      shutdownLineRef.current = line;
      await voiceOrchestratorRef.current.speakText(line, { context: "shutdown", mood: "goodbye" });
    }

    setShutdownStatus("starting");
    setShutdownPrompt("Closing session...");
    await new Promise((resolve) => window.setTimeout(resolve, 2200));

    const result = await runShutdownFlow({
      stopListening: () => setVoiceStatus("stopping"),
      stopAudio: stopAudioPlayback,
      stopAvatarSpeech: () => setIsAudioPlaying(false),
      appShell,
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
    await voiceOrchestratorRef.current.replayLastAudio();
  }

  useEffect(() => {
    if (isSpeaking) {
      setSpeakingStartedAt((previous) => (Date.now() - previous > 320 ? Date.now() : previous));
    }
  }, [isSpeaking]);

  return (
    <main style={pageStyle}>
      <div style={stageStyle}>
        <AvatarPanel
          avatarState={avatarState}
          gesturePerformance={gesturePerformance}
          overlayVisibility={{
            controlsOpen: isControlsOpen,
            transcriptOpen: isTranscriptOpen,
            captionsVisible: isCaptionVisible,
            shutdownVisible: shutdownStatus !== "idle",
          }}
          presenceSignals={{
            transcriptEventAtMs: lastTranscriptAt,
            userSpokeAtMs: lastUserSpeechAt,
            replyAtMs: lastReplyAt,
          }}
        />
        <SubtitleCaptions speaker={captionSpeaker} text={captionText} onVisibilityChange={setIsCaptionVisible} />

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
              setListeningStartedAt(Date.now());
              void emitVoiceEvent("voice:recording_started");
            }}
            onRecordingStopped={() => {
              void emitVoiceEvent("voice:recording_stopped");
            }}
            onTranscribe={transcribeAudio}
            onTranscript={async (text) => {
              setCaptionSpeaker("user");
              setCaptionText(text);
              setLastTranscriptAt(Date.now());
              setLastUserSpeechAt(Date.now());
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
  background: "#03050c",
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
  border: "1px solid rgba(130, 155, 217, 0.55)",
  background: "rgba(9, 13, 26, 0.52)",
  color: "#eef1ff",
  borderRadius: 999,
  padding: "6px 12px",
  cursor: "pointer",
  backdropFilter: "blur(8px)",
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
  background: "rgba(8, 12, 22, 0.76)",
  border: "1px solid rgba(96, 120, 190, 0.5)",
  backdropFilter: "blur(12px)",
  zIndex: 20,
};

const transcriptOverlayStyle: React.CSSProperties = {
  position: "absolute",
  left: 10,
  bottom: 132,
  width: "min(560px, calc(100vw - 20px))",
  borderRadius: 12,
  padding: 10,
  border: "1px solid rgba(103, 125, 195, 0.5)",
  background: "rgba(6, 10, 18, 0.75)",
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
  border: "1px solid rgba(99, 116, 164, 0.9)",
  borderRadius: 10,
  padding: "10px 12px",
  background: "rgba(8, 12, 24, 0.88)",
  color: "#f5f5f5",
};

const buttonStyle: React.CSSProperties = {
  border: "1px solid rgba(206, 223, 255, 0.65)",
  borderRadius: 10,
  padding: "10px 16px",
  cursor: "pointer",
  background: "rgba(222, 232, 255, 0.9)",
  color: "#0d162f",
  fontWeight: 700,
};

const secondaryButtonStyle: React.CSSProperties = {
  border: "1px solid rgba(136, 155, 216, 0.75)",
  borderRadius: 10,
  padding: "10px 16px",
  cursor: "pointer",
  background: "rgba(11, 16, 28, 0.66)",
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
  border: "1px solid rgba(96, 121, 194, 0.62)",
  background: "rgba(8, 12, 22, 0.62)",
  borderRadius: 999,
  padding: "5px 10px",
  fontSize: 12,
  backdropFilter: "blur(8px)",
};
