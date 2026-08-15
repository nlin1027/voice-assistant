import uuid
import asyncio
from pathlib import Path
from .store import TaskStore
from .hermes import run_hermes
from .slots import SlotPool

class TaskBroker:
    def __init__(self, root, db_path, slots=None):
        self.root = root
        self.store = TaskStore(db_path)
        self.slots = SlotPool(slots) if slots else SlotPool()
        self.slots.assert_provisioned()
        self.inflight = {}

    async def create(self, objective, task_type, risk):
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        workdir = self.root / task_id
        workdir.mkdir(parents=True, exist_ok=True)
        self.store.insert(task_id, objective, task_type, risk, str(workdir))
        return task_id

    async def run(self, task_id):
        row = self.store.get(task_id)
        workdir = Path(row["workdir"])
        self.store.mark_running(task_id)
        async with self.slots.lease() as slot:
            try:
                result = await run_hermes(row["objective"], workdir, row["risk"], timeout_s=1800, profile=slot)
                self.store.update_result(task_id, status="success", summary=result.stdout, raw_output=result.full_result, cost_usd=result.cost_usd)
            except Exception as e:
                self.store.update_result(task_id, status="failed", error=str(e))
                raise
        return self.store.get(task_id)

    async def run_and_report(self, task_id, on_complete):
        try:
            row = await self.run(task_id)
        except Exception as e:
            if on_complete:
                try:
                    await on_complete(None, e)
                except Exception:
                    pass
            return
        if on_complete:
            try:
                await on_complete(row, None)
            except Exception:
                pass

    def dispatch(self, task_id, on_complete=None):
        """Run task in the background and should be independent of caller's lifetime"""
        task = asyncio.create_task(self.run_and_report(task_id, on_complete))
        self.inflight[task_id] = task
        task.add_done_callback(lambda t: self.inflight.pop(task_id, None))