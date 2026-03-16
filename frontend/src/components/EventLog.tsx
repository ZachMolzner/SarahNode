import type { SystemEvent } from '../types/events';

type Props = {
  events: SystemEvent[];
};

export function EventLog({ events }: Props) {
  return (
    <section>
      <h2>Live Events</h2>
      <ul style={{ maxHeight: 420, overflowY: 'auto', listStyle: 'none', padding: 0, margin: 0 }}>
        {events.map((event, index) => (
          <li
            key={`${event.timestamp}-${index}`}
            style={{ borderBottom: '1px solid #eee', padding: '10px 0', fontFamily: 'monospace', fontSize: 13 }}
          >
            <div>
              <strong>{event.type}</strong>
            </div>
            <div>{event.timestamp}</div>
            <pre style={{ margin: '6px 0 0 0', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {JSON.stringify(event.payload, null, 2)}
            </pre>
          </li>
        ))}
      </ul>
    </section>
  );
}
