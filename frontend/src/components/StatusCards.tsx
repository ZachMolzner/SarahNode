import type { ConnectionState, SystemEvent } from "../types/events";

type Props = {
  events: SystemEvent[];
  connectionState: ConnectionState;
};

export function StatusCards({ events, connectionState }: Props) {
  const latestSpeaking = events.find((event) => event.type === "speaking_status");
  const latestModeration = events.find((event) => event.type === "moderation_decision");
  const latestReply = events.find((event) => event.type === "reply_selected");

  return (
    <section
      style={{
        display: "grid",
        gap: 12,
        gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
      }}
    >
      <Card title="WebSocket" value={connectionState} />
      <Card title="Speaking" value={readSpeaking(latestSpeaking)} />
      <Card title="Moderation" value={readModeration(latestModeration)} />
      <Card title="Latest Reply" value={readReply(latestReply)} />
    </section>
  );
}

function readSpeaking(event: SystemEvent | undefined): string {
  const isSpeaking = event?.payload?.["is_speaking"];
  return isSpeaking === true ? "speaking" : "idle";
}

function readModeration(event: SystemEvent | undefined): string {
  if (!event) return "No moderation events yet";

  const allowed = event.payload?.["allowed"];
  if (allowed === true) return "allowed";

  const category = event.payload?.["category"];
  return typeof category === "string" ? `blocked (${category})` : "blocked";
}

function readReply(event: SystemEvent | undefined): string {
  if (!event) return "No reply selected yet";

  const text = event.payload?.["text"];
  return typeof text === "string" ? text : "Reply unavailable";
}

function Card({ title, value }: { title: string; value: string }) {
  return (
    <article
      style={{
        border: "1px solid #2a2a2a",
        borderRadius: 12,
        padding: 16,
        background: "#161616",
      }}
    >
      <h3 style={{ margin: "0 0 8px" }}>{title}</h3>
      <p style={{ margin: 0, lineHeight: 1.5, opacity: 0.9 }}>{value}</p>
    </article>
  );
}
