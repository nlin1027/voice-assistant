import { useEffect, useMemo, useState, type FormEvent } from 'react';

import { supabase } from '../lib/supabase';
import { addMonths, getMonthGrid, isSameDay, toDateKey } from '../lib/calendarDate';

interface ScheduleEvent {
  id: string;
  title: string;
  starts_at: string;
  ends_at: string | null;
  notes: string | null;
  source: 'manual' | 'agent';
}

const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const formatTime = (iso: string) =>
  new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });

const formatWhen = (starts_at: string, ends_at: string | null) => {
  const startText = formatTime(starts_at);
  if (!ends_at) return startText;
  return `${startText} – ${formatTime(ends_at)}`;
};

export const SchedulePage = () => {
  const [events, setEvents] = useState<ScheduleEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [visibleMonth, setVisibleMonth] = useState(() => new Date());
  const [selectedDate, setSelectedDate] = useState(() => new Date());

  const [title, setTitle] = useState('');
  const [time, setTime] = useState('09:00');
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

  const eventsByDay = useMemo(() => {
    const map = new Map<string, ScheduleEvent[]>();
    for (const event of events) {
      const key = toDateKey(new Date(event.starts_at));
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(event);
    }
    return map;
  }, [events]);

  const gridDays = useMemo(
    () => getMonthGrid(visibleMonth.getFullYear(), visibleMonth.getMonth()),
    [visibleMonth]
  );

  const selectedDayEvents = eventsByDay.get(toDateKey(selectedDate)) ?? [];
  const today = new Date();

  const handleSelectDay = (day: Date) => {
    setSelectedDate(day);
    if (day.getMonth() !== visibleMonth.getMonth() || day.getFullYear() !== visibleMonth.getFullYear()) {
      setVisibleMonth(day);
    }
  };

  const goToday = () => {
    const now = new Date();
    setVisibleMonth(now);
    setSelectedDate(now);
  };

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault();
    if (!supabase || !title.trim() || !time) return;
    const [hours, minutes] = time.split(':').map(Number);
    const startsAt = new Date(selectedDate);
    startsAt.setHours(hours, minutes, 0, 0);

    setSubmitting(true);
    const { error } = await supabase
      .from('schedule_events')
      .insert({ title, starts_at: startsAt.toISOString(), notes: notes || null, source: 'manual' });
    setSubmitting(false);
    if (error) {
      setError(error.message);
      return;
    }
    setTitle('');
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
    <div className="w-full max-w-6xl mx-auto flex flex-col lg:flex-row gap-4 sm:gap-6 px-3 sm:px-6 py-4 sm:py-6">
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-lg sm:text-xl font-semibold text-foreground">
            {visibleMonth.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
          </h1>
          <div className="flex items-center gap-1.5">
            <button
              onClick={goToday}
              className="text-xs font-medium px-2.5 py-1.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-foreground/40 transition-colors"
            >
              Today
            </button>
            <button
              onClick={() => setVisibleMonth((m) => addMonths(m, -1))}
              aria-label="Previous month"
              className="w-8 h-8 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-card transition-colors"
            >
              ‹
            </button>
            <button
              onClick={() => setVisibleMonth((m) => addMonths(m, 1))}
              aria-label="Next month"
              className="w-8 h-8 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-card transition-colors"
            >
              ›
            </button>
          </div>
        </div>

        {error && <p className="text-destructive text-sm mb-3">{error}</p>}

        <div className="grid grid-cols-7 text-center text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
          {WEEKDAY_LABELS.map((label) => (
            <div key={label} className="py-1.5">
              {label}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7 border-t border-l border-border rounded-lg overflow-hidden">
          {gridDays.map((day) => {
            const key = toDateKey(day);
            const dayEvents = eventsByDay.get(key) ?? [];
            const isCurrentMonth = day.getMonth() === visibleMonth.getMonth();
            const isToday = isSameDay(day, today);
            const isSelected = isSameDay(day, selectedDate);
            const visiblePills = dayEvents.slice(0, 3);
            const overflowCount = dayEvents.length - visiblePills.length;

            return (
              <button
                key={key}
                onClick={() => handleSelectDay(day)}
                className={`flex flex-col items-start gap-1 border-r border-b border-border p-1.5 sm:p-2 text-left min-h-[72px] sm:min-h-[108px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:z-10 ${
                  isSelected ? 'bg-primary/5' : 'hover:bg-card/60'
                }`}
              >
                <span
                  className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium shrink-0 ${
                    isToday
                      ? 'bg-primary text-primary-foreground'
                      : isCurrentMonth
                        ? 'text-foreground'
                        : 'text-muted-foreground/50'
                  }`}
                >
                  {day.getDate()}
                </span>

                <div className="hidden sm:flex flex-col gap-0.5 w-full">
                  {visiblePills.map((event) => (
                    <span
                      key={event.id}
                      className={`truncate rounded px-1.5 py-0.5 text-[10px] font-medium leading-tight ${
                        event.source === 'agent'
                          ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
                          : 'bg-primary/15 text-primary'
                      }`}
                    >
                      {formatTime(event.starts_at)} {event.title}
                    </span>
                  ))}
                  {overflowCount > 0 && (
                    <span className="text-[10px] text-muted-foreground px-1.5">+{overflowCount} more</span>
                  )}
                </div>

                <div className="flex sm:hidden gap-0.5 mt-0.5">
                  {dayEvents.slice(0, 4).map((event) => (
                    <span
                      key={event.id}
                      className={`w-1.5 h-1.5 rounded-full ${
                        event.source === 'agent' ? 'bg-amber-500' : 'bg-primary'
                      }`}
                    />
                  ))}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="w-full lg:w-80 shrink-0 flex flex-col gap-4 lg:sticky lg:top-6 lg:self-start">
        <div>
          <h2 className="text-sm font-semibold text-foreground">
            {selectedDate.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {loading
              ? 'Loading…'
              : selectedDayEvents.length === 0
                ? 'Nothing scheduled'
                : `${selectedDayEvents.length} event${selectedDayEvents.length === 1 ? '' : 's'}`}
          </p>
        </div>

        {selectedDayEvents.length > 0 && (
          <ul className="flex flex-col gap-2">
            {selectedDayEvents.map((event) => (
              <li
                key={event.id}
                className="flex items-start justify-between gap-3 bg-card border border-border rounded-md px-3 py-2.5"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{event.title}</p>
                  <p className="text-xs text-muted-foreground">{formatWhen(event.starts_at, event.ends_at)}</p>
                  {event.notes && <p className="text-xs text-muted-foreground mt-1">{event.notes}</p>}
                  {event.source === 'agent' && (
                    <span className="inline-block mt-1 text-[10px] uppercase tracking-wide text-amber-600 dark:text-amber-400">
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

        <form onSubmit={handleAdd} className="flex flex-col gap-2 border-t border-border pt-4">
          <input
            type="text"
            placeholder="Add an event…"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="bg-card border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground"
            required
          />
          <div className="flex gap-2">
            <input
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
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
      </div>
    </div>
  );
};
