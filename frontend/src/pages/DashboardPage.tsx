import { EventLog } from '../components/EventLog';
import { StatusCards } from '../components/StatusCards';
import { sendSimpleMockChat } from '../lib/api';
import { useEvents } from '../hooks/useEvents';

export function DashboardPage() {
  const { events, connectionState } = useEvents();

  return (
    <main style={{ maxWidth: 1000, margin: '20px auto', padding: '0 12px', fontFamily: 'sans-serif' }}>
      <h1>SarahNode Dashboard</h1>
      <p style={{ marginTop: 0 }}>WebSocket status: {connectionState}</p>
      <button
        type="button"
        onClick={() => sendSimpleMockChat('demo-user', 'hello nova!', 2)}
        style={{ marginBottom: 16 }}
      >
        Send Demo Chat
      </button>
      <StatusCards events={events} connectionState={connectionState} />
      <EventLog events={events} />
    </main>
  );
}
