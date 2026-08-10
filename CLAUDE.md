do not edit the project or any files on your own. you may only edit the project if i directly ask you to. you may also ask for permission but it is ultimately up to my own (the prompter's) discretion.

When giving me curl commands to run in my PowerShell terminal, format them so I can paste and run directly:

Use curl.exe explicitly, never bare curl (it's aliased to Invoke-WebRequest, which has different flags).
Keep the whole command on one line — no \ line continuation (that's bash-only).
For JSON bodies with -d, wrap the JSON in single quotes AND escape every inner double-quote with \", e.g. -d '{\"key\":\"value\"}'. This is required due to how Windows passes arguments to native executables (embedded " gets stripped otherwise) — plain single-quoted JSON without escaping will break.

Venv lives at C:\Users\ignsock\venvs\voice-assistant — deliberately outside the repo. nltk 3.10.1's inisec.py blocks imports from any site-packages under the current working directory, so an in-project .venv breaks the pipecat CLI. Do not move it back in.

Project (where you run commands)    C:\Users\ignsock\Documents\GitHub\voice-assistant
Venv (packages live here)	        C:\Users\ignsock\venvs\voice-assistant
Activate	                        C:\Users\ignsock\venvs\voice-assistant\Scripts\Activate.ps1
Python directly	                    C:\Users\ignsock\venvs\voice-assistant\Scripts\python.exe

Running the voice agent: activate the external venv (C:\Users\ignsock\venvs\voice-assistant\Scripts\Activate.ps1), then from bot/server run python bot.py and open the printed local URL. Use python bot.py, not uv run bot.py — bare uv run creates a project-local .venv, which re-triggers the nltk inisec.py CWD import block. If you do use uv commands here, pass --active so they target the external venv.

hangover report 1:
Project context: Building a voice assistant that dispatches long-running tasks to a local Hermes Agent (Nous Research) while conversation continues. Architecture: Pipecat cascade bot (bot/server/bot.py, smallwebrtc + Deepgram/OpenAI/Cartesia) → broker/ package (store.py = SQLite task rows, hermes.py = subprocess driver, broker.py = orchestration, cli.py = test harness) → hermes -z one-shot subprocess sandboxed in Docker, working in hermes-tasks/<task_id>/ (bind-mounted to /workspace). Steps 1–2 are complete and verified: filesystem containment, per-risk network gating (read_only = network on, reversible/destructive = off), timeout handling, and container cleanup all tested and working. Known blocker: concurrent hermes -z runs cross-contaminate — Hermes' _recreate_container() recovery path calls _find_reusable_container without honoring TERMINAL_DOCKER_PERSIST_ACROSS_PROCESSES=false, and since every top-level run hardcodes task_id="default", a second task can attach to a first task's container and write into its directory; the planned fix is an asyncio.Semaphore(1) in TaskBroker to serialize execution. Next up is step 3: move TaskBroker to a module-scope singleton in bot.py, expose it as a Pipecat async tool (@tool_options(cancel_on_interruption=False) — Pipecat 1.7.0 natively handles dispatch-and-continue, progress streaming via is_final=False, and result injection as a developer message), with later steps adding check_task, a spoken-readback gate for destructive