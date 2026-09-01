---
name: bmad-code-docs
description: 'Code docs management — recall, query, generate, auto-load.'
triggers: ["bmad-code-docs", "recall", "remember", "code docs", "history"]
---

# Code Docs

**Goal:** Recall project history, generate new knowledge, and auto-load context.

## Rules

1. Every code-doc must contain valid YAML frontmatter: id, type, title, date, tags
2. Sections are written with English labels
3. Doc type must be chosen correctly: P, T, D, L, A, X
4. **Use the exact section headings defined by the doc type** — never invent
   your own headings. Each type has a fixed set of `##` sections (see below).
5. Use full type names in `type:` (pattern, troubleshooting, decision, learning,
   api, pending) — or the short codes P, T, D, L, A, X.

## Required Sections per Type

- **P (pattern):** Pattern, Usage Scenario, Example, Advantages, Disadvantages
- **T (troubleshooting):** Error, Cause, Solution, Prevention
- **D (decision):** Decision, Rationale, Results
- **L (learning):** Learned, Context, Evidence, Application
- **A (api):** API, Signature, Usage, Notes
- **X (pending):** Description, Context, Next Steps

Do not rename or reorder these headings. Optional `## Related Records` /
`## Change History` blocks may follow, but the required headings must appear
exactly as listed.
4. Related experiments and stories are added as links
5. Index updates automatically
6. **At the start of every task, relevant code-docs are loaded automatically**

## Doc Types

- **P (Pattern):** Pattern, usage, example, advantages/disadvantages
- **T (Troubleshooting):** Error, cause, solution, prevention
- **D (Decision):** Decision, rationale, results
- **L (Learning):** Learned, context, evidence, application
- **A (API):** Signature, usage, notes
- **X (Pending):** Pending items, TODO/FIXME, future plans

## Auto-Load Rules

At the start of a task, follow these steps:

1. **Extract keywords from the task description** (auth, guard, experiment, etc.)
2. **Search tags by keywords** → find relevant docs
3. **Check experiment references** (E-NNN) → find related docs
4. **Always load pending items** (those needing attention)
5. **Use the loaded context** → don't repeat the same mistakes, apply known patterns

## When to Generate a New Doc

- **When a new decision is made** → D doc
- **When a recurring pattern is detected** → P doc
- **After an experiment result** → L doc
- **When using a new API** → A doc
- **When resolving an error** → T doc
- **When seeing a TODO/FIXME or planning ahead** → X doc

## Choosing Between Pattern (P) and API (A)

- A scenario that describes **how a system works as a reusable practice**
  (a hook, a mechanism, a workflow that "can be used in other projects",
  "recurs", "is a pattern") → **P (pattern)** — even if a function signature
  is mentioned.
- A scenario that describes **using or documenting a specific function's
  interface** (signature, params, return, how to call it) → **A (api)**.
- Key test: does the scenario focus on *reuse across projects* (P) or on
  *one function's usage contract* (A)?

## Choosing Between Pattern (P) and Decision (D)

- A scenario that describes **how a mechanism/function/process works** (e.g.
  "the index is auto-updated when a doc is created", "run_batch uses
  ThreadPoolExecutor for parallel processing") → **P (pattern)** — even if it
  says "now uses" / "now creates". The subject is *how the system behaves
  recurrently*, not a deliberate choice.
- A scenario that describes **a deliberate choice / policy that was decided**
  (e.g. "we decided to adopt X instead of Y", "a meeting decided ...") → **D
  (decision)**.
- Key test: does the scenario describe *how something works repeatedly* (P) or
  *a choice that was made* (D)?

## Choosing Between Learning (L) and Other Types

- A scenario about **auto-loading / recalling context at task start** (e.g.
  "system should auto-load relevant code-docs via load_context_for_task()")
  is a **learned behavior** → **L (learning)**.
- A scenario about a **future task to do** (TODO, next step) → **X (pending)**.
- A scenario about a **recurring reusable practice** → **P (pattern)**.

## Pending (X) Doc Rules

### When to Create
- When a TODO/FIXME comment is seen
- When a future step is planned
- When an experiment fails (theory revision)
- When a dependency is detected
- When a high-priority item is identified

### Priority Levels
- **urgent**: Blocks the sprint, security issue
- **high**: Depends on experiment results, critical development
- **normal**: Standard development work
- **low**: Improvement, optimization

### Update Rules
- Completed item: `status: pending` → `status: done`
- Add completion date
- Update related experiment/story references

### Dependency Tracking
- Specify dependent items: "should be done after experiment E-148"
- Ordering: dependency must complete first
- Cross-reference: link related pending items
