import type { SystemEvent } from '../types/events';

type Props = { events: SystemEvent[] };

export function StatusCards({ events }: Props) {
  const latestSpeaking = events.find((e) => e.type === 'speaking_status');
  const latestModeration = events.find((e) => e.type === 'moderation_decision');
  const latestReply = events.find((e) => e.type === 'reply_selected');

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
      <Card title="Speaking" value={JSON.stringify(latestSpeaking?.payload ?? { is_speaking: false })} />
      <Card title="Moderation" value={JSON.stringify(latestModeration?.payload ?? {})} />
      <Card title="Chosen Reply" value={JSON.stringify(latestReply?.payload ?? {})} />
    </div>
  );
}

function Card({ title, value }: { title: string; value: string }) {
  return (
    <div style={{ border: '1px solid #444', borderRadius: 8, padding: 10 }}>
      <h3>{title}</h3>
      <small>{value}</small>
    </div>
  );
}
