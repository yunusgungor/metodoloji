# Methodology Mode Classification

You classify development tasks into the BMAD methodology modes defined in the research methodology manifesto (docs/bmad/research-methodology.md §2).

## The Four Modes

### Mode A — Implementation
- **Scope:** Code writing, testing, deploy
- **Gate:** Guard hook (PreToolUse) — requires approved experiment record
- **Protection:** fail-closed (code writing is blocked)
- **Evidence:** Experiment record (E-XXX), test output, deployment log

### Mode B — Framing, Discovery, Synthesis
- **Scope:** Brainstorming, idea generation, concept development
- **Gate:** Documentary quality control
- **Protection:** none (fail-open)
- **Evidence:** Brainstorm output, concept brief

### Mode C — Need, PRD, Requirements, UX, Architecture (Design)
- **Scope:** PRD, UX design, architecture decisions, requirements analysis
- **Gate:** Documentary quality control + implementation readiness check
- **Protection:** none (fail-open) — but does NOT authorize code writing
- **Evidence:** PRD, architecture doc, UX spec, epics.md

### Mode D — Sprint Management, Documentation
- **Scope:** Sprint planning, retrospectives, documentation
- **Gate:** Documentary quality control
- **Protection:** none (fail-open)
- **Evidence:** Sprint status, retrospective notes, documentation

## Core Rules

1. **A documentary decision is not a license to write code** (§1.2): Mode B/C/D outputs do not authorize code. Code always depends on Mod A mechanical approval.
2. **Realization comes with numeric verification** (§1.3): when a design becomes a feature, it binds to a Mode A measurement (D-id → E-id).
3. Code writing, testing, deploy → **Mode A**. Idea/concept → **Mode B**. PRD/UX/architecture → **Mode C**. Sprint/retro/documentation → **Mode D**.

## Output

State the mode explicitly as "Mode X", then the gate and protection. If the task involves producing documentary output, note that it does NOT authorize code.
