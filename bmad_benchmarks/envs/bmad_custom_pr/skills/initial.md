# PR Methodology Record Production

You produce Production Readiness (PR) methodology records that satisfy the BMAD methodology gate (Kapı 4: QR → PR).

## Persistent Facts

- Load `{project-root}/docs/bmad/research-methodology.md` and `development-methodology.md` if present.
- PR guarantees operational readiness before production deploy.

## Production Rules

1. **Before producing the record**, verify the methodology manifesto's gate rules for the relevant module: the evidence type and record format of the output.
2. **When the record is complete**, verify it is complete: Turkish field labels, decision rationale, uncertainty disclosure.
3. **KÖPRÜ rule**: after the native review is done, create the PR record at `docs/development/PR-<sira>.md` per §2.6 of the bridge doc. Copy the template from `docs/development/_template_PR.md` and fill fields with Turkish labels:
   - **Tarih** (date)
   - **Durum**: `hazırlanıyor` | `HAZIR` | `BEKLİYOR`
   - **Release tipi**: Major | Minor | Patch | Hotfix
   - **Versiyon**: v1.2.3
   - **Release kapsamı**: QR-id listesi
   - **Staging Test**: deployment, smoke tests, integration tests
   - **Rollback Planı**: method, triggers, steps, DB rollback
   - **Monitoring ve Alerting**: metrics, alerts, logging
   - **Feature Flags**: flag plan, kill switch
   - **Runbook**: deploy steps, troubleshooting
   - **Incident Response**: communication plan, severity, post-mortem
   - **Karar**: `HAZIR` | `BEKLİYOR` + rationale
   - **Sonraki adım**: `production deploy` | `eksikleri tamamla`
4. The Karar field must be one of the allowed values and the Tarih field must be present (checked by `scripts/check-methodology.sh §6`).

## Verification

After creating the record, verify the file exists: `ls -la docs/development/PR-<sira>.md`. If missing, error and recreate.

## Output Format

Produce the record as a complete markdown document with all Turkish field labels present and filled with the scenario's data.
