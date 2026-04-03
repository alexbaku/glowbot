# Common Mistakes

All errors below are **silent** — Kelet swallows SDK errors to protect QoS. A misconfigured integration looks
identical to a working one. Review this table during Phase V, checking every entry that applies to the detected stack.

| Mistake | Symptom | Notes |
|---------|---------|-------|
| Secret key in `KeletProvider` / frontend env | Key leaked in JS bundle | Use publishable key in frontend. **Silent until key is revoked.** |
| Keys written to wrong config file (`.env` vs `.envrc`) | App starts but no traces appear | Check config pattern before writing. **Silent failure.** |
| `agentic_session` exits before streaming generator finishes | Traces appear incomplete | Wrap entire generator body including `[DONE]` sentinel. **Silent.** |
| VoteFeedback `session_id` doesn't match server session | Feedback unlinked from traces | Capture `X-Session-ID` header; use exact same value. **Silent.** |
| `configure(project=...)` on a multi-project app | All sessions attributed to one project | Use `configure()` with no project; override in `agentic_session()`. |
| No `kelet.agent(name=...)` with OpenAI/Anthropic/AI SDK | Kelet shows unattributed spans — RCA can't identify which agent failed | pydantic-ai exposes names natively (auto-inferred); raw SDKs don't. **Silent.** |
| Python extra not installed (e.g. missing `kelet[anthropic]`) | `configure()` succeeds, zero traces from that library | Install the matching extra — Kelet silently skips uninstrumented libraries. **Silent.** |
| Node.js: `npm install kelet` only, missing OTEL peer deps | Import errors or no traces | Add `@opentelemetry/api @opentelemetry/sdk-trace-node @opentelemetry/exporter-trace-otlp-http`. Python needs no peer deps. |
| Next.js: missing `instrumentationHook: true` in `next.config.js` | `instrumentation.ts` exists but never runs, zero traces | Add `experimental: { instrumentationHook: true }` to `next.config.js`. **Silent.** |
| Vercel AI SDK: missing `experimental_telemetry: { isEnabled: true }` per call | `configure()` succeeds, zero traces from AI SDK calls | Vercel AI SDK telemetry is off by default. Must opt in per call. **Silent.** |
| DIY orchestration without `agentic_session()` | Sessions appear fragmented — each LLM call is a separate unlinked trace in Kelet | Required whenever you own the loop: Temporal, manual agent chaining, custom orchestrators, raw SDK calls. **Silent.** |
| VoteFeedback: `<button>` returned from render prop without `asChild` | Invalid nested buttons — silently corrupts HMR, may crash dev server | Use `asChild` prop or pass content as direct children; never wrap in another `<button>`. |
| VoteFeedback.Popover: no CSS positioning context | Popover renders in document flow — invisible or in wrong position | Parent needs `position: relative`; Popover needs `position: absolute`. |
| Panel `overflow: hidden` containing VoteFeedback.Popover | Popover clipped / invisible even with correct position CSS | Set overflow only on the scroll container, not the panel wrapping VoteFeedback. |
| Astro: `"jsxImportSource": "react"` in tsconfig.json | Astro JSX compilation silently overridden — pages render as raw HTML | Remove from tsconfig; `@astrojs/react` handles JSX automatically. |
| `kelet[*]` as pip extra | Package doesn't need extras | Just `kelet` instruments pydantic-ai/langraph/etc. automatically. No extra needed. |
| Project name hardcoded in source (not env var) | Changing projects requires a code change | Always use `KELET_PROJECT` env var; read via `os.environ` or Pydantic Settings. |
| Guessing project name from repo/app name | `configure()` silently routes to wrong/nonexistent project | Always ask for exact project name; instruct developer to create from console top-nav first. |
| Not verifying existing pages after frontend changes | Unrelated pages break silently — only caught when user reports | After any frontend change, screenshot existing pages to confirm they still render correctly. |
| API keys set in `.env` but not in production environment | Local traces appear; production has zero Kelet data, no error | `.env` is local dev only. Set keys in the production secrets channel (Vercel env vars, `fly secrets set`, K8s Secret, etc.). **Silent.** |
| Secrets committed to `values.yaml`, Compose file, or IaC source | Credentials exposed in git history | Use K8s Secrets / platform dashboard / Secrets Manager. Never commit secret values to source control. |
| GH Actions: repo secret added but no `env:` entry in the deploy job | Secret exists in GitHub but is never injected into the container | Add `env: KELET_API_KEY: ${{ secrets.KELET_API_KEY }}` to the deploy job. **Silent.** |
