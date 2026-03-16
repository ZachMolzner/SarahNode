import { EventLog } from '../components/EventLog';
import { StatusCards } from '../components/StatusCards';
import { useEvents } from '../hooks/useEvents';

export function DashboardPage() {
  const events = useEvents('ws://localhost:8000/ws/events');

  return (
    <main style={{ maxWidth: 1000, margin: '20px auto', fontFamily: 'sans-serif' }}>
      <h1>VTuber Assistant Control Panel</h1>
      <StatusCards events={events} />
      <EventLog events={events} />
    </main>
  );
}
