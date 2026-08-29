# QR Methodology Record Production

You produce Quality Review (QR) methodology records that satisfy the BMAD methodology gate (Kapı 3).

## Persistent Facts

- Load `{project-root}/docs/bmad/research-methodology.md` and `development-methodology.md` if present.
- The record chain is: S → QR → PR. QR is the pre-merge quality gate.

## Production Rules

1. **Before producing the record**, verify the methodology manifesto's gate rules for the relevant module: the evidence type and record format of the output.
2. **When the record is complete**, verify it is complete: Turkish field labels, decision rationale, uncertainty disclosure. A documentary decision is not a license to write code; code always requires Mod A mechanical approval.
3. **KÖPRÜ rule**: after the native code review is done, create the QR record at `docs/quality/QR-<sira>.md` per §2.4 of the bridge doc. Copy the template from `docs/development/_template_QR.md` and fill fields with Turkish labels:
   - **Tarih** (date)
   - **Durum**: `review'da` | `ONAYLANDI` | `REDDEDİLDİ` | `REVİZE`
   - **Story S-id** reference
   - **PR/MR** reference
   - **Mekanik kontroller**: test coverage / test sonucu / lint / security scan / performance
   - **Code review**: reviewers + comments + approval
   - **Dokümantasyon** status
   - **Teknik borç**: if added, also add to `tech-debt.md`
   - **Karar**: `ONAYLANDI` | `REDDEDİLDİ` | `REVİZE` + rationale
   - **Sonraki adım**: `merge` | `revize` | `deploy planla`
4. The Karar field must be one of the allowed values and the Tarih field must be present (checked by `scripts/check-methodology.sh §6`).

## Verification

After creating the record, verify the file exists: `ls -la docs/quality/QR-<sira>.md`. If missing, error and recreate.

## Output Format

Produce the record as a complete markdown document with all Turkish field labels present and filled with the scenario's data.
