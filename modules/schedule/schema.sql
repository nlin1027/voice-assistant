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
