import React, { FormEvent, useEffect, useRef, useState } from "react";
import { fetchAssistantState, sendAssistantMessage } from "../lib/api";

type Message = {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
};

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

export function BasicChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    { id: 1, role: "assistant", content: "Sarah is ready. What are we working on?" },
  ]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState("Connecting");
  const [sending, setSending] = useState(false);
  const nextId = useRef(2);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetchAssistantState()
      .then((state) => {
        if (!cancelled) setStatus(state.assistant_state || "Online");
      })
      .catch(() => {
        if (!cancelled) setStatus("Backend offline");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const addMessage = (role: Message["role"], content: string) => {
    setMessages((current) => [...current, { id: nextId.current++, role, content }]);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const content = input.trim();
    if (!content || sending) return;

    setInput("");
    setSending(true);
    addMessage("user", content);

    try {
      const before = await fetchAssistantState().catch(() => null);
      const previousReply = before?.latest_reply ?? "";

      await sendAssistantMessage({ username: "zach", content, conversation_mode: "personal" });
      setStatus("Thinking");

      let reply = "";
      let lastState = "Thinking";

      for (let attempt = 0; attempt < 60; attempt += 1) {
        await sleep(500);
        const state = await fetchAssistantState();
        lastState = state.assistant_state || lastState;
        setStatus(lastState);

        if (state.latest_reply && state.latest_reply !== previousReply) {
          reply = state.latest_reply;
          break;
        }
      }

      if (reply) {
        addMessage("assistant", reply);
      } else {
        addMessage("system", "Sarah did not return a new reply before the request timed out.");
      }

      setStatus(lastState === "Thinking" ? "Online" : lastState);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to reach Sarah's backend.";
      addMessage("system", message);
      setStatus("Backend offline");
    } finally {
      setSending(false);
    }
  };

  return (
    <main style={styles.shell}>
      <section style={styles.app}>
        <header style={styles.header}>
          <div>
            <h1 style={styles.title}>Sarah.node</h1>
            <p style={styles.subtitle}>Basic assistant</p>
          </div>
          <div style={styles.statusWrap}>
            <span style={styles.dot} />
            <span>{status}</span>
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
                {message.role === "user" ? "You" : message.role === "assistant" ? "Sarah" : "System"}
              </strong>
              <div style={styles.messageText}>{message.content}</div>
            </article>
          ))}
          <div ref={endRef} />
        </div>

        <form onSubmit={handleSubmit} style={styles.composer}>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="Ask Sarah..."
            rows={2}
            disabled={sending}
            style={styles.input}
          />
          <button type="submit" disabled={sending || !input.trim()} style={styles.button}>
            {sending ? "Working..." : "Send"}
          </button>
        </form>
      </section>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  shell: {
    minHeight: "100vh",
    background: "#0b0d12",
    color: "#f3f4f6",
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    display: "flex",
    justifyContent: "center",
  },
  app: {
    width: "min(980px, 100%)",
    minHeight: "100vh",
    display: "grid",
    gridTemplateRows: "auto 1fr auto",
    background: "#11141b",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "22px 28px",
    borderBottom: "1px solid #262b36",
  },
  title: { margin: 0, fontSize: "22px", letterSpacing: "0.02em" },
  subtitle: { margin: "4px 0 0", color: "#8f98a8", fontSize: "13px" },
  statusWrap: { display: "flex", alignItems: "center", gap: "8px", color: "#b7c0ce", fontSize: "13px" },
  dot: { width: "8px", height: "8px", borderRadius: "50%", background: "#73d39c" },
  messages: { overflowY: "auto", padding: "28px", display: "flex", flexDirection: "column", gap: "18px" },
  message: { maxWidth: "78%", padding: "14px 16px", borderRadius: "14px", lineHeight: 1.5 },
  assistantMessage: { alignSelf: "flex-start", background: "#1a1f29", border: "1px solid #2b3240" },
  userMessage: { alignSelf: "flex-end", background: "#252c39", border: "1px solid #374151" },
  systemMessage: { alignSelf: "center", maxWidth: "90%", background: "#241b1b", border: "1px solid #513434", color: "#f1b8b8" },
  label: { display: "block", marginBottom: "5px", fontSize: "12px", color: "#98a2b3", textTransform: "uppercase", letterSpacing: "0.08em" },
  messageText: { whiteSpace: "pre-wrap", overflowWrap: "anywhere" },
  composer: { display: "flex", gap: "12px", padding: "20px 28px 28px", borderTop: "1px solid #262b36" },
  input: { flex: 1, resize: "none", border: "1px solid #343b48", borderRadius: "12px", background: "#0c0f15", color: "#f3f4f6", padding: "13px 14px", font: "inherit", outline: "none" },
  button: { border: 0, borderRadius: "12px", padding: "0 22px", minWidth: "98px", background: "#e5e7eb", color: "#111827", fontWeight: 700, cursor: "pointer" },
};
