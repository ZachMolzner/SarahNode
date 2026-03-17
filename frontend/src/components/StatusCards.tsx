import type { ConnectionState, SystemEvent } from "../types/events";

type Props = {
  events: SystemEvent[];
  connectionState: ConnectionState;
  isAudioPlaying: boolean;
};

function findLatestEvent(events: SystemEvent[], type: string): SystemEvent | undefined {
  return events.find((event) => event.type === type);
}

export function StatusCards({ events, connectionState, isAudioPlaying }: Props) {
  const assistantStateEvent = findLatestEvent(events, "assistant_state");
  const latestSafetyEvent = findLatestEvent(events, "moderation_decision");
  const latestReplyEvent = findLatestEvent(events, "reply_selected");
  const latestAvatarEvent = findLatestEvent(events, "avatar_event");
  const latestSpeakingEvent = findLatestEvent(events, "speaking_status");

  const assistantState = assistantStateEvent?.payload?.["state"];
  const avatarState = latestAvatarEvent?.payload?.["state"];
  const latestReply = latestReplyEvent?.payload?.["text"];

  return (
    <section
      style={{
        display: "grid",
        gap: 12,
        gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
      }}
    >
      <Card title="WebSocket" value={String(connectionState)} />
      <Card title="Assistant Status" value={String(assistantState ?? "idle")} />
      <Card title="Voice" value={readSpeaking(latestSpeakingEvent)} />
      <Card title="Safety Filter" value={readSafetyFilter(latestSafetyEvent)} />
      <Card title="Audio Playback" value={isAudioPlaying ? "playing" : "idle"} />
      <Card title="Presence / Avatar" value={String(avatarState ?? assistantState ?? "idle")} />
      <Card title="Latest Reply" value={typeof latestReply === "string" ? latestReply : "No reply yet"} />
    </section>
  );
}

function readSpeaking(event: SystemEvent | undefined): string {
  if (!event) return "idle";

  const isSpeaking = event.payload?.["is_speaking"];
  const emotion = event.payload?.["emotion"];

  if (isSpeaking === true) {
    return typeof emotion === "string" ? `speaking (${emotion})` : "speaking";
  }

  return "idle";
}

function readSafetyFilter(event: SystemEvent | undefined): string {
  if (!event) return "No moderation events yet";

  const allowed = event.payload?.["allowed"];
  if (allowed === true) return "allowed";

  const category = event.payload?.["category"];
  return typeof category === "string" ? `blocked (${category})` : "blocked";
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
