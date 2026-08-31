# SP Methodology Record Production

You produce Sprint Planning (SP) methodology records that satisfy the BMAD methodology gate (Gate 2: IR → SP → S).

## Persistent Facts

- Load `{project-root}/docs/bmad/research-methodology.md` and `development-methodology.md` if present.
- SP guarantees the sprint scope is clear, measurable, and realistic.

## Production Rules

1. **Before producing the record**, verify the methodology manifesto's gate rules for the relevant module: the evidence type and record format of the output.
2. **When the record is complete**, verify it is complete: English field labels, decision rationale, uncertainty disclosure.
3. **Bridge rule**: after producing the native sprint-status.yaml, create the SP record at `docs/development/SP-<seq>.md` per §2.2 of the bridge doc. Copy the template from `docs/development/_template_SP.md` and fill fields with English labels:
   - **Date** (date)
   - **Status**: `planned` | `in-progress` | `completed` | `cancelled`
   - **Sprint Goal**: single sentence
   - **Stories**: S-id list + priority + story points
   - **Capacity**: estimated points / team velocity
   - **Technical Debt**: this sprint's debt items + total load
   - **Blockers**: known blockers + resolution plan
   - **Dependencies**: external team/system dependencies
4. **Tech-debt cap rule**: the 'Technical Debt' section cannot be left empty. Read the P0 table from `docs/development/tech-debt.md`; reference every TD-XXX ID even if out of scope. If P0 table is empty, write 'Technical Debt: (no P0, the manifesto's 20% time-box rule does not apply to this sprint)'. This enforces the 'Technical debt cannot be hidden' (manifesto §3.3) rule.
5. The Status field must be one of the allowed values and the Date field must be present (checked by `scripts/check-methodology.sh §6`).

## Verification

After creating the record, verify: `ls -la docs/development/SP-<seq>.md` and `grep -E "TD-[0-9]+|no P0" docs/development/SP-<seq>.md`. If 0 lines, error and recreate.

## Output Format

Produce the record as a complete markdown document with all English field labels present and filled with the scenario's data.
