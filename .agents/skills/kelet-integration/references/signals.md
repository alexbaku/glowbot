# Kelet Signals Reference

## Contents
- [Signal Kinds](#signal-kinds) and [Sources](#signal-sources)
- [Synthetic Signals: Platform vs Code](#synthetic-signals-platform-vs-code)
- [Signal Brainstorming: 3–5 per flow](#signal-brainstorming-35-per-flow)
- [Required Fields](#required-fields)
- [Selecting Synthetic Evaluators](#selecting-synthetic-evaluators) — framework + preset list
- [Synthetic Deeplink Generation](#synthetic-deeplink-generation)
- [Naming Conventions](#naming-conventions)

---

## Signal Kinds

| Kind        | Use when                                                                |
|-------------|-------------------------------------------------------------------------|
| `FEEDBACK`  | User explicitly rates quality (thumbs up/down, star rating)             |
| `EDIT`      | User modifies AI-generated content — implicit "this was wrong"          |
| `EVENT`     | A notable action occurred (retry clicked, flow abandoned, feature used) |
| `METRIC`    | A numeric quality measurement (score 0.0–1.0)                           |
| `ARBITRARY` | Custom/untyped observation that doesn't fit above                       |

## Signal Sources

| Source      | Use when                                         |
|-------------|--------------------------------------------------|
| `HUMAN`     | Signal came from a real user action              |
| `LABEL`     | Signal came from a human labeling/review process |
| `SYNTHETIC` | Automated signal — **see platform note below**   |

## Synthetic Signals: Platform vs Code

**Synthetic signals are Kelet's responsibility, not the developer's.**

For LLM-as-judge evaluators, heuristic checks, quality monitors:
→ Direct the developer to `https://console.kelet.ai/synthetics`
Kelet manages evaluators there on their behalf — no code required, cold-start solution included.

Only write `source=SYNTHETIC` signal code if:

1. Developer explicitly requests it, AND
2. The platform genuinely cannot implement it (explain why, ask developer to confirm)

## Signal Brainstorming: 3–5 per flow

Cap proposals at 5 per agentic flow. Prioritize by signal-to-noise:

- **Highest value**: edit signals (user directly shows what was wrong) and explicit downvotes
- **High value**: abandonment / retry events (strong implicit dissatisfaction signal)
- **Medium value**: tool call failures, API errors (automated, low noise)
- **Lower value**: generic page events (high noise, less specific to agent quality)

For each proposal, state: what it captures → how it manifests → what failure it reveals to Kelet's RCA engine.

## Required Fields

- `kind` (required)
- `source` (required)
- `session_id` OR `trace_id` (at least one required — auto-resolved from `agentic_session` context if not passed
  explicitly)
- `trigger_name` (optional) — identifies what the signal represents; see naming conventions below
- `score` (0.0–1.0 if provided)
- `value` (optional) — text content: feedback text, edit diff, reasoning, etc.
- `confidence` (0.0–1.0 if provided)
- `metadata` (optional) — arbitrary dict for extra context

---

## Selecting Synthetic Evaluators

A synthetic evaluator is a tip that fires on every session. Kelet clusters sessions by signal patterns to find
root causes. Good evaluators make the clusters sharp; bad ones add noise.

**Core selection framework:**

1. **One per failure category, no overlap.** Every agent fails in a finite set of ways. Map each failure mode
   from Phase 0b to a category, then pick ONE evaluator per category. Two evaluators on the same category
   (e.g. `Completeness` + `Relevance` + `Answer Relevancy`) multiply noise without adding information.

   | Category | What it measures | When it matters |
   |----------|-----------------|-----------------|
   | Comprehension | Did it understand what was asked? | Always |
   | Execution | Did it take the right actions? (retrieval, tool choice) | RAG, multi-tool |
   | Correctness | Is the output factually right? | RAG, knowledge agents |
   | Usefulness | Is the output actionable and complete? | Always |
   | Behavior | Was the interaction appropriate? | Customer-facing, role-based |
   | User reaction | Implicit signal from the user's next action | Always (if multi-turn) |

2. **Captures what traces can't.** Traces already record latency, tokens, tool calls, errors. Evaluators
   should measure what's invisible in the trace: semantic quality, faithfulness to context, user satisfaction.

3. **Grounded in the agent's actual behavior.** `RAG Faithfulness` is useless without a retrieval step.
   `Tool Usage Efficiency` is useless without tool calls. Match the evaluator to what the agent actually does.

4. **Type is determined by the check, not the concept.** If understanding content is required to make the
   judgment, it's `llm` — even if the concept sounds simple. `code` is ONLY for checks a junior dev could
   write in one line without reading the content (`len()`, `json.parse()`, regex, field presence).

**Prefer platform presets** — the Kelet console has built-in evaluators for common patterns. Use the exact
preset name in the deeplink; the platform auto-configures them. Custom evaluators only when no preset fits.

**Universal — apply to almost any agent:**

| Preset Name | Type | Catches |
|------------|------|---------|
| `Task Completion` | llm | Did the agent accomplish the user's goal? |
| `Conversation Completeness` | llm | User intentions left unaddressed or deflected |
| `Answer Relevancy` | llm | Off-topic responses, padding, missed the actual question |
| `Sentiment Analysis` | llm | User frustration, dissatisfaction, repeated corrections throughout the session |
| `Session Health Stats` | code | Turn counts, token usage, tool frequency — structural anomalies |

**RAG / retrieval agents:**

| Preset Name | Type | Catches |
|------------|------|---------|
| `RAG Faithfulness` | llm | Claims contradicting retrieved documents — context-specific hallucination |
| `Hallucination Detection` | llm | Fabricated facts, non-existent citations (no retrieval context required) |

**Multi-tool / agentic:**

| Preset Name | Type | Catches |
|------------|------|---------|
| `Loop Detection` | code | Repeated tool calls, circular execution patterns |
| `Tool Usage Efficiency` | llm | Redundant calls, retry loops, poor sequencing |
| `Knowledge Retention` | llm | Agent forgets facts the user provided earlier in the session |

**Role / behavior:**

| Preset Name | Type | Catches |
|------------|------|---------|
| `Role Adherence` | llm | Agent drifts outside its assigned scope or persona |
| `Agent Over-Compliance` | llm | Sycophancy — changing answer when user pushes back without new info |

⚠️ Type trap: "did the agent refuse when it should have helped?" sounds binary but requires understanding intent
→ always `llm`. Only use `code` if a junior dev could write the check in one line without reading the content.

---

## Synthetic Deeplink Generation

Base64url-encode the payload, then append to `https://console.kelet.ai/synthetics/setup?deeplink=`:

```python
python3 -c "
import base64, json
payload = {
    'use_case': '<agent use case>',
    'ideas': [
        {'name': '<name>', 'evaluator_type': 'llm', 'description': '<description>'},
        {'name': '<name>', 'evaluator_type': 'code', 'description': '<description>'},
    ]
}
encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).rstrip(b'=').decode()
print(f'https://console.kelet.ai/synthetics/setup?deeplink={encoded}')
"
```

Include only evaluators the developer selected. Add `"context"` to an idea only to steer the evaluator toward
something specific. `evaluator_type`: `"code"` = deterministic check; `"llm"` = semantic/qualitative.

---

## Naming Conventions

Use `trigger_name` to identify what a signal represents. Follow `source-action` format: lowercase, hyphenated, two-part
names that reflect where the signal came from and what happened.

| Good             | Bad                      | Why                                             |
|------------------|--------------------------|-------------------------------------------------|
| `user-vote`      | `good-response`          | Name the source+action, not the assumed quality |
| `user-edit`      | `edit`                   | Include source to distinguish from system edits |
| `user-retry`     | `retry_button_clicked`   | Concise; no UI implementation details           |
| `system-timeout` | `timeout_error_occurred` | Describe the signal, not the error log          |

Kelet clusters by `trigger_name` — inconsistent names fragment analytics. Same behavior across projects → same name.
