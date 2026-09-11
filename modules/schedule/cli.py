"""Schedule module CLI. Stdlib-only so it runs unmodified in Hermes' sandboxed
container (python3.11, no pip install step at task time).

Talks directly to Supabase's REST API (PostgREST) over HTTPS. SUPABASE_URL and
SUPABASE_ANON_KEY are read from a .env file sitting next to this script (see
_load_local_env()) -- that file rides along with this module's existing
read-only bind mount, so it's always present inside the container regardless
of risk. This was previously read from the environment, injected by
broker/hermes.py via Hermes' TERMINAL_DOCKER_FORWARD_ENV -- that forwarding
step turned out to be unreliable (intermittently absent inside the container
for no config-side reason), so the environment is now only a fallback for
local/host testing. MODULES_RISK is still environment-only -- it's set fresh
per task by broker/hermes.py, not a static credential a file would help with.

All times are Eastern (America/New_York, EST/EDT as the date requires).
Give --start/--end/--from/--to as a plain local wall-clock timestamp, e.g.
2026-09-10T14:00:00 for 2pm Eastern -- no "Z" or offset needed. Any offset
that is included is ignored and replaced with the correct Eastern one, so
the schedule can never end up with a mix of timezones; the DST cutover is
computed from the fixed U.S. rule (2nd Sunday in March / 1st Sunday in
November) rather than the system's tzdata, which the sandbox may not have.

Usage:
    python3 cli.py list [--from LOCAL_ISO] [--to LOCAL_ISO]
    python3 cli.py add --title TEXT --start LOCAL_ISO [--end LOCAL_ISO] [--notes TEXT]
    python3 cli.py update ID [--title TEXT] [--start LOCAL_ISO] [--end LOCAL_ISO] [--notes TEXT]
    python3 cli.py remove ID

All commands print JSON to stdout on success. Errors go to stderr with a
non-zero exit code. add/update/remove require MODULES_RISK=edit -- this task
was dispatched with a different risk, refuse rather than silently no-op.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

WRITE_COMMANDS = {"add", "update", "remove"}

_TZ_SUFFIX_RE = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")


def _load_local_env():
    """Parse the .env file next to this script, if present. Deliberately not
    python-dotenv -- this must run with zero pip installs inside Hermes'
    sandbox, so it's a minimal KEY=VALUE parser, good enough for this file's
    two flat values."""
    path = Path(__file__).resolve().parent / ".env"
    values = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


_LOCAL_ENV = _load_local_env()


def _nth_sunday(year, month, n):
    first = datetime(year, month, 1)
    days_to_sunday = (6 - first.weekday()) % 7
    return first + timedelta(days=days_to_sunday, weeks=n - 1)


def _eastern_utc_offset(naive_dt):
    """UTC offset for US Eastern time at this naive local date, per the fixed
    U.S. DST rule (2nd Sunday in March 2am - 1st Sunday in November 2am)."""
    year = naive_dt.year
    dst_start = _nth_sunday(year, 3, 2).replace(hour=2)
    dst_end = _nth_sunday(year, 11, 1).replace(hour=2)
    return timedelta(hours=-4) if dst_start <= naive_dt < dst_end else timedelta(hours=-5)


def _eastern_iso(value):
    """Reinterpret an ISO 8601 timestamp as Eastern local time and return it
    with the correct EST/EDT offset attached. Any existing offset/Z suffix on
    the input is stripped first, so the wall-clock digits are always taken as
    Eastern regardless of what was appended -- times can't end up mixed."""
    if value is None:
        return None
    naive = _TZ_SUFFIX_RE.sub("", value)
    try:
        naive_dt = datetime.fromisoformat(naive)
    except ValueError:
        print(f"error: could not parse '{value}' as an ISO 8601 timestamp", file=sys.stderr)
        sys.exit(1)
    offset = _eastern_utc_offset(naive_dt)
    total_minutes = int(offset.total_seconds() // 60)
    sign = "-" if total_minutes < 0 else "+"
    total_minutes = abs(total_minutes)
    offset_str = f"{sign}{total_minutes // 60:02d}:{total_minutes % 60:02d}"
    return naive_dt.isoformat() + offset_str


def _env(name):
    # The .env file next to this script is checked first -- it's reliably present
    # (bind-mounted alongside this code), unlike the environment, which depends on
    # Hermes forwarding it into the container correctly on every single task.
    value = _LOCAL_ENV.get(name) or os.environ.get(name)
    if not value:
        print(
            f"error: {name} is not set (checked modules/schedule/.env and this task's environment)",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def _request(method, path, body=None):
    url = _env("SUPABASE_URL").rstrip("/") + "/rest/v1/" + path
    key = _env("SUPABASE_ANON_KEY")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if method in ("POST", "PATCH"):
        headers["Prefer"] = "return=representation"

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(f"error: schedule request failed ({e.code}): {detail}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"error: could not reach Supabase: {e.reason}", file=sys.stderr)
        sys.exit(1)

    return json.loads(raw) if raw else []


def cmd_list(args):
    path = "schedule_events?select=*&order=starts_at.asc"
    if args.from_:
        path += f"&starts_at=gte.{_eastern_iso(args.from_)}"
    if args.to:
        path += f"&starts_at=lte.{_eastern_iso(args.to)}"
    print(json.dumps(_request("GET", path), indent=2))


def cmd_add(args):
    body = [{
        "title": args.title,
        "starts_at": _eastern_iso(args.start),
        "ends_at": _eastern_iso(args.end),
        "notes": args.notes,
        "source": "agent",
    }]
    print(json.dumps(_request("POST", "schedule_events", body), indent=2))


def cmd_update(args):
    fields = {}
    if args.title is not None:
        fields["title"] = args.title
    if args.start is not None:
        fields["starts_at"] = _eastern_iso(args.start)
    if args.end is not None:
        fields["ends_at"] = _eastern_iso(args.end)
    if args.notes is not None:
        fields["notes"] = args.notes
    if not fields:
        print("error: update needs at least one of --title/--start/--end/--notes", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(_request("PATCH", f"schedule_events?id=eq.{args.id}", fields), indent=2))


def cmd_remove(args):
    print(json.dumps(_request("DELETE", f"schedule_events?id=eq.{args.id}"), indent=2))


def main():
    parser = argparse.ArgumentParser(description="Schedule module CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List schedule entries, soonest first")
    p_list.add_argument("--from", dest="from_", help="Eastern local time, e.g. 2026-09-10T00:00:00")
    p_list.add_argument("--to", help="Eastern local time, only entries starting at/before this")
    p_list.set_defaults(func=cmd_list)

    p_add = sub.add_parser("add", help="Add a schedule entry")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--start", required=True, help="Eastern local start time, e.g. 2026-09-10T14:00:00")
    p_add.add_argument("--end", help="Eastern local end time")
    p_add.add_argument("--notes")
    p_add.set_defaults(func=cmd_add)

    p_update = sub.add_parser("update", help="Update a schedule entry by id")
    p_update.add_argument("id")
    p_update.add_argument("--title")
    p_update.add_argument("--start", help="Eastern local start time")
    p_update.add_argument("--end", help="Eastern local end time")
    p_update.add_argument("--notes")
    p_update.set_defaults(func=cmd_update)

    p_remove = sub.add_parser("remove", help="Remove a schedule entry by id")
    p_remove.add_argument("id")
    p_remove.set_defaults(func=cmd_remove)

    args = parser.parse_args()

    if args.command in WRITE_COMMANDS and os.environ.get("MODULES_RISK") != "edit":
        risk = os.environ.get("MODULES_RISK", "<unset>")
        print(
            f"error: '{args.command}' modifies the schedule and requires risk=edit "
            f"(this task was dispatched with risk={risk}). Refusing.",
            file=sys.stderr,
        )
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
