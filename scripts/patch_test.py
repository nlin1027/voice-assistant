"""Concurrent cross-contamination test for the Hermes recovery-path patch.

Runs two Hermes tasks at once under identical labels, force-removes the
intruder's container mid-run to trigger `_recreate_container()`, and checks
whether it attaches to the victim's container.

    python scripts\\patch_test.py

Both tasks MUST use the same risk level: `_find_reusable_container` filters on
the egress label, so a read_only task and a reversible task would not collide
regardless of the patch, giving a false pass.

Do not apply the TaskBroker semaphore before running this -- it would serialize
the two tasks and the race could never occur.
"""

import asyncio
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from broker.hermes import HERMES, prompt_template, risk_profiles  # noqa: E402

TASKS = REPO / "hermes-tasks"
RISK = "reversible"          # same for both tasks -- see module docstring
KILL_DELAY_S = 25            # how long into bravo's sleep to remove its container
PROC_TIMEOUT_S = 900

# Task A -- the victim. Stays alive long enough to be a reuse target for B.
# Its sleep sits under the 180s TERMINAL_TIMEOUT so the command itself survives.
ALPHA = (
    "alpha",
    "Run this shell command and wait for it to finish: sleep 150. "
    "Then write the single word alpha to /workspace/marker.txt.",
)

# Task B -- the intruder. Several sequential commands, so there is still work
# left after its container is removed. That next command is what trips recovery.
BRAVO = (
    "bravo",
    "Do these as three separate commands, one at a time: "
    "first run 'echo step-one', then run 'sleep 60', "
    "then write the single word bravo to /workspace/marker.txt.",
)


def hermes_containers():
    """Map resolved /workspace bind source -> container id."""
    ids = subprocess.run(
        ["docker", "ps", "-a", "--filter", "label=hermes-agent=1", "--format", "{{.ID}}"],
        capture_output=True, text=True,
    ).stdout.split()
    found = {}
    for cid in ids:
        raw = subprocess.run(["docker", "inspect", cid],
                             capture_output=True, text=True).stdout
        if not raw.strip():
            continue
        info = json.loads(raw)[0]
        ws = [m["Source"] for m in info["Mounts"] if m["Destination"] == "/workspace"]
        if ws:
            found[Path(ws[0]).resolve()] = cid
    return found


async def run_task(tag, objective, workdir):
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "TERMINAL_CWD": str(workdir),
        **risk_profiles[RISK],
    }
    proc = await asyncio.create_subprocess_exec(
        HERMES, "-z", prompt_template.format(objective=objective),
        cwd=str(workdir), env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=PROC_TIMEOUT_S)
    except asyncio.TimeoutError:
        proc.terminate()
        await proc.wait()
        print(f"[{tag}] TIMED OUT after {PROC_TIMEOUT_S}s")
        return

    log = workdir / f"{tag}.stderr.log"
    log.write_text(err.decode("utf-8", "replace"), encoding="utf-8")
    print(f"[{tag}] exit={proc.returncode}  stderr -> {log}")


async def kill_intruder(workdir):
    """Wait for bravo's container, let it get into the sleep, then remove it."""
    target = workdir.resolve()
    while True:
        cid = hermes_containers().get(target)
        if cid:
            print(f"[killer] bravo container {cid[:12]} up; waiting {KILL_DELAY_S}s")
            await asyncio.sleep(KILL_DELAY_S)
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True)
            print(f"[killer] removed {cid[:12]} -- recovery should fire next command")
            return
        await asyncio.sleep(2)


def verdict(dirs):
    print("\n=== marker.txt placement ===")
    for tag, d in dirs.items():
        m = d / "marker.txt"
        body = m.read_text(encoding="utf-8").strip() if m.exists() else "(absent)"
        print(f"  {tag:<6} {d.name}: {body!r}")

    alpha_marker = dirs["alpha"] / "marker.txt"
    contaminated = (
        alpha_marker.exists()
        and alpha_marker.read_text(encoding="utf-8").strip() == "bravo"
    )

    err_log = dirs["bravo"] / "bravo.stderr.log"
    err = err_log.read_text(encoding="utf-8", errors="replace") if err_log.exists() else ""
    fired = "attempting recovery" in err
    reused = "Recovery: reusing running container" in err

    print("\n=== recovery path ===")
    print(f"  recovery triggered:      {fired}")
    print(f"  reused foreign container:{reused}")
    print(f"  alpha dir holds 'bravo': {contaminated}")

    print("\n=== verdict ===")
    if not fired:
        print("  INCONCLUSIVE -- recovery never triggered, so the patch was never")
        print("  exercised. Raise KILL_DELAY_S or lengthen bravo's objective and retry.")
    elif reused or contaminated:
        print("  FAIL -- the gate did not hold; bravo attached to alpha's container.")
    else:
        print("  PASS -- recovery fired and bravo built its own container.")


async def main():
    stamp = uuid.uuid4().hex[:6]
    dirs = {}
    for tag, _ in (ALPHA, BRAVO):
        d = TASKS / f"patchtest_{stamp}_{tag}"
        d.mkdir(parents=True, exist_ok=True)
        dirs[tag] = d
    print(f"alpha -> {dirs['alpha']}\nbravo -> {dirs['bravo']}\n")

    await asyncio.gather(
        run_task(*ALPHA, dirs["alpha"]),
        run_task(*BRAVO, dirs["bravo"]),
        kill_intruder(dirs["bravo"]),
        return_exceptions=True,
    )
    verdict(dirs)


if __name__ == "__main__":
    asyncio.run(main())
