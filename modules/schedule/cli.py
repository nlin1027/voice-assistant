"""Schedule module CLI. Stdlib-only so it runs unmodified in Hermes' sandboxed
container (python3.11, no pip install step at task time).

Talks directly to Supabase's REST API (PostgREST) over HTTPS. Reads
SUPABASE_URL, SUPABASE_ANON_KEY, and MODULES_RISK from the environment --
these are injected by broker/hermes.py, not passed as CLI args.

Usage:
    python3 cli.py list [--from ISO] [--to ISO]
    python3 cli.py add --title TEXT --start ISO [--end ISO] [--notes TEXT]
    python3 cli.py update ID [--title TEXT] [--start ISO] [--end ISO] [--notes TEXT]
    python3 cli.py remove ID

All commands print JSON to stdout on success. Errors go to stderr with a
non-zero exit code. add/update/remove require MODULES_RISK=edit -- this task
was dispatched with a different risk, refuse rather than silently no-op.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

WRITE_COMMANDS = {"add", "update", "remove"}


def _env(name):
    value = os.environ.get(name)
    if not value:
        print(f"error: {name} is not set in this task's environment", file=sys.stderr)
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
        path += f"&starts_at=gte.{args.from_}"
    if args.to:
        path += f"&starts_at=lte.{args.to}"
    print(json.dumps(_request("GET", path), indent=2))


def cmd_add(args):
    body = [{
        "title": args.title,
        "starts_at": args.start,
        "ends_at": args.end,
        "notes": args.notes,
        "source": "agent",
    }]
    print(json.dumps(_request("POST", "schedule_events", body), indent=2))


def cmd_update(args):
    fields = {}
    if args.title is not None:
        fields["title"] = args.title
    if args.start is not None:
        fields["starts_at"] = args.start
    if args.end is not None:
        fields["ends_at"] = args.end
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
    p_list.add_argument("--from", dest="from_", help="ISO 8601, only entries starting at/after this")
    p_list.add_argument("--to", help="ISO 8601, only entries starting at/before this")
    p_list.set_defaults(func=cmd_list)

    p_add = sub.add_parser("add", help="Add a schedule entry")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--start", required=True, help="ISO 8601 start time, e.g. 2026-09-10T14:00:00Z")
    p_add.add_argument("--end", help="ISO 8601 end time")
    p_add.add_argument("--notes")
    p_add.set_defaults(func=cmd_add)

    p_update = sub.add_parser("update", help="Update a schedule entry by id")
    p_update.add_argument("id")
    p_update.add_argument("--title")
    p_update.add_argument("--start")
    p_update.add_argument("--end")
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
