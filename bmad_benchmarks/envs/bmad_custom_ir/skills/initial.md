# IR Methodology Record Production

You produce Implementation Readiness (IR) methodology records that satisfy the BMAD methodology gate (Gate 1: E → IR → SP).

## Persistent Facts

- Load `{project-root}/docs/bmad/research-methodology.md` and `development-methodology.md` if present.
- IR is the entrance gate from research to development: research → development transition.

## Production Rules

1. **Before producing the record**, verify the methodology manifesto's gate rules for the relevant module: the evidence type and record format of the output.
2. **When the record is complete**, verify it is complete: English field labels, decision rationale, uncertainty disclosure. A documentary decision is not a license to write code; code always requires Mod A mechanical approval.
3. **Bridge rule**: after producing the native implementation-readiness report, create the IR record at `docs/development/IR-<seq>.md` per §2.1 of the bridge doc. Copy the template from `docs/development/_template_IR.md` and fill fields with English labels:
   - **Date** (date)
   - **Status**: `preparing` | `READY` | `INCOMPLETE`
   - **Research Inputs**: E/R/D/C-id list
   - **Design Documents**: PRD/UX/architecture file references
   - **Success Criteria**: functional, non-functional, user
   - **Technical Dependencies**: APIs, libraries, infrastructure, external services
   - **Risk Assessment**: known risks + mitigation
   - **Gaps**: gap item → research mode → estimated time
   - **Decision**: `READY` | `INCOMPLETE` + rationale
   - **Next Step**: `proceed to sprint planning` | `return to research`
4. The Decision field must be one of the allowed values and the Date field must be present (checked by `scripts/check-methodology.sh §6`).

## Verification

After creating the record, verify the file exists: `ls -la docs/development/IR-<seq>.md`. If missing, error and recreate.

## Output Format

Produce the record as a complete markdown document with all English field labels present and filled with the scenario's data.
