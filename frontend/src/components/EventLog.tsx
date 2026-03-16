import type { SystemEvent } from '../types/events';

type Props = { events: SystemEvent[] };

export function EventLog({ events }: Props) {
  return (
    <div>
      <h3>Event Log</h3>
      <ul style={{ maxHeight: 300, overflowY: 'auto', padding: 0, listStyle: 'none' }}>
        {events.map((event, idx) => (
          <li key={`${event.timestamp}-${idx}`} style={{ borderBottom: '1px solid #333', padding: '6px 0' }}>
            <strong>{event.type}</strong> - {JSON.stringify(event.payload)}
          </li>
        ))}
      </ul>
    </div>
  );
}
