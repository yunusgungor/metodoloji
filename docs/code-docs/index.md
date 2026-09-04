# Code Docs Index

Structured documentation system used to remember project history and generate new knowledge.

## Categories

### [Decisions](./decisions/) — 0 records

### [Patterns](./patterns/) — 1 records
- [Test Pattern](./patterns/P-001-test-pattern.md)

### [Learnings](./learnings/) — 0 records

### [API Usages](./api/) — 1 records
- [Test API](./api/A-001-test-api.md)

### [Troubleshooting](./troubleshooting/) — 0 records

### [Pending Items](./pending/) — 0 records

## Automatic Generation

These files are generated automatically by hooks:
- **Audit hook**: Detects important events (experiment approval → learning, architecture change → decision, error in tool output → troubleshooting, TODO/future plans → pending)
- **Skill**: Manual recall and recording via `bmad-code-docs`

## Search

- By tag: `recall_by_tag("auth")`
- By experiment ID: `recall_by_experiment("E-001")`
- By category: list in the `docs/code-docs/decisions/` folder

## Automatic Loading

Relevant docs are loaded automatically at task start:

```python
# Based on task context
context = load_context_for_task("Run the guard hook auth test")

# Recent docs
recent = load_recent_docs(n=5)

# Pending items
pending = load_pending_docs()
```

## Last Update

Updated automatically — no manual editing needed.