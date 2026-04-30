# Implementation Reference

## Session ID Evaluation

Before choosing a session ID, answer from the code:

```
Does the app have a new-conversation / reset / start-over concept?
├─► Yes: does the candidate ID change at that boundary?
│   ├─► Yes ──► ✅ Correct mapping — proceed
│   └─► No  ──► ⚠️ Mismatch — surface it, propose a fix (e.g. generate UUID per conversation)
└─► No reset concept found / ambiguous ──► Ask developer to confirm intended session boundary

Is the candidate ID a stable user identifier (phone, email, user_id, device_id)?
└─► Yes ──► ⚠️ It outlives sessions — generate kelet_session_id UUID per conversation
            └─► Is it PII (phone, email)? → omit user_id=, inform developer prominently
            └─► Non-PII (internal user ID, opaque UUID)? → wire as user_id=
```

---

## Decision Tree

```
N agentic flows?
├─► 1  ──► configure(project="name") at startup
└─► N  ──► configure() once, agentic_session(project=...) per flow

Stack?
├─► Python   ──► kelet.configure() + agentic_session() context manager
├─► Node.js  ──► configure() + agenticSession({sessionId}, callback)
└─► Next.js  ──► instrumentation.ts + KeletExporter

User-facing with React?
├─► Yes ──► KeletProvider at root
│           ├─► Multiple flows? → nested KeletProvider per flow (project only)
│           └─► VoteFeedback at AI response sites + session propagation
└─► No  ──► Server-side only

Feedback signals?
├─► Explicit (votes)            ──► VoteFeedback / kelet.signal(kind=FEEDBACK, source=HUMAN)
├─► Implicit (edits)            ──► useFeedbackState (tag AI vs human updates with trigger names)
├─► Coded signals from React    ──► useKeletSignal() inside KeletProvider
└─► Synthetic signal evaluators ──► Generate deeplink → console.kelet.ai/<project>/synthetics/setup
```

## Implementation Steps

1. **API keys** — collected in Batch 2; do NOT ask again. Detect config pattern,
   write to correct file. Always write `KELET_PROJECT` — missing = silent routing to wrong project, no error raised.
2. **Install** — detect package manager from lockfiles (`uv.lock`→uv, `poetry.lock`→poetry, `Pipfile`→pipenv, else pip;
   `bun.lockb`→bun, `pnpm-lock.yaml`→pnpm, `yarn.lock`→yarn, else npm).
   Python: `kelet`; extras only if needed (`kelet[google-adk]`, `kelet[openai]`, `kelet[anthropic]`, `kelet[langchain]`, `kelet[all]`).
   Node.js/Next.js: `kelet` + OTEL peers (`@opentelemetry/api @opentelemetry/sdk-trace-node @opentelemetry/exporter-trace-otlp-http`).
   React: `@kelet-ai/feedback-ui`.
3. **Instrument server** — `configure()` at startup + `agentic_session()` per flow
4. **Instrument frontend** — `KeletProvider` at root, nested per flow if multi-project
5. **Connect feedback** — VoteFeedback + session ID propagation if user-facing
6. **Verify** — type check, confirm env vars set, open Kelet console and confirm traces appear

## Wrap decision

User-facing conversational turn → wrap in `agentic_session()`. Tooling / health / one-shot (admin, `/healthz`, curl RAG lookups) → don't; server auto-groups unwrapped calls.

Signal + agent run in the same handler → one wrap around both. Nested wraps dedupe but render as two units.

## Shutdown (long-running servers)

Call `shutdown()` explicitly in teardown or spans from the final seconds drop.

- **Python**: auto `atexit`; call in FastAPI lifespan `finally` / Django SIGTERM / Celery `worker_shutdown`.
- **TS**: auto `beforeExit` only — SIGINT/SIGTERM are not auto-handled (would override host's graceful shutdown). Install your own handler that awaits `shutdown()` before `process.exit(N)`.

```python
@asynccontextmanager
async def lifespan(app):
    kelet.configure(api_key=..., project=...)
    try:
        yield
    finally:
        kelet.shutdown()
```
