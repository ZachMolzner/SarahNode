import type { SystemEvent } from '../types/events';

type Props = { events: SystemEvent[] };

export function StatusCards({ events }: Props) {
  const latestSpeaking = events.find((e) => e.type === 'speaking_status');
  const latestModeration = events.find((e) => e.type === 'moderation_decision');
  const latestReply = events.find((e) => e.type === 'reply_selected');

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }}>
      <Card title='Speaking Status' value={JSON.stringify(latestSpeaking?.payload ?? { is_speaking: false })} />
      <Card title='Moderation Decision' value={JSON.stringify(latestModeration?.payload ?? { pending: true })} />
      <Card title='Chosen Reply' value={JSON.stringify(latestReply?.payload ?? { pending: true })} />
    </div>
  );
}

function Card({ title, value }: { title: string; value: string }) {
  return (
    <div
      style={{
        border: '1px solid #374151',
        borderRadius: 10,
        padding: 12,
        background: '#111827',
        minHeight: 92,
      }}
    >
      <h3 style={{ marginTop: 0, marginBottom: 8, fontSize: '1rem' }}>{title}</h3>
      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12 }}>{value}</pre>
    </div>
  );
}
