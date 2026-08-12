import asyncio
from pathlib import Path
from .broker import TaskBroker

REPO = Path(__file__).resolve().parent.parent
broker = TaskBroker(root=REPO / "hermes-tasks", db_path=REPO / "broker" / "tasks.db")
ALPHA = "Write the word alpha to /workspace/alpha.txt then report done"
BRAVO = "Write the word bravo to /workspace/bravo.txt then report done"

async def main():
    a = await broker.create(ALPHA, "file_op", "reversible")
    b = await broker.create(BRAVO, "file_op", "reversible")
    print(f"alpha -> {a}\nbravo -> {b}\n")

    results = await asyncio.gather(broker.run(a), broker.run(b), return_exceptions=True)
    for tag, r in zip(("alpha", "bravo"), results):
        print(f"{tag}: {r if isinstance(r, Exception) else r['status']}")

if __name__ == "__main__":
    asyncio.run(main())