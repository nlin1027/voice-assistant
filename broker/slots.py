import asyncio
import contextlib
from pathlib import Path

HERMES_ROOT = Path(r"C:\Users\ignsock\AppData\Local\hermes")
DEFAULT_SLOTS = ("slot0", "slot1", "slot2")

class SlotPool:
    def __init__(self, names=DEFAULT_SLOTS):
        self.names = list(names)
        if not self.names:
            raise ValueError("needs at least one slot")
        self.free = asyncio.Queue()
        for n in self.names: 
            self.free.put_nowait(n)

    @staticmethod
    def home(name):
        return HERMES_ROOT / "profiles" / name

    def assert_provisioned(self):
        missing = [n for n in self.names if not self.home(n).is_dir()]
        if missing:
            raise RuntimeError(f"unprovisioned slots --> run provision_slots.py")

    @contextlib.asynccontextmanager
    async def lease(self):
        name = await self.free.get()
        try:
            yield name
        finally:
            self.free.put_nowait(name)