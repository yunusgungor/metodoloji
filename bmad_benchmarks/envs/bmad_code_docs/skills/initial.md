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
