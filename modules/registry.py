"""Registry of modules Hermes can access via CLI. Each entry mounts a module's
CLI directory (always read-only -- it's code, not data) into the Hermes
sandbox container and describes it in the task prompt.

Adding a module later: drop a new package under modules/, add one entry here.
The broker (broker/hermes.py) doesn't need to change.
"""

from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent

MODULES = [
    {
        "name": "schedule",
        "host_dir": MODULE_ROOT / "schedule",
        "container_dir": "/mnt/modules/schedule",
        "describe": (
            "schedule -- personal schedule, backed by a cloud database. Run with "
            "`python3 /mnt/modules/schedule/cli.py <command> ...`.\n"
            "  list [--from ISO] [--to ISO]   List entries, soonest first.\n"
            "  add --title T --start ISO [--end ISO] [--notes T]   Add an entry.\n"
            "  update ID [--title T] [--start ISO] [--end ISO] [--notes T]   Update an entry.\n"
            "  remove ID   Remove an entry.\n"
            "  All times are Eastern (America/New_York). Give ISO timestamps as plain local "
            "wall-clock time, e.g. 2026-09-10T14:00:00 for 2pm Eastern -- no \"Z\" or UTC offset. "
            "list works on any task. add/update/remove require this task's risk to be "
            "\"edit\" -- the CLI itself refuses them otherwise."
        ),
    },
]


def volume_mounts():
    """(host_dir, container_dir) pairs to bind-mount read-only into the container."""
    return [(str(m["host_dir"]), m["container_dir"]) for m in MODULES]


def describe_all():
    if not MODULES:
        return ""
    entries = "\n\n".join(m["describe"] for m in MODULES)
    return f"""
You also have access to the following modules, each a small CLI you can run directly:

{entries}
"""
