import { useEffect, useState, type FormEvent } from 'react';

import { supabase } from '../lib/supabase';

interface ScheduleEvent {
  id: string;
  title: string;
  starts_at: string;
  ends_at: string | null;
  notes: string | null;
  source: 'manual' | 'agent';
}

const formatWhen = (starts_at: string, ends_at: string | null) => {
  const start = new Date(starts_at);
  const startText = start.toLocaleString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
  if (!ends_at) return startText;
  const end = new Date(ends_at);
  const endText = end.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  return `${startText} – ${endText}`;
};

export const SchedulePage = () => {
  const [events, setEvents] = useState<ScheduleEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [start, setStart] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    if (!supabase) {
      setLoading(false);
      return;
    }
    const { data, error } = await supabase
      .from('schedule_events')
      .select('*')
      .order('starts_at', { ascending: true });
    if (error) setError(error.message);
    else setEvents(data as ScheduleEvent[]);
    setLoading(false);
  };

  useEffect(() => {
    load();
    const client = supabase;
    if (!client) return;

    // Live updates so entries Hermes adds show up here without a manual refresh.
    const channel = client
      .channel('schedule_events_changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'schedule_events' }, load)
      .subscribe();

    return () => {
      client.removeChannel(channel);
    };
  }, []);

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault();
    if (!supabase || !title.trim() || !start) return;
    setSubmitting(true);
    const { error } = await supabase
      .from('schedule_events')
      .insert({ title, starts_at: new Date(start).toISOString(), notes: notes || null, source: 'manual' });
    setSubmitting(false);
    if (error) {
      setError(error.message);
      return;
    }
    setTitle('');
    setStart('');
    setNotes('');
  };

  const handleRemove = async (id: string) => {
    if (!supabase) return;
    const { error } = await supabase.from('schedule_events').delete().eq('id', id);
    if (error) setError(error.message);
  };

  if (!supabase) {
    return (
      <div className="w-full max-w-xl mx-auto px-6 py-10">
        <h1 className="text-xl font-semibold text-foreground mb-4">Schedule</h1>
        <p className="text-muted-foreground text-sm">
          Not configured yet — set <code className="text-foreground">VITE_SUPABASE_URL</code> and{' '}
          <code className="text-foreground">VITE_SUPABASE_ANON_KEY</code> in{' '}
          <code className="text-foreground">bot/client/.env</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-xl mx-auto px-6 py-10">
      <h1 className="text-xl font-semibold text-foreground mb-6">Schedule</h1>

      <form onSubmit={handleAdd} className="flex flex-col gap-3 mb-10">
        <input
          type="text"
          placeholder="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="bg-card border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground"
          required
        />
        <div className="flex gap-3">
          <input
            type="datetime-local"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="flex-1 bg-card border border-border rounded-md px-3 py-2 text-sm text-foreground"
            required
          />
          <button
            type="submit"
            disabled={submitting}
            className="bg-primary text-primary-foreground rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            Add
          </button>
        </div>
        <input
          type="text"
          placeholder="Notes (optional)"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="bg-card border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground"
        />
      </form>

      {error && <p className="text-destructive text-sm mb-4">{error}</p>}

      {loading ? (
        <p className="text-muted-foreground text-sm">Loading…</p>
      ) : events.length === 0 ? (
        <p className="text-muted-foreground text-sm">Nothing scheduled yet.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {events.map((event) => (
            <li
              key={event.id}
              className="flex items-start justify-between gap-4 bg-card border border-border rounded-md px-4 py-3"
            >
              <div>
                <p className="text-sm font-medium text-foreground">{event.title}</p>
                <p className="text-xs text-muted-foreground">{formatWhen(event.starts_at, event.ends_at)}</p>
                {event.notes && <p className="text-xs text-muted-foreground mt-1">{event.notes}</p>}
                {event.source === 'agent' && (
                  <span className="inline-block mt-1 text-[10px] uppercase tracking-wide text-primary">
                    added by agent
                  </span>
                )}
              </div>
              <button
                onClick={() => handleRemove(event.id)}
                aria-label={`Remove ${event.title}`}
                className="text-muted-foreground hover:text-destructive text-sm shrink-0"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
