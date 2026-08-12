import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from .slots import SlotPool

HERMES = r"C:\Users\ignsock\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe"
prompt_template = """{objective}

---
Your working directory is /workspace. Only files written there persist.
When finished:
1. Write complete details to /workspace/result.md — ALWAYS, even if the task
   could not be completed. If you did not do the work, write why. Do this
   before replying.
2. Reply with ONLY a two-sentence summary suitable for reading aloud —
   no markdown, no file paths, no code, numbers spelled out plainly.
"""

risk_profiles = {
    "read_only": {
        "TERMINAL_ENV": "docker",
        "TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE": "true",
        "TERMINAL_DOCKER_NETWORK": "true",
        "TERMINAL_CONTAINER_PERSISTENT": "false",
        "TERMINAL_DOCKER_PERSIST_ACROSS_PROCESSES": "false",
    },
    "reversible": {
        "TERMINAL_ENV": "docker",
        "TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE": "true",
        "TERMINAL_DOCKER_NETWORK": "false",
        "TERMINAL_CONTAINER_PERSISTENT": "false",
        "TERMINAL_DOCKER_PERSIST_ACROSS_PROCESSES": "false",
    },
    "destructive": {
        "TERMINAL_ENV": "docker",
        "TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE": "true",
        "TERMINAL_DOCKER_NETWORK": "false",
        "TERMINAL_CONTAINER_PERSISTENT": "false",
        "TERMINAL_DOCKER_PERSIST_ACROSS_PROCESSES": "false",
    },
}

@dataclass
class HermesResult:
    stdout: str
    stderr: str
    full_result: str | None
    cost_usd: float | None
    returncode: int

async def run_hermes(objective, workdir, risk, timeout_s=1800, profile=None):
    workdir = Path(workdir)
    prompt = prompt_template.format(objective=objective)
    usage_path = workdir / "usage.json"

    child_env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "TERMINAL_CWD": str(workdir),
        **risk_profiles[risk]
    }
    if profile:
        child_env["HERMES_HOME"] = str(SlotPool.home(profile))
        
    proc = await asyncio.create_subprocess_exec(
        HERMES, "-z", prompt,
        "--usage-file", str(usage_path),
        cwd=str(workdir),
        env=child_env, 
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )  

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.terminate()
        await proc.wait()
        raise TimeoutError(f"hermes didn't finish within {timeout_s}s")
    finally:
        try:
            await terminate_containers(workdir)
        except:
            pass

    stdout = stdout.decode("utf-8", errors="replace").strip()
    stderr = stderr.decode("utf-8", errors="replace").strip()
    (workdir / "hermes.stderr.log").write_text(stderr, encoding="utf-8")

    if proc.returncode != 0:
        raise RuntimeError(f"hermes exited {proc.returncode}: {stderr[-2000:]}")

    return HermesResult(
        stdout=stdout,
        stderr=stderr,
        full_result=read_hermes_result(workdir),
        cost_usd=read_cost(usage_path),
        returncode=proc.returncode,
    )

async def terminate_containers(workdir):
    proc = await asyncio.create_subprocess_exec(
        "docker", "ps", "-q", "--filter", "label=hermes-agent=1",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()

    for cid in out.decode().split():
        inspect = await asyncio.create_subprocess_exec(
            "docker", "inspect", "-f",
            '{{range .Mounts}}{{if eq .Destination "/workspace"}}{{.Source}}{{end}}{{end}}',
            cid,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        src, _ = await inspect.communicate()

        if src.decode().strip().lower() == str(workdir).lower():
            rm = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", cid,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await rm.wait()

def read_cost(usage_path):
    try:
        data = json.loads(usage_path.read_text(encoding="utf-8"))
        return data.get("estimated_cost_usd")
    except Exception:
        return None

def read_hermes_result(workdir):
    try:
        return (workdir / "result.md").read_text(encoding="utf-8")
    except Exception:
        return None