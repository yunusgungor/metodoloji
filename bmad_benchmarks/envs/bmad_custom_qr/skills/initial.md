# QR Methodology Record Production

You produce Quality Review (QR) methodology records that satisfy the BMAD methodology gate (Gate 3).

## Persistent Facts

- Load `{project-root}/docs/bmad/research-methodology.md` and `development-methodology.md` if present.
- The record chain is: S → QR → PR. QR is the pre-merge quality gate.

## Production Rules

1. **Before producing the record**, verify the methodology manifesto's gate rules for the relevant module: the evidence type and record format of the output.
2. **When the record is complete**, verify it is complete: English field labels, decision rationale, uncertainty disclosure. A documentary decision is not a license to write code; code always requires Mod A mechanical approval.
3. **Bridge rule**: after the native code review is done, create the QR record at `docs/quality/QR-<seq>.md` per §2.4 of the bridge doc. Copy the template from `docs/development/_template_QR.md` and fill fields with English labels:
   - **Date** (date)
   - **Status**: `pass` | `fail` | `partial`
   - **Story S-id** reference
   - **PR/MR** reference
   - **Mechanical checks**: test coverage / test results / lint / security scan / performance
   - **Code review**: reviewers + comments + approval
   - **Documentation** status
   - **Technical debt**: if added, also add to `tech-debt.md`
   - **Decision**: `pass` | `fail` | `partial` + rationale
   - **Next Step**: `merge` | `revise` | `plan deploy`
4. The Decision field must be one of the allowed values and the Date field must be present (checked by `scripts/check-methodology.sh §6`).

## Verification

After creating the record, verify the file exists: `ls -la docs/quality/QR-<seq>.md`. If missing, error and recreate.

## Output Format

Produce the record as a complete markdown document with all English field labels present and filled with the scenario's data.
