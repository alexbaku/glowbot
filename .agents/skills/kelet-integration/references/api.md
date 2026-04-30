# Kelet SDK API Reference

## Package Names

| Stack                | Package                                                                                                               |
| -------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Python               | `kelet` — optional extras: `kelet[google-adk]`, `kelet[openai]`, `kelet[anthropic]`, `kelet[langchain]`, `kelet[all]` |
| TypeScript / Node.js | `kelet @opentelemetry/api @opentelemetry/sdk-trace-node @opentelemetry/exporter-trace-otlp-http`                      |
| React frontend       | `@kelet-ai/feedback-ui`                                                                                               |

## Python SDK

Functions (all in `kelet` namespace):

- `kelet.configure(*, api_key=None, project=None, base_url=None, strict=False)` — call once at startup. All params default
  to env vars (`KELET_API_KEY`, `KELET_PROJECT`, `KELET_API_URL`); `kelet.configure()` with no args works when
  env vars are set. If credentials are missing, `configure()` logs one warning and installs a no-op — `signal()`
  and `agentic_session()` become silent no-ops. Pass `strict=True` to fail-fast instead (raises `ValueError`).
  Explicit empty `api_key=""` still raises regardless of `strict`.
- `kelet.agentic_session(*, session_id, user_id=None, project=None)` — async/sync context manager AND decorator
- `kelet.agent(*, name)` — context manager; names an agent within a session for readable multi-agent traces
- `async kelet.signal(kind, source, *, session_id=None, trace_id=None, trigger_name=None, score=None, value=None, confidence=None, metadata=None, timestamp=None)` —
  submit a signal; auto-resolves session from context. Best-effort: transport errors logged, not raised. Raises `ValueError` only on missing session/trace context or `score`/`confidence` outside [0,1]. No try/except needed.

- `kelet.get_session_id()` — get current session ID from context
- `kelet.create_kelet_processor()` — for manual OTEL setup (e.g.
  `logfire.configure(additional_span_processors=[kelet.create_kelet_processor()])`)
- `kelet.shutdown()` — flush + close exporters. Auto-`atexit`; call explicitly in FastAPI lifespan / Django SIGTERM / Celery `worker_shutdown`.

## TypeScript SDK

**Critical difference from Python**: `agenticSession` is **callback-based**, not a context manager. AsyncLocalStorage
propagates context through the callback's call tree — there's no `with`-equivalent in Node.js, so the callback IS the
scope boundary. Writing `await agenticSession(...)` without a callback silently breaks context propagation.

```
agenticSession({ sessionId, userId? }, async () => { ... })  // returns callback's return value
```

Node.js only (not browser-compatible). Inside the callback, `signal()` auto-resolves `sessionId` from context.

Other functions:

- `configure({ apiKey, project, apiUrl, strict? })` — call once at startup. Missing credentials →
  one `console.warn` + no-op (`signal()` / `agenticSession` become silent passthroughs). Pass
  `strict: true` to throw instead. Explicit empty `apiKey: ""` still throws regardless of `strict`.
- `signal({ kind, source, sessionId?, traceId?, triggerName?, score?, value?, confidence?, metadata?, timestamp? })` —
  returns Promise<void>
- `getSessionId()`, `getUserId()`, `getTraceId()` — read from current context

## Next.js

Use `KeletExporter` in `instrumentation.ts` via `@vercel/otel`:

- `new KeletExporter({ apiKey, project })`

## React (`@kelet-ai/feedback-ui`)

- `KeletProvider({ apiKey?, project, baseUrl? })` — `apiKey` optional if a parent provider already set it
- `VoteFeedback.Root({ session_id, onFeedback? })` — compound component root
- `VoteFeedback.UpvoteButton` / `VoteFeedback.DownvoteButton` — render their OWN `<button>` element; children render
  inside it. Use `asChild` prop (Radix-style) to merge handlers onto your own element via cloneElement. NEVER return a
  `<button>` from a render prop without `asChild` — creates invalid nested buttons that silently corrupt HMR.
  ✓ `<VoteFeedback.UpvoteButton><svg/></VoteFeedback.UpvoteButton>` (direct children)
  ✓
  `<VoteFeedback.UpvoteButton asChild>{({ isSelected }) => <button className={...}>👍</button>}</VoteFeedback.UpvoteButton>` (
  asChild)
  ✗ `<VoteFeedback.UpvoteButton>{({ isSelected }) => <button>👍</button>}</VoteFeedback.UpvoteButton>` (nested buttons)
- `VoteFeedback.Popover` — fully headless; renders as a plain `role="dialog"` div with NO positioning. To float above
  buttons: (1) wrap `VoteFeedback.Root` in a `position: relative` container, (2) give Popover
  `position: absolute; bottom: calc(100% + 8px)`, (3) ensure no ancestor has `overflow: hidden` — it clips the
  popover. Click-outside-to-close is NOT implemented; do NOT build a workaround (library will add it natively).
- `VoteFeedback.Textarea`, `VoteFeedback.SubmitButton`
- `useFeedbackState<T>(initialState, session_id, options?)` — drop-in for `useState`; tracks edits automatically. Second
  arg to each `setState` call sets trigger name: `setState(value, "ai_generation")` vs `setState(value, "manual_edit")`
- `useKeletSignal()` — returns a `sendSignal(params)` function for sending signals directly from React event handlers.
  Use for coded signals (abandon, copy, accept) tied to an explicit trigger — never for rephrase (always LLM synthetic;
  see SKILL.md). Must be called inside a `KeletProvider`.
  params: `{ session_id, kind, source, trigger_name?, score?, value?, metadata? }`
  Example:
  `const sendSignal = useKeletSignal(); sendSignal({ session_id, kind: 'FEEDBACK', source: 'HUMAN', trigger_name: 'user-abandon', score: 0.0 });`

## Env Vars

Keys are self-describing by prefix: `sk-kelet-...` = secret · `pk-kelet-...` = publishable.

| Variable                            | Where             | What                                                            |
| ----------------------------------- | ----------------- | --------------------------------------------------------------- |
| `KELET_API_KEY`                     | Server            | Secret key — required; configure() warns and no-ops if missing (pass `strict=True` to raise) |
| `KELET_PROJECT`                     | Server            | Project name — required; missing = silent routing to wrong project |
| `KELET_API_URL`                     | Server (optional) | Custom endpoint (self-hosted)                                   |
| `VITE_KELET_PUBLISHABLE_KEY`        | Vite frontend     | Publishable key for KeletProvider                               |
| `NEXT_PUBLIC_KELET_PUBLISHABLE_KEY` | Next.js           | Same, Next.js convention                                        |
| `VITE_KELET_PROJECT`                | Vite frontend     | Project name for KeletProvider                                  |
| `NEXT_PUBLIC_KELET_PROJECT`         | Next.js           | Same, Next.js convention                                        |
| `PUBLIC_KELET_PROJECT`              | SvelteKit         | Same, SvelteKit convention                                      |
