# Voice Assistant with Background Task Delegation

A voice AI agent that can hand off long-running, open-ended work to a sandboxed
coding agent mid-conversation — without freezing the call, and without losing
the result if the caller hangs up before it's done.

## The problem

Voice agents are turn-based: a tool call is expected to return within the
current turn, or the conversation stalls. That's fine for a weather lookup,
but breaks down for anything that takes real time — multi-step research, file
edits, running commands. The two obvious options are both bad: block the call
until the task finishes (dead air, a frozen conversation), or fire it off and
hope the caller is still on the line when it completes (silently lose the
result otherwise).

This project dispatches that work to a background task instead: the
conversation continues immediately, the task runs independently — sandboxed,
so an autonomous agent touching the filesystem or shell is safe — and the
result is delivered whenever the caller is next actually listening, even if
that's a different call entirely.

## Architecture

```
 Caller (WebRTC)
        │
        ▼
┌────────────────────────────────┐
│  Pipecat voice pipeline         │   bot/server/bot.py
│  transport.input()              │
│    → Deepgram STT               │
│    → user context aggregator    │
│    → OpenAI LLM (Responses API) │
│    → Cartesia TTS               │
│    → transport.output()         │
│    → assistant aggregator       │
└───────────────┬──────────────────┘
                │ run_hermes_task(objective, task_type, risk)
                │ — dispatched, non-blocking
                ▼
┌────────────────────────────────┐
│  TaskBroker                     │   broker/broker.py
│  - SQLite-backed task record    │   broker/store.py
│  - leases a sandbox slot        │   broker/slots.py
│  - runs in its own asyncio task,│
│    decoupled from the call      │
└───────────────┬──────────────────┘
                ▼
┌────────────────────────────────┐
│  Hermes agent, `-z` one-shot     │   broker/hermes.py
│  Docker-sandboxed subprocess     │
│  workdir: hermes-tasks/<id>/     │
│  risk-gated fs / network access  │
│  writes result.md                │
└────────────────────────────────┘
```

## Problems solved

**Dispatch without blocking the turn.** A tool call in a voice pipeline
normally has to return before the conversation can move on. `run_hermes_task`
uses Pipecat's `@tool_options(cancel_on_interruption=False)` together with
`FunctionCallResultProperties(is_final=False)` — the tool returns an
immediate "started" acknowledgment, the task keeps running in the background,
and a second result is injected later as a developer-role message the LLM
can speak on its own. The caller never waits on dead air.

**Results have to survive the call ending.** If the caller disconnects,
Pipecat cancels the pipeline worker — so the background task can't be a
child of that worker's lifetime. `TaskBroker.dispatch()` runs it as an
independent `asyncio.create_task`, and a small SQLite store
(`broker/store.py`) tracks each task through `queued → running →
success/failed` plus a `delivered` flag. On the next call's
`on_client_ready`, the bot sweeps `get_undelivered()` and works any
finished-while-you-were-gone results into its opening line.

**Concurrent tasks corrupting each other's sandbox.** The underlying sandboxed
agent (Hermes) keys its container-reuse logic off a hardcoded task id, so two
tasks running at once could attach to the same container and write into each
other's working directory. Rather than patch a third-party dependency,
`SlotPool` (`broker/slots.py`) pre-provisions a small fixed pool of
independent Hermes profiles (`slot0`–`slot2`); each task leases one for its
run, which gives concurrent tasks physically separate profile homes — and
therefore separate containers — for free. Verified with a concurrency
test (`broker/concurrency_test.py`) and a Docker-events replay showing two
genuinely overlapping, non-colliding container lifecycles.

**Letting an autonomous agent touch the filesystem safely.** Every task runs
in a disposable Docker container. Its own working directory
(`hermes-tasks/<task_id>/`) is the only path writable by default; a small
allowlist (`broker/approved_paths.py`) can additionally expose specific host
directories, mounted read-only or read-write depending on the task's
declared risk tier (`read_only` vs `edit`), with outbound network disabled
above `read_only`. Container teardown happens in a `finally` block
(`terminate_containers`) so a crash or timeout can't leak a running
container.

**Bounding a task that hangs.** Every run is wrapped in `asyncio.wait_for`
with a hard timeout; cleanup runs unconditionally, not just on the happy
path.

## What I learned

- Fast-moving frameworks punish assumptions — Pipecat renamed a core concept
  (`PipelineTask` → `PipelineWorker`) mid-project, and stale training data was
  the biggest source of wrong-but-plausible code. Verifying against live
  source became a habit, not a one-off.
- A background task's lifetime has to be reasoned about independently of
  whatever triggered it — tying it to the tool call, or even the pipeline
  worker, silently loses work on disconnect.
- Concurrency bugs in a black-box dependency don't always need a patch —
  constraining the *inputs* you control (here, the profile/container-reuse
  key) can isolate the problem without touching code you don't own.
- `finally` is where correctness actually lives in anything that spawns
  external processes or containers; the happy path is the easy 90%.
- SQLite is a perfectly good durable queue for a single-machine tool like
  this — no need to reach for a message broker.

## Project layout

```
voice-assistant/
├── bot/server/bot.py        # Pipecat voice pipeline + run_hermes_task tool
├── broker/
│   ├── broker.py             # TaskBroker: create / run / dispatch
│   ├── store.py                # SQLite task state + delivery tracking
│   ├── hermes.py                 # Sandboxed subprocess driver, risk profiles
│   ├── slots.py                    # Pool of pre-provisioned Hermes profiles
│   ├── approved_paths.py             # Allowlisted host directories
│   ├── provision_slots.py              # One-time slot setup
│   ├── cli.py                            # Standalone CLI for dispatching tasks
│   └── concurrency_test.py                 # Proof that concurrent tasks stay isolated
└── hermes-tasks/<task_id>/  # Per-task workdir: result.md, usage.json, ...
```

## Stack

Pipecat (voice pipeline framework) · Deepgram (STT) · OpenAI Responses API
(LLM) · Cartesia (TTS) · Hermes Agent (Nous Research, sandboxed coding agent)
· Docker · SQLite · Python / asyncio

## Running it

```bash
cd bot/server
uv sync
cp .env.example .env   # fill in API keys
uv run bot.py          # or: python bot.py, see project CLAUDE.md
```

## Status

End-to-end working: non-blocking dispatch, disconnect-safe delivery,
sandboxed + risk-gated filesystem/network access, and verified concurrency
isolation across simultaneous tasks.
