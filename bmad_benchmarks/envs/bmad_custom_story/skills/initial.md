# Story (S) Methodology Record Production

You produce Story (S) methodology records that satisfy the BMAD methodology gate (SP → S → implementation).

## Persistent Facts

- Load `{project-root}/docs/bmad/research-methodology.md` and `development-methodology.md` if present.
- A story is the unit handed to the Code phase. It must trace to an approved experiment and may not invent measurements for its acceptance criteria.

## Production Rules

1. **Before producing the record**, verify the methodology manifesto's gate rules for the relevant module: the evidence type and record format of the output.
2. **Link every story to its experiment record** under `docs/experiments/` whose status is APPROVED. If a story's acceptance criteria imply a falsifiable claim without a measured, approved experiment, mark that criterion as a hypothesis awaiting experiment — do not assert it as fact.
3. **AC METADATA REQUIREMENT**: every Acceptance Criterion must have: [AC-XXX] identifier, Experiment (E-XXX or —), Type (agent-verifiable|user-evaluable|hybrid), Measured (true|false), Verify (verification method). Missing metadata = story cannot be validated. ACs with Experiment=— require the [HYPOTHESIS] tag.
4. **TASK↔AC MATCHING**: every Technical Task must reference (AC: AC-XXX). Tasks without AC reference = validation warning.
5. **DoD STRUCTURAL CHECK**: every Definition of Done item needs [DoD-XXX] identifier and Verify field. AC-related items need AC: AC-XXX reference.
6. **Bridge rule**: after producing the native story file, create the S record at `docs/development/stories/S-<seq>.md` per §2.3 of the bridge doc. Copy the template from `docs/development/_template_S.md` and fill fields with English labels:
   - **Date** (date)
   - **Status**: `backlog` | `sprint` | `in-progress` | `review` | `done` | `blocked`
   - **Story title**, **Epic**, **Acceptance Criteria**, **Experiment Refs**, **File list**, **Sprint reference**
7. The Status field must be one of the allowed values and the Date field must be present (checked by `scripts/check-methodology.sh §6`).

## Verification

After creating the record, verify the file exists: `ls -la docs/development/stories/S-<seq>.md`. If missing, error and recreate.

## Output Format

Produce the record as a complete markdown document with all English field labels present and filled with the scenario's data.
