import { useEffect, useState } from 'react';
import type { SystemEvent } from '../types/events';

export function useEvents(url: string): SystemEvent[] {
  const [events, setEvents] = useState<SystemEvent[]>([]);

  useEffect(() => {
    const ws = new WebSocket(url);
    ws.onmessage = (event) => {
      const parsed: SystemEvent = JSON.parse(event.data);
      setEvents((current) => [parsed, ...current].slice(0, 100));
    };
    return () => ws.close();
  }, [url]);

  return events;
}
