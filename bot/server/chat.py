"""Text-chat agent. Same brain as the voice bot (bot.py) -- same OpenAI model,
same Hermes-delegation tool and instructions -- just without audio. Talks to
the OpenAI Responses API directly (the same API surface Pipecat's
OpenAIResponsesHttpLLMService uses for voice, confirmed against the installed
SDK) rather than going through a Pipecat pipeline, since none of what Pipecat
exists for -- STT/TTS/VAD/turn-taking/interruptions -- applies to a plain text
box.

Delivery of async Hermes results is pull-based, not push-based: every call
here sweeps broker.store.get_undelivered() first (the same delivered-flag
sweep bot.py's on_client_ready does for voice), so a task that finished while
the chat tab was closed or idle shows up as soon as the client polls again.
"""

import json
import os

from loguru import logger
from openai import AsyncOpenAI

from agent_common import HERMES_DELEGATION_INSTRUCTIONS, OPENAI_MODEL, dispatch_hermes_task

SYSTEM_INSTRUCTIONS = (
    "You are a helpful assistant, chatting over text instead of voice. Respond helpfully "
    "and concisely.\n\n" + HERMES_DELEGATION_INSTRUCTIONS
)

RUN_HERMES_TASK_TOOL = {
    "type": "function",
    "name": "run_hermes_task",
    "description": "Dispatch a background Hermes task to accomplish an objective.",
    "parameters": {
        "type": "object",
        "properties": {
            "objective": {"type": "string", "description": "What to accomplish."},
            "task_type": {"type": "string", "description": "A short label for the kind of task."},
            "risk": {
                "type": "string",
                "enum": ["read_only", "edit"],
                "description": (
                    "read_only to look something up, edit to add or change something. "
                    "No other value is valid."
                ),
            },
        },
        "required": ["objective", "task_type", "risk"],
    },
}

_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def sweep_finished_tasks(broker, chat_store):
    """Turn any undelivered finished Hermes task (dispatched from chat OR
    voice) into a chat message. Mirrors bot.py's on_client_ready sweep."""
    for row in broker.store.get_undelivered():
        if row["status"] == "success":
            content = f"Task finished: {row['objective']} — {row['summary']}"
        else:
            content = f"Task failed: {row['objective']} — {row['error']}"
        chat_store.append("assistant", content)
        broker.store.mark_delivered(row["id"])


def _history_to_input(history):
    return [{"role": m["role"], "content": m["content"]} for m in history]


async def _create_response(input_items):
    return await _client.responses.create(
        model=OPENAI_MODEL,
        instructions=SYSTEM_INSTRUCTIONS,
        input=input_items,
        tools=[RUN_HERMES_TASK_TOOL],
        store=False,
    )


async def handle_chat_message(broker, chat_store, user_text: str) -> list[dict]:
    """Handle one turn of the text chat: sweep finished tasks, record the
    user's message, run the model (dispatching any run_hermes_task calls
    directly through the broker), record the reply, and return the full,
    now-current transcript."""
    sweep_finished_tasks(broker, chat_store)
    chat_store.append("user", user_text)

    try:
        input_items = _history_to_input(chat_store.get_all())
        response = await _create_response(input_items)

        function_calls = [item for item in response.output if item.type == "function_call"]
        if function_calls:
            for call in function_calls:
                input_items.append(
                    {
                        "type": "function_call",
                        "call_id": call.call_id,
                        "name": call.name,
                        "arguments": call.arguments,
                    }
                )
            for call in function_calls:
                args = json.loads(call.arguments) if call.arguments else {}
                task_id = await dispatch_hermes_task(
                    broker,
                    objective=args.get("objective", ""),
                    task_type=args.get("task_type", ""),
                    risk=args.get("risk", ""),
                )
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps({"status": "started", "task_id": task_id}),
                    }
                )

            response = await _create_response(input_items)

        reply = response.output_text or "(no response)"
    except Exception as e:
        logger.error(f"Chat turn failed: {e}")
        reply = f"Sorry, something went wrong talking to the model: {e}"

    chat_store.append("assistant", reply)
    return chat_store.get_all()


async def clear_chat(chat_store):
    chat_store.clear()
