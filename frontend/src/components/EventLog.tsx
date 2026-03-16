import type { SystemEvent } from '../types/events';

type Props = { events: SystemEvent[] };

export function EventLog({ events }: Props) {
  return (
    <div>
      <h3 style={{ marginTop: 0 }}>Event Log</h3>
      <ul style={{ maxHeight: 340, overflowY: 'auto', padding: 0, listStyle: 'none', margin: 0 }}>
        {events.length === 0 ? (
          <li style={{ opacity: 0.75, padding: '6px 0' }}>No events yet. Start backend and post a mock chat message.</li>
        ) : (
          events.map((event, idx) => (
            <li key={`${event.timestamp}-${idx}`} style={{ borderBottom: '1px solid #1f2937', padding: '8px 0' }}>
              <strong>{event.type}</strong>
              <div style={{ fontSize: 12, opacity: 0.8 }}>{new Date(event.timestamp).toLocaleTimeString()}</div>
              <pre style={{ margin: '4px 0 0', whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12 }}>
                {JSON.stringify(event.payload)}
              </pre>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
