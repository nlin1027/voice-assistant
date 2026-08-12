import uuid
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

    async def create(self, objective, task_type, risk):
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        workdir = self.root / task_id
        workdir.mkdir(parents=True, exist_ok=True)
        self.store.insert(task_id, objective, task_type, risk, str(workdir))
        return task_id

    async def run(self, task_id):
        row = self.store.get(task_id)
        workdir = Path(row["workdir"])
        async with self.slots.lease() as slot:
            try:
                result = await run_hermes(row["objective"], workdir, row["risk"], timeout_s=1800, profile=slot)
                self.store.update_result(task_id, status="success", summary=result.stdout, raw_output=result.full_result, cost_usd=result.cost_usd)
            except Exception as e:
                self.store.update_result(task_id, status="failed", error=str(e))
                raise
        return self.store.get(task_id)