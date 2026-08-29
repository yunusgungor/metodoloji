# SP Methodology Record Production

You produce Sprint Planning (SP) methodology records that satisfy the BMAD methodology gate (Kapı 2: IR → SP → S).

## Persistent Facts

- Load `{project-root}/docs/bmad/research-methodology.md` and `development-methodology.md` if present.
- SP guarantees the sprint scope is clear, measurable, and realistic.

## Production Rules

1. **Before producing the record**, verify the methodology manifesto's gate rules for the relevant module: the evidence type and record format of the output.
2. **When the record is complete**, verify it is complete: Turkish field labels, decision rationale, uncertainty disclosure.
3. **KÖPRÜ rule**: after producing the native sprint-status.yaml, create the SP record at `docs/development/SP-<sira>.md` per §2.2 of the bridge doc. Copy the template from `docs/development/_template_SP.md` and fill fields with Turkish labels:
   - **Tarih** (date)
   - **Durum**: `planlandı` | `devam ediyor` | `tamamlandı` | `iptal`
   - **Sprint hedefi**: single sentence
   - **Story'ler**: S-id listesi + öncelik + story points
   - **Kapasite**: estimated points / team velocity
   - **Teknik borç**: this sprint's debt items + total load
   - **Blokerler**: known blockers + resolution plan
   - **Bağımlılıklar**: external team/system dependencies
4. **Tech-debt cap rule**: the 'Teknik borç' section cannot be left empty. Read the P0 table from `docs/development/tech-debt.md`; reference every TD-XXX ID even if out of scope. If P0 table is empty, write 'Teknik borç: (P0 yok, manifestonun %20 time-box kuralı bu sprint için geçerli değil)'. This enforces the 'Teknik borç gizlenemez' (manifesto §3.3) rule.
5. The Durum field must be one of the allowed values and the Tarih field must be present (checked by `scripts/check-methodology.sh §6`).

## Verification

After creating the record, verify: `ls -la docs/development/SP-<sira>.md` and `grep -E "TD-[0-9]+|P0 yok" docs/development/SP-<sira>.md`. If 0 lines, error and recreate.

## Output Format

Produce the record as a complete markdown document with all Turkish field labels present and filled with the scenario's data.
