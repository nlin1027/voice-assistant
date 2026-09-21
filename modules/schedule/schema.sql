-- Schedule module. Paste this into the Supabase SQL editor once, on a fresh project.

create table if not exists schedule_events (
  id         uuid primary key default gen_random_uuid(),
  title      text not null,
  starts_at  timestamptz not null,
  ends_at    timestamptz,
  notes      text,
  source     text not null default 'manual' check (source in ('manual', 'agent')),
  created_at timestamptz not null default now()
);

create index if not exists schedule_events_starts_at_idx on schedule_events (starts_at);

alter table schedule_events enable row level security;

-- Personal single-user project: the anon key is the trust boundary, gated by putting the
-- client app behind the same Cloudflare Access policy as the bot (see project plan). Open
-- policy for the anon role — revisit if this project ever has more than one user.
create policy "anon full access" on schedule_events
  for all
  to anon
  using (true)
  with check (true);

-- One freeform note per day or per week. scope_date is a plain date (no time-of-day, no
-- timezone conversion needed) — for scope='day' it's the day itself; for scope='week' it's
-- the Sunday that starts that week, matching the client calendar's Sunday-start weeks. The
-- composite primary key makes "the note for this day/week" a natural upsert target (one row
-- per period) instead of needing lookup-by-id like schedule_events.
create table if not exists schedule_notes (
  scope       text not null check (scope in ('day', 'week')),
  scope_date  date not null,
  content     text not null,
  source      text not null default 'manual' check (source in ('manual', 'agent')),
  updated_at  timestamptz not null default now(),
  primary key (scope, scope_date)
);

alter table schedule_notes enable row level security;

create policy "anon full access" on schedule_notes
  for all
  to anon
  using (true)
  with check (true);
