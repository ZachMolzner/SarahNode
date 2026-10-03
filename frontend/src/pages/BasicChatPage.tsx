import React, { FormEvent, useEffect, useRef, useState } from "react";
import { MarkdownMessage } from "../components/MarkdownMessage";
import { SarahAvatar } from "../components/SarahAvatar";
import { fetchAssistantState, sendAssistantMessage } from "../lib/api";
import {
  emotionFromReply,
  localSpeechSupported,
  speakSarahReply,
  stopLocalSpeech,
} from "../lib/localSpeech";

type Message = {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
};

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));
const REPLY_POLL_INTERVAL_MS = 250;
const REPLY_POLL_ATTEMPTS = 480;

const FACE_TEST_MOODS = [
  "happy",
  "relaxed",
  "sad",
  "angry",
  "surprised",
  "concerned",
  "neutral",
] as const;

type FaceTestMood = (typeof FACE_TEST_MOODS)[number];

export function BasicChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      role: "assistant",
      content: "Sarah is ready. Ask me about IT, coding, research, or anything else.",
    },
  ]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState("Connecting");
  const [avatarMood, setAvatarMood] = useState("neutral");
  const [replySignal, setReplySignal] = useState(0);
  const [faceTestSignal, setFaceTestSignal] = useState(0);
  const [attentionSignal, setAttentionSignal] = useState(0);
  const [sending, setSending] = useState(false);
  const [localSpeaking, setLocalSpeaking] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(() => {
    return window.localStorage.getItem("sarah.voiceEnabled") !== "false";
  });
  const speechAvailable = localSpeechSupported();
  const nextId = useRef(2);
  const endRef = useRef<HTMLDivElement | null>(null);
  const faceTestActiveRef = useRef(false);
  const faceTestTimersRef = useRef<number[]>([]);

  useEffect(() => {
    let cancelled = false;

    const refreshBackendStatus = async () => {
      try {
        const state = await fetchAssistantState();
        if (!cancelled) {
          setStatus(state.assistant_state || "Online");
          if (!faceTestActiveRef.current) {
            const inferredMood = emotionFromReply(state.latest_reply || "");
            if (inferredMood || state.latest_reply_emotion) {
              setAvatarMood(inferredMood || state.latest_reply_emotion || "neutral");
            }
          }
        }
      } catch {
        if (!cancelled) {
          setStatus("Backend offline");
        }
      }
    };

    void refreshBackendStatus();
    const heartbeat = window.setInterval(refreshBackendStatus, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(heartbeat);
    };
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    window.localStorage.setItem("sarah.voiceEnabled", String(voiceEnabled));
    if (!voiceEnabled) {
      stopLocalSpeech();
      setLocalSpeaking(false);
    }
  }, [voiceEnabled]);

  useEffect(() => {
    return () => {
      stopLocalSpeech();
      for (const timer of faceTestTimersRef.current) {
        window.clearTimeout(timer);
      }
    };
  }, []);

  const addMessage = (role: Message["role"], content: string) => {
    setMessages((current) => [
      ...current,
      { id: nextId.current++, role, content },
    ]);
  };

  const clearFaceTest = () => {
    for (const timer of faceTestTimersRef.current) {
      window.clearTimeout(timer);
    }
    faceTestTimersRef.current = [];
    faceTestActiveRef.current = false;
  };

  const setTestMood = (mood: FaceTestMood) => {
    setAvatarMood(mood);
    setReplySignal((current) => current + 1);
  };

  const runFaceTestCommand = (content: string): boolean => {
    const match = content.match(
      /^\/(?:face-test|facetest)(?:\s+([a-z-]+))?\s*$/i,
    );
    if (!match) return false;

    clearFaceTest();
    stopLocalSpeech();
    setLocalSpeaking(false);
    setFaceTestSignal((current) => current + 1);
    faceTestActiveRef.current = true;

    const requested = (match[1] || "all").toLowerCase();

    if (requested === "all") {
      addMessage(
        "system",
        "Facial-expression test started in Face view: happy → relaxed → sad → angry → surprised → concerned → neutral.",
      );

      FACE_TEST_MOODS.forEach((mood, index) => {
        const timer = window.setTimeout(() => {
          setTestMood(mood);
          if (index === FACE_TEST_MOODS.length - 1) {
            const finishTimer = window.setTimeout(() => {
              faceTestActiveRef.current = false;
            }, 1800);
            faceTestTimersRef.current.push(finishTimer);
          }
        }, index * 2200);
        faceTestTimersRef.current.push(timer);
      });
      return true;
    }

    if (FACE_TEST_MOODS.includes(requested as FaceTestMood)) {
      const mood = requested as FaceTestMood;
      setTestMood(mood);
      addMessage(
        "system",
        `Facial-expression test: ${mood}. Use /face-test all to cycle every expression or send a normal message to exit test mode.`,
      );
      return true;
    }

    faceTestActiveRef.current = false;
    addMessage(
      "system",
      "Unknown facial-expression test. Use /face-test, or /face-test happy|relaxed|sad|angry|surprised|concerned|neutral.",
    );
    return true;
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const content = input.trim();
    if (!content || sending) return;

    setInput("");
    addMessage("user", content);

    if (runFaceTestCommand(content)) {
      return;
    }

    clearFaceTest();
    setAttentionSignal((current) => current + 1);
    setSending(true);

    try {
      const before = await fetchAssistantState().catch(() => null);
      const previousReply = before?.latest_reply ?? "";

      await sendAssistantMessage({
        username: "zach",
        content,
        conversation_mode: "personal",
      });
      setStatus("Thinking");

      let reply = "";
      let lastState = "Thinking";

      for (let attempt = 0; attempt < REPLY_POLL_ATTEMPTS; attempt += 1) {
        await sleep(REPLY_POLL_INTERVAL_MS);
        const state = await fetchAssistantState();
        lastState = state.assistant_state || lastState;
        setStatus(lastState);

        if (state.latest_reply && state.latest_reply !== previousReply) {
          reply = state.latest_reply;
          setAvatarMood(
            emotionFromReply(state.latest_reply) ||
              state.latest_reply_emotion ||
              "neutral",
          );
          setReplySignal((current) => current + 1);
          break;
        }
      }

      if (reply) {
        addMessage("assistant", reply);

        if (voiceEnabled && speechAvailable) {
          const started = speakSarahReply(reply, {
            onStart: () => setLocalSpeaking(true),
            onEnd: () => setLocalSpeaking(false),
            onError: () => setLocalSpeaking(false),
          });
          if (!started) {
            setLocalSpeaking(false);
          }
        }
      } else {
        addMessage(
          "system",
          "Sarah did not return a new reply before the request timed out.",
        );
      }

      setStatus(lastState === "Thinking" ? "Online" : lastState);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Unable to reach Sarah's backend.";
      addMessage("system", message);
      setStatus("Backend offline");
    } finally {
      setSending(false);
    }
  };

  const displayStatus = localSpeaking ? "speaking" : status;

  return (
    <main style={styles.shell}>
      <section style={styles.app}>
        <aside style={styles.avatarPane}>
          <SarahAvatar
            status={displayStatus}
            mood={avatarMood}
            replySignal={replySignal}
            faceTestSignal={faceTestSignal}
            attentionSignal={attentionSignal}
          />
        </aside>

        <section style={styles.chatPane}>
          <header style={styles.header}>
            <div>
              <h1 style={styles.title}>Sarah.node</h1>
              <p style={styles.subtitle}>
                IT • Coding • Research • General assistant
              </p>
            </div>
            <div style={styles.headerControls}>
              <button
                type="button"
                onClick={() => setVoiceEnabled((enabled) => !enabled)}
                disabled={!speechAvailable}
                title={
                  speechAvailable
                    ? "Toggle Sarah's local Windows voice"
                    : "Local speech synthesis is unavailable in this runtime"
                }
                style={{
                  ...styles.voiceButton,
                  ...(!voiceEnabled || !speechAvailable
                    ? styles.voiceButtonMuted
                    : {}),
                }}
              >
                {voiceEnabled && speechAvailable ? "Voice On" : "Voice Off"}
              </button>
              <div style={styles.statusWrap}>
                <span style={styles.dot} />
                <span>{displayStatus}</span>
              </div>
            </div>
          </header>

          <div style={styles.messages} aria-live="polite">
            {messages.map((message) => (
              <article
                key={message.id}
                style={{
                  ...styles.message,
                  ...(message.role === "user"
                    ? styles.userMessage
                    : message.role === "system"
                      ? styles.systemMessage
                      : styles.assistantMessage),
                }}
              >
                <strong style={styles.label}>
                  {message.role === "user"
                    ? "You"
                    : message.role === "assistant"
                      ? "Sarah"
                      : "System"}
                </strong>
                <div style={styles.messageText}>
                  {message.role === "assistant" ? (
                    <MarkdownMessage content={message.content} />
                  ) : (
                    message.content
                  )}
                </div>
              </article>
            ))}
            <div ref={endRef} />
          </div>

          <form onSubmit={handleSubmit} style={styles.composer}>
            <textarea
              value={input}
              onFocus={() => setAttentionSignal((current) => current + 1)}
              onChange={(event) => {
                setInput(event.target.value);
                setAttentionSignal((current) => current + 1);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="Ask Sarah anything, or type /face-test to test expressions..."
              rows={2}
              disabled={sending}
              style={styles.input}
            />
            <button
              type="submit"
              disabled={sending || !input.trim()}
              style={styles.button}
            >
              {sending ? "Working..." : "Send"}
            </button>
          </form>
        </section>
      </section>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  shell: {
    height: "100vh",
    minHeight: "620px",
    background: "#080b10",
    color: "#f3f4f6",
    fontFamily:
      "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    display: "flex",
    justifyContent: "center",
    overflow: "hidden",
  },
  app: {
    width: "min(1440px, 100%)",
    height: "100vh",
    display: "grid",
    gridTemplateColumns: "minmax(300px, 36%) minmax(0, 1fr)",
    background: "#11141b",
    borderLeft: "1px solid #1d232d",
    borderRight: "1px solid #1d232d",
  },
  avatarPane: {
    minWidth: 0,
    minHeight: 0,
  },
  chatPane: {
    minWidth: 0,
    minHeight: 0,
    display: "grid",
    gridTemplateRows: "auto 1fr auto",
    background: "#11141b",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "20px",
    padding: "22px 28px",
    borderBottom: "1px solid #262b36",
  },
  title: {
    margin: 0,
    fontSize: "22px",
    letterSpacing: "0.02em",
  },
  subtitle: {
    margin: "4px 0 0",
    color: "#8f98a8",
    fontSize: "13px",
  },
  headerControls: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  voiceButton: {
    border: "1px solid #354052",
    borderRadius: "8px",
    padding: "6px 10px",
    background: "#182230",
    color: "#dce7f5",
    fontSize: "12px",
    fontWeight: 700,
    cursor: "pointer",
  },
  voiceButtonMuted: {
    background: "#11151d",
    color: "#7e8999",
  },
  statusWrap: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    color: "#b7c0ce",
    fontSize: "13px",
    whiteSpace: "nowrap",
  },
  dot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    background: "#73d39c",
  },
  messages: {
    minHeight: 0,
    overflowY: "auto",
    padding: "28px",
    display: "flex",
    flexDirection: "column",
    gap: "18px",
  },
  message: {
    maxWidth: "82%",
    padding: "14px 16px",
    borderRadius: "14px",
    lineHeight: 1.5,
  },
  assistantMessage: {
    alignSelf: "flex-start",
    background: "#1a1f29",
    border: "1px solid #2b3240",
  },
  userMessage: {
    alignSelf: "flex-end",
    background: "#252c39",
    border: "1px solid #374151",
  },
  systemMessage: {
    alignSelf: "center",
    maxWidth: "90%",
    background: "#241b1b",
    border: "1px solid #513434",
    color: "#f1b8b8",
  },
  label: {
    display: "block",
    marginBottom: "5px",
    fontSize: "12px",
    color: "#98a2b3",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
  messageText: {
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
  },
  composer: {
    display: "flex",
    gap: "12px",
    padding: "20px 28px 28px",
    borderTop: "1px solid #262b36",
  },
  input: {
    flex: 1,
    resize: "none",
    border: "1px solid #343b48",
    borderRadius: "12px",
    background: "#0c0f15",
    color: "#f3f4f6",
    padding: "13px 14px",
    font: "inherit",
    outline: "none",
  },
  button: {
    border: 0,
    borderRadius: "12px",
    padding: "0 22px",
    minWidth: "98px",
    background: "#e5e7eb",
    color: "#111827",
    fontWeight: 700,
    cursor: "pointer",
  },
};
