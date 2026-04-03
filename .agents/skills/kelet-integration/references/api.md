# Kelet SDK API Reference

## Package Names

| Stack                | Package                                                                                                                             |
|----------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| Python               | `kelet` (pip/uv)                                                                                                                    |
| TypeScript / Node.js | `kelet @opentelemetry/api @opentelemetry/sdk-trace-node @opentelemetry/exporter-trace-otlp-http` (npm)                              |
| React frontend       | `@kelet-ai/feedback-ui` (npm)                                                                                                       |
| Python extras        | `kelet[anthropic]`, `kelet[openai]`, `kelet[langchain]`, `kelet[all]` — if not installed, `configure()` silently skips that library |

## Python SDK

Functions (all in `kelet` namespace):

- `kelet.configure(*, api_key=None, project=None, base_url=None)` — call once at startup
- `kelet.agentic_session(*, session_id, user_id=None, project=None)` — async/sync context manager AND decorator
- `kelet.agent(*, name)` — context manager; names an agent within a session for readable multi-agent traces
-

`async kelet.signal(kind, source, *, session_id=None, trace_id=None, trigger_name=None, score=None, value=None, confidence=None, metadata=None, timestamp=None)` —
submit a signal; auto-resolves session from context

- `kelet.get_session_id()` — get current session ID from context
- `kelet.create_kelet_processor()` — for manual OTEL setup (e.g.
  `logfire.configure(additional_span_processors=[kelet.create_kelet_processor()])`)

## TypeScript SDK

**Critical difference from Python**: `agenticSession` is **callback-based**, not a context manager. AsyncLocalStorage
propagates context through the callback's call tree — there's no `with`-equivalent in Node.js, so the callback IS the
scope boundary. Writing `await agenticSession(...)` without a callback silently breaks context propagation.

```
agenticSession({ sessionId, userId? }, async () => { ... })  // returns callback's return value
```

Node.js only (not browser-compatible). Inside the callback, `signal()` auto-resolves `sessionId` from context.

Other functions:

- `configure({ apiKey, project, apiUrl })` — call once at startup
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
  Use for coded signals (abandon, copy, accept, rephrase) that aren't tied to component state. Must be called inside
  a `KeletProvider`.
  params: `{ session_id, kind, source, trigger_name?, score?, value?, metadata? }`
  Example:
  `const sendSignal = useKeletSignal(); sendSignal({ session_id, kind: 'FEEDBACK', source: 'HUMAN', trigger_name: 'user-abandon', score: 0.0 });`

## Env Vars

| Variable                            | Where             | What                                                            |
|-------------------------------------|-------------------|-----------------------------------------------------------------|
| `KELET_API_KEY`                     | Server            | Secret key — required; configure() raises ValueError if missing |
| `KELET_PROJECT`                     | Server (optional) | Default project name                                            |
| `KELET_API_URL`                     | Server (optional) | Custom endpoint (self-hosted)                                   |
| `VITE_KELET_PUBLISHABLE_KEY`        | Vite frontend     | Publishable key for KeletProvider                               |
| `NEXT_PUBLIC_KELET_PUBLISHABLE_KEY` | Next.js           | Same, Next.js convention                                        |
