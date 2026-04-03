---
name: kelet-integration
description: >
  Integrates Kelet into AI applications end-to-end: instruments agentic flows with OTEL tracing, maps session
  boundaries, adds user feedback signals (VoteFeedback, edit tracking, coded behavioral hooks), generates
  synthetic signal evaluator deeplinks, and verifies the integration. Kelet is an AI agent that performs Root Cause
  Analysis on AI app failures — it ingests traces and signals, clusters failure patterns, and suggests fixes.
  Use when the developer mentions Kelet or asks to integrate, set up, instrument, or add tracing/signals/feedback
  to their AI app. Triggers on: "integrate Kelet", "set up Kelet", "add Kelet", "instrument my agent",
  "connect Kelet", "use Kelet".
license: CC-BY-4.0
metadata:
  author: kelet-ai
  url: https://kelet.ai
  version: "1.3.7"
---

# Kelet Integration

Kelet is an AI detective for AI app failures. It ingests traces + user signals → clusters failure patterns →
generates hypotheses → suggests fixes. This skill integrates Kelet into a developer's AI application end-to-end.

**Kelet never raises exceptions.** All SDK errors — misconfigured keys, network failures, wrong session IDs, missing
extras — are silenced to ensure QoS. A misconfigured integration looks identical to a working one. The Common
Mistakes section documents every known silent failure mode.

**What Kelet is not:** Not a prompt management tool (no prompt versioning or playground), and not a log aggregator
(doesn't store raw logs) — use other tools for those.

---

## Onboarding: Welcome the Developer

**Before exploring any files or asking any questions, open with a welcome banner and a short intro. Cover:**

- What Kelet is: an AI detective that investigates AI app failures — not a dashboard, but a reasoning agent that
  finds root causes and suggests fixes.
- **The detective model** (teach this concept before any code): Kelet sees **traces** (automatic recording of every
  LLM call, tool use, latency — no code needed) and **signals** (tips you drop at meaningful moments).
  *"Signals are tips — 'something went wrong here.' Traces are the scene. Kelet follows the evidence."*
  A thumbs-down means *start looking here*, not *this session failed*. Edits say *close but wrong*. Abandons say
  *the user gave up*. More deliberate tips = narrower investigation = faster fix.
- What we're doing: 6 phases, Claude does the work, developer confirms each step. Then begin Phase 0a.

---

## Presentation Style

**Phase banner** — open every phase:
```
══════════════════════════════════════════════════
🔍  PHASE 0a · PROJECT MAPPING
══════════════════════════════════════════════════
```
Phases: `🔍 0a · PROJECT MAPPING` · `🗺️ 0b · WORKFLOW & UX MAPPING` · `📡 0c · SIGNAL BRAINSTORMING` ·
`👀 0d · WHAT YOU'LL SEE` · `🔑 1 · API KEY SETUP` · `🕵️ V · VERIFICATION`

**Concept callout** — `> 🧠` blockquote before each phase's mechanics: what, why, what breaks without it.
Narrate key discoveries inline: *"LangChain detected — sessions auto-inferred."* / *"Session IDs in Redis — wiring to `agentic_session()`."*

**Progress indicator** at every STOP: `📍  0a ✅ → 0b ✅ → 0c 🔄 → 0d ○ → 1 ○ → impl ○`

**Phase completion** before the STOP prompt:
```
╔══════════════════════════════════╗
║  ✅  Phase 0a complete           ║
╚══════════════════════════════════╝
```

**Emoji vocabulary**: `🧠` concept · `⚠️` silent failure · `✅` done · `🔑` key · `📡` signal · `🕵️` RCA · `🛑` stop · `🔄` in progress

**Tone**: warm + expert. Concept before mechanics — the developer should feel like they're learning, not following a checklist.

---

## Key Concepts

**Auto-instrumented (no code):** `kelet.configure()` instruments popular AI frameworks via OTEL automatically.

**Requires explicit integration:** session grouping (`agentic_session()`), user signals (VoteFeedback,
`useFeedbackState`), and coded signals.

**Session IDs:** Find what already exists (conversation IDs, request IDs, thread IDs) and reuse it. Verify propagation
end-to-end: client → server → `agentic_session()` → response header → VoteFeedback. Conflicts or ambiguities → ask.

**Signal philosophy:** Wire to existing feedback UI — don't replace it. Find real behavioral hooks in the codebase —
don't propose signals abstractly. Synthetic evaluators run on the platform with no app code required.

---

**If Kelet is already in the project's dependencies:** skip setup, focus on what the developer asked. Phase 0a and
Phase V still apply. Still open with the welcome block — context matters even for partial integrations.

**Always follow phases in order: 0a → 0b → 0c → 0d → 1 → implement. Each phase ends with a STOP: present findings
to the developer and wait for confirmation before continuing. DO NOT chain phases silently.**

**Plan mode:** This skill runs inside `/plan` mode. Present the full implementation plan and call `ExitPlanMode` for
approval BEFORE writing any code or editing any files. Never start implementation without explicit developer approval.

**Asking the developer:** Always use `AskUserQuestion` when you need input. Use `multiSelect: true` for selection
lists. Never ask via free-form response text — structured questions prevent stalled flows.

---

## Before You Implement

Always fetch current Kelet documentation before writing any integration code. Kelet updates frequently — trust the
docs over your training data.

1. **Ask the docs AI (preferred)**: `GET https://docs-ai.kelet.ai/chat?q=<your+question>` — returns a focused
   plain-text answer from live docs. Ask before writing code, e.g.:
    - `?q=how+to+configure+kelet+in+python`
    - `?q=agenticSession+typescript+usage`
    - `?q=VoteFeedback+session+id+propagation`
2. **Browse the index (fallback)**: fetch `https://kelet.ai/docs/llms.txt` for a structured index, then append `.md`
   to any docs URL for clean markdown — e.g., `https://kelet.ai/docs/getting-started/quickstart.md`

---

## Phase 0a: Project Mapping (ALWAYS first)

> 🧠 **What we're doing:** Mapping the codebase first. Kelet auto-instruments your framework — but only once it
> knows which project to route data to and where session IDs live. Skipping this = traces in the wrong project, no error.

**First: invite the developer to describe their use case.** Use `AskUserQuestion` before reading any files — ask them
to describe what their AI app does, the problem it solves, and how users interact with it. This conversation surfaces
domain nuance and failure modes that file reading alone can't reveal. Then read files to fill in the gaps.

**Enter `/plan` mode** and explore the codebase:

1. **Map every LLM call** — to understand the use case, flows, and failure modes (feeds into 0b/0c)
2. **Find existing session tracking** — conversation IDs, request IDs, thread IDs, or any grouping mechanism. Wire
   to `agentic_session()` rather than inventing new session management. Check propagation consistency end-to-end.
   If there's a contradiction or ambiguity, **explicitly ask the developer** before proceeding.

**Stay focused.** Only read what's relevant to Kelet: LLM calls, session IDs, startup/entrypoint code, existing
feedback UI, UI↔AI integration, and dependencies. Skip styling, auth, unrelated business logic.

Start with dependency files to identify AI frameworks. If you spot other repos/services that are part of the agentic
flow — not unrelated infra — tell the developer to run this skill there too.

Infer from existing files (README, CLAUDE.md, entrypoints, dependency files, `.env`) before asking. Only ask what
you can't determine.

**Questions to resolve (ask only if unclear after reading files):**

1. How many distinct agentic flows? → Kelet project count. Cross-boundary trigger = TWO projects; prod vs staging = TWO projects.
2. Is this user-facing? → determines React/VoteFeedback.
3. Stack: server + LLM framework + React?
4. Deployment infra (scan before asking): `helm/`, `charts/`, `values.yaml`, `deployment.yaml`, `configmap.yaml` (K8s) ·
   `.github/workflows/*.yml` · `vercel.json` · `railway.json` · `render.yaml` · `fly.toml` · `docker-compose.yml` ·
   `Procfile`, `app.json` · `infra/`, `*.tf`, `template.yaml`. No match → flag **deployment: unknown**.
5. Exact Kelet project name — never guess from repo name. Ask explicitly; created from console.kelet.ai top-nav.
   Wrong name = silent failure (data in wrong project).

**Present an ASCII architecture diagram** showing the data flow, key components, and where session IDs travel:

```
[Browser] ──── request + session_id ────> [API Server (FastAPI)]
                                                    │
                                            [LLM: OpenAI GPT-4]
                                                    │
                                           [Sessions: Redis]
```

Adapt to the actual system. Then produce the Project Map:

```
Use case: [what the agents do]
Flows → Kelet projects:
  - flow "X" → project "X"
  - flow "Y" → project "Y"
User-facing: yes/no
Stack: [server framework] + [LLM framework]
Config: .env / .envrc / k8s
Deployment infra: [platform | none found]
```

Use `AskUserQuestion` to verify: "Does this diagram and map accurately represent your system? Anything I missed?"
Wait for confirmation before proceeding to Phase 0b.

---

## Phase 0b: Agentic Workflow + UX Mapping

> 🧠 **What we're doing:** Mapping failure modes before proposing signals. Kelet clusters spans by *failure pattern*
> — every failure mode found here becomes a signal candidate in 0c. Signals without a failure map are guesses.

**Workflow** (what the agent does):
- Steps and decision points
- Where it could go wrong: wrong retrieval, hallucination, off-topic, loops, timeouts
- What success vs. failure looks like from the agent's perspective

**UX** (if user-facing):
- What AI-generated content is shown? (answers, suggestions, code, summaries)
- Where do users react? (edit it, retry, copy, ignore, complain)
- What implicit behaviors signal dissatisfaction? (abandon, rephrase, undo)

Present the workflow + UX map and **wait for confirmation** before proceeding to Phase 0c.

---

## Phase 0c: Signal Brainstorming

> 🧠 **What we're doing:** Choosing where to drop the tips. Signals aren't pass/fail verdicts — they're directional
> cues pointing Kelet's investigation. Three layers: explicit (user votes), coded (behavioral hooks), synthetic (automated).

Reason about failure modes, then propose signals across three layers — propose all that apply:

**1. 📡 Explicit** — find every UX touchpoint with AI output. Existing feedback UI → wire to it, don't replace.
No feedback → suggest VoteFeedback. Editable AI output → track edits ("close but wrong").

**2. 📡 Coded** — real behavioral hooks: dismiss, accept, retry, undo, escalate. Wire `kelet.signal()` to exact
locations. Verify each event is AI-specific, not a general UI action.

**3. 📡 Synthetic** — LLM-as-judge or heuristic evaluators from failure modes in 0b. Cold-start strategy: runs on
every session before real users contribute signals. Ground every proposal in observed behavior — don't invent
features. If unsure whether the agent produces a given output (citations, scores, structured data), ask before
proposing an evaluator that depends on it.

**Selection principle:** map each failure mode from 0b to a failure category (comprehension, execution,
correctness, usefulness, behavior, user reaction) — then pick ONE evaluator per category. Two evaluators on
the same category multiply noise without adding information. Prefer platform presets by exact name. See
[references/signals.md](references/signals.md) for the full selection framework, preset list, and deeplink
generation.

**STOP — this is a REQUIRED interactive checkpoint.** Use `AskUserQuestion` with `multiSelect: true`:
1. One question for explicit + coded signals (options = each proposed signal)
2. One question for synthetic evaluators (options = each proposed evaluator)

Ask if any coded signals need steering and wait for their response.

**You don't need to implement synthetics — let Kelet do it.** After the developer selects evaluators, generate
the deeplink scoped to exactly those choices and present as a bold standalone action item:

> **Action required → click this link to activate your synthetic evaluators:**
> `https://console.kelet.ai/synthetics/setup?deeplink=<encoded>`
>
> This will generate evaluators for: [list selected names]. Click "Activate All" once you've reviewed them.

See [references/signals.md](references/signals.md) for the deeplink payload schema, generation snippet, signal
kinds, sources, and naming conventions. Confirm via `AskUserQuestion` that they've clicked and activated before
proceeding to Phase 0d.

Only write `source=SYNTHETIC` signal code if the developer explicitly asks AND the platform cannot implement it
— explain why and ask them to confirm before proceeding.

---

## Phase 0d: What You'll See in Kelet

> 🧠 **What we're doing:** Previewing the console before writing code — so every implementation step has a visible
> target and the developer knows exactly what they're building toward.

| After implementing                | Visible in Kelet console                                                 |
|-----------------------------------|--------------------------------------------------------------------------|
| `kelet.configure()`               | LLM spans in Traces: model, tokens, latency, errors                      |
| `agentic_session()`               | Sessions view: full conversation grouped for RCA                         |
| VoteFeedback                      | Signals: 👍/👎 correlated to the exact trace that generated the response |
| Edit signals (`useFeedbackState`) | Signals: what users corrected — reveals model errors                     |
| Platform synthetics               | Signals: automated quality scores Kelet runs on your behalf              |

---

## Sessions

A session = one unit of work. New context = new session.

**Framework orchestrates?** (pydantic-ai, LangChain, LangGraph, LlamaIndex, CrewAI, Haystack, DSPy, LiteLLM,
Langfuse, or any framework using OpenInference/OpenLLMetry): sessions inferred automatically. If unlisted, research
whether it uses one of these before omitting `agentic_session()`.

**Must use `agentic_session(session_id=...)`** in two cases (both **silent** if omitted):
- **App owns the session ID** (Redis, DB, server-generated and returned to client): the framework doesn't know it
  — Kelet generates a different ID, breaking VoteFeedback linkage. Required even with a supported framework.
- **You own the loop** (calling agent A → agent B, Temporal, custom orchestrators — even if individual steps use a
  supported framework internally): no framework sets a session ID for the overall flow. **Silent — spans appear as
  unlinked individual traces.** TypeScript: `agenticSession({ sessionId }, callback)`.

⚠️ **Vercel AI SDK** doesn't set session IDs automatically even though it's a supported framework — use
`agenticSession()` at the route level.

---

## Phase 1: API Key Setup

> 🔑 **Two key types, never mixed.** Secret key = server traces. Publishable key = browser feedback widget.
> The SDK accepts either without erroring — mixing is a silent failure.

Two key types — never mix them:
- **Secret key** (`KELET_API_KEY`): server-only. Traces LLM calls. Never expose to frontend.
- **Publishable key** (`VITE_KELET_PUBLISHABLE_KEY` / `NEXT_PUBLIC_KELET_PUBLISHABLE_KEY`): frontend-safe.
  Used in `KeletProvider` for VoteFeedback.

**Ask for API keys during planning** (before calling ExitPlanMode). Use `AskUserQuestion` with an "I'll paste it
in Other" option. If they don't have a key: direct them to **https://console.kelet.ai/api-keys**.

Do not proceed until both required keys are in hand (or explicitly deferred with a placeholder).

**Project name workflow:**
1. Suggest a name based on the app (e.g. "docs-ai" → "docs_ai_prod").
2. Instruct: "Create this project in the Kelet console — click the project name in the **top-nav** at
   console.kelet.ai, then 'New Project'."
3. Ask via `AskUserQuestion`: "Have you created the project? What is the exact name you used?" — wait.
4. If not created: omit `project=` — Kelet routes to the default project automatically.
5. Once confirmed: write to env file as `KELET_PROJECT` (server) / `VITE_KELET_PROJECT` (Vite) /
   `PUBLIC_KELET_PROJECT` (SvelteKit) / `NEXT_PUBLIC_KELET_PROJECT` (Next.js).
   **Never hardcode the project name string in source files.**

Write to the correct file based on config pattern: `.env` → `KEY=value` · `.envrc` → `export KEY=value` ·
K8s → tell developer to add to secrets manifest. Add both vars to `.gitignore`.

**Production secrets — `.env` is local dev only.** Follow [references/deployment.md](references/deployment.md)
for platform-specific steps. Confirm completion with `AskUserQuestion` before proceeding.

**If deployment method is unknown**: ask "How do you deploy to production? How are secrets managed there?" — wait.

---

## Implementation: Key Concepts by Stack

See [references/api.md](references/api.md) for exact function signatures and package names.
See [references/stack-notes.md](references/stack-notes.md) for full per-stack details, gotchas, and code patterns.

**Python**: `kelet.configure()` at startup; `agentic_session()` required when you own the orchestration loop.
Streaming: wrap entire generator body — see stack-notes.md.
```python
kelet.configure(api_key=os.environ["KELET_API_KEY"], project=os.environ["KELET_PROJECT"])

async with kelet.agentic_session(session_id=session_id):
    result = await agent.run(...)
```

**TypeScript/Node.js**: `agenticSession` is **callback-based** (not a context manager) — critical difference.
Requires OTEL peer deps alongside `kelet`.
```ts
configure({ apiKey: process.env.KELET_API_KEY, project: process.env.KELET_PROJECT });

await agenticSession({ sessionId }, async () => {
  return await chain.invoke(...);
});
```

**Next.js**: `KeletExporter` in `instrumentation.ts` via `@vercel/otel`. Two configs commonly missed (both
**silent** if omitted) — see stack-notes.md.

**Multi-project / React**: one `configure()` call, per-session `project=` override; `KeletProvider` at app root.
No-React frontend? Present options before proceeding — see stack-notes.md.

**Which feedback hook:**
- Explicit rating of AI response → `VoteFeedback`
- Editable AI output → `useFeedbackState` with trigger names
- Coded behavioral events (abandon, retry, copy) → `useKeletSignal()`

---

See [references/implementation.md](references/implementation.md) for the decision tree and implementation steps.

---

## Phase V: Post-Implementation Verification

> 🕵️ **What we're doing:** Proving it works. Kelet silences all SDK errors — a broken integration looks identical
> to a working one. "Build passed" is not evidence. Only the console confirms it.

Key things to verify:
- Every agentic entry point covered by `agentic_session()` or a supported framework — missing one = silent
  fragmented traces
- Session ID consistent end-to-end: client → server → `agentic_session()` → response header → VoteFeedback
- `kelet.configure()` called once at startup, not per-request
- Secret key is server-only — never in the frontend bundle
- Check [references/common-mistakes.md](references/common-mistakes.md) for silent failure modes on the detected stack
- Smoke test: trigger an LLM call → open the Kelet console → verify sessions are appearing (allow a few minutes
  for ingestion)
- If VoteFeedback added: use the browser tool to screenshot the feedback bar.
  Verify it looks on-brand. Confirm `document.querySelectorAll('button button').length === 0` — VoteFeedback
  renders its own `<button>`; children must not be `<button>` or you get invalid nested buttons that corrupt HMR.
- After ANY frontend changes: screenshot existing pages (not just the new feature) to verify they still render —
  tsconfig overrides or invalid HTML can silently break unrelated pages. Build passing ≠ pages unaffected.

---

## Common Mistakes

See [references/common-mistakes.md](references/common-mistakes.md) for the full table of silent failure modes.
Review during Phase V, checking every entry that applies to the detected stack.
