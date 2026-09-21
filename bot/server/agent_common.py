"""Config shared between the voice bot (bot.py) and the text chat (chat.py) so
the two stay *the same agent* -- same model, same Hermes-delegation behavior --
with only the modality (voice vs. text) differing.
"""

import os

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")

# Kept byte-identical to what bot.py's voice system instruction has always used
# for this paragraph -- only the delegation behavior needs to match between the
# two agents, not the framing around it (voice keeps its "spoken aloud" guard,
# chat doesn't need one).
HERMES_DELEGATION_INSTRUCTIONS = (
    "For anything about the user's schedule (checking, adding, changing, or removing "
    "an appointment/event), use run_hermes_task rather than answering from memory — "
    "you have no direct knowledge of it. Use risk=\"read_only\" to look something up, "
    "risk=\"edit\" to add or change something, and task_type=\"schedule\"."
)


async def dispatch_hermes_task(broker, objective, task_type, risk, on_complete=None):
    """Create and dispatch a Hermes task on the given broker.

    Plain asyncio -- no Pipecat types involved -- so both the voice bot's tool
    wrapper and the text chat's tool-calling loop share this exact call path.
    Returns the new task_id immediately; the task itself runs in the
    background (broker.dispatch is fire-and-forget).
    """
    task_id = await broker.create(objective, task_type, risk)
    broker.dispatch(task_id, on_complete=on_complete)
    return task_id
