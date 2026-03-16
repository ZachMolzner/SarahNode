import { EventLog } from '../components/EventLog';
import { StatusCards } from '../components/StatusCards';
import { useEvents } from '../hooks/useEvents';

export function DashboardPage() {
  const events = useEvents('ws://localhost:8000/ws/events');

  return (
    <main
      style={{
        maxWidth: 1100,
        margin: '24px auto',
        fontFamily: 'Inter, system-ui, sans-serif',
        color: '#e5e7eb',
        padding: '0 16px',
      }}
    >
      <section
        style={{
          background: 'linear-gradient(135deg, #111827 0%, #1f2937 100%)',
          border: '1px solid #374151',
          borderRadius: 12,
          padding: 16,
          marginBottom: 16,
        }}
      >
        <h1 style={{ margin: 0 }}>VTuber Assistant Control Panel</h1>
        <p style={{ margin: '8px 0 0', opacity: 0.85 }}>
          Live view of chat ingestion, moderation, selected replies, speaking state, and avatar events.
        </p>
        <small style={{ opacity: 0.75 }}>
          WebSocket: <code>ws://localhost:8000/ws/events</code> • Events buffered: {events.length}
        </small>
      </section>

      <StatusCards events={events} />

      <section
        style={{
          marginTop: 16,
          border: '1px solid #374151',
          borderRadius: 12,
          background: '#0b1220',
          padding: 12,
        }}
      >
        <EventLog events={events} />
      </section>
    </main>
  );
}
