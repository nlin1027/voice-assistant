import argparse
import asyncio
import time
from pathlib import Path

from .broker import TaskBroker

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_ROOT = REPO_ROOT / "hermes-tasks"
DB_PATH = REPO_ROOT / "broker" / "tasks.db"

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("objective", help="What you want Hermes to do")
    parser.add_argument("--type", default="research", choices=["research", "code", "file_op", "lookup", "system"])
    parser.add_argument("--risk", default="read_only", choices=["read_only", "reversible", "destructive"])
    args = parser.parse_args()

    broker = TaskBroker(root=TASKS_ROOT, db_path=DB_PATH)
    task_id = await broker.create(args.objective, args.type, args.risk)

    start = time.monotonic()
    try:
        row = await broker.run(task_id)
    except Exception as e:
        elapsed = time.monotonic() - start
        print(f"failed after {elapsed}: {e}")
        return
    elapsed = time.monotonic() - start

    print(f"\nDone in {elapsed:.1f}s")
    print(f"  status:  {row['status']}")
    print(f"  cost:    ${row['cost_usd']:.4f}" if row['cost_usd'] is not None else "  cost:    (unknown)")
    print(f"  summary: {row['summary']}")
    result_md = TASKS_ROOT / task_id / "result.md"
    print(f"  result:  {result_md}  ({'exists' if result_md.exists() else 'MISSING'})")
    print(f"  raw output: {row['raw_output']}")

if __name__ == "__main__":
    asyncio.run(main())