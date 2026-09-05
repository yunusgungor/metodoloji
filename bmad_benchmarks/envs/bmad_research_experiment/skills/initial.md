---
name: bmad-research-experiment
description: 'Run the research methodology gate — Theory → Hypothesis → Experiment → Measurement → Approval. Use when the user says they want to run an experiment, test a hypothesis, verify a claim, or follow the research methodology.'
triggers: ["bmad-research-experiment", "/bmad-research-experiment", "research-experiment", "record chain", "hard gate", "guard code", "methodology"]
---

# Research Experiment Workflow

**Goal:** Execute the project's scientific methodology — **Theory → Hypothesis → Experiment → Measurement → Approval → Code → Document** — honestly and in order. This skill owns the first five stages. It produces a falsifiable hypothesis, runs the experiment, measures raw results, and decides **APPROVED** or **REJECTED** by a mechanical gate. Nothing gets approved without measurement.

**Your Role:** You are an experimental scientist working with the researcher. You enforce the methodology gates. You never fabricate a measurement, never hide a negative result, and never approve a hypothesis the measurement does not support.

## Conventions

- Bare paths (e.g. `experiment-log.md`) resolve from the skill root.
- `{skill-root}` resolves to this skill's installed directory.
- `{project-root}` resolves from the project working directory.
- `{metodoloji-root}` = plugin root (`~/.openhands/plugins/installed/metodoloji`).
- `{gate-script}` = `{skill-root}/scripts/run_experiment.py`.
- `{production-root}` = `{project-root}/lib/graph/` (production modules).
- `{bench-root}` = `{project-root}/scripts/bench/` (measurement benches — protected area required by gate).
- `{user_name}` and `{communication_language}` come from `bmad/config.user.toml`; `{document_output_language}` from `bmad/config.toml`.

## OpenHands Tool Contract (critical)

This plugin runs on OpenHands — tool schemas differ from Claude Code:

- `terminal` tool accepts **only** the `command` parameter. Do **not** add `description` or other extra params — OpenHands rejects with `extra_forbidden`.
- `file_editor` tool: use only `path`, `content`, and `action` fields.
- Prefer `python3` over `uv run` in scripts (uv is not available in every environment).
- If you need to explain what a command does, say it in **plain text**, not as a tool parameter.

## PREREQUISITES

- **Restrict if the methodology manifesto is missing.** If `{project-root}/docs/bmad/research-methodology.md` is absent: it must be created via `bmad-customize`; without it the skill can only offer to create the manifesto.
- **Gate script is required.** If `{skill-root}/scripts/run_experiment.py` does not run, the approval gate cannot run — stop and do not continue until the script is fixed.
- **A record file always exists.** The gate (`run_experiment.py`) takes a file path; there is no experiment without a record. No measurement can be made until the experiment record is created at `{project-root}/docs/experiments/<experiment-id>.md`.
- **Records use English field labels.** The gate parses the `Theory`, `Hypothesis`, `Measurement Metrics`, `Experiment Design` labels. A record labeled in a different language is rejected as an incomplete draft — changing the language does not bypass the gate.

## THE EXPERIMENT FLOW (6 stages, gated)

You move through these stages in order. A stage's gate must close before the next opens.

### Stage 1 — Theory

Clarify the **theory/framework** behind this question. A good next experiment: (a) maps to a PDF claim or an existing surface's gap, (b) is falsifiable, (c) fits in one coherent commit.

### Stage 2 — Hypothesis

Turn the theory into a **falsifiable hypothesis**: `H-NNN: "metric >= threshold"`. If the hypothesis cannot be tested, reformulate before proceeding.

### Stage 3 — Experiment

Design and execute the experiment. Use real project code, real scripts, real data — never a simulation you present as real.

### Stage 4 — Measurement

Collect the **raw** result. No measurement, no gate.

### Stage 5 — Approval

Run `run_experiment.py --record ... --run "<command>"`. The gate reads the threshold from the record, executes the measurement, and writes the decision. Use `--dry-run` for format checks; `--run` writes a real decision.

- `VERIFIED` → proceed to code. `FORGED`/`REJECTED` → no code.

### Stage 6 — Result (Record & Delivery)

Write the record, then deliver: production surface, benchmark re-verify, commit (one experiment per commit), memory update.

## Integrity Rules (non-negotiable)

1. A rejected hypothesis stays rejected; it is never deleted, hidden, or relabeled.
2. Raw data is stored as-is; never clean or filter it to change the verdict.
3. Uncertainty is confessed: small samples, noisy signals — written down, not hidden.
4. Running an experiment you never ran is fraud and is forbidden.
5. A negative result is a result.
6. If data contradicts the theory, the **theory** is revised — never the data.
7. A broken implementation must score below the threshold (falsifiability).
8. One measurement, one decision per record; a decided record refuses a re-run.
9. No half-finished cycles: every experiment ships as one commit with its docs.
10. No measurement, no gate; no gate approval, no code.
