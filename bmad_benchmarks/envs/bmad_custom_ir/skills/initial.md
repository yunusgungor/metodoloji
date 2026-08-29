# IR Methodology Record Production

You produce Implementation Readiness (IR) methodology records that satisfy the BMAD methodology gate (Kapı 1: E → IR → SP).

## Persistent Facts

- Load `{project-root}/docs/bmad/research-methodology.md` and `development-methodology.md` if present.
- IR is the entrance gate from research to development: research → development transition.

## Production Rules

1. **Before producing the record**, verify the methodology manifesto's gate rules for the relevant module: the evidence type and record format of the output.
2. **When the record is complete**, verify it is complete: Turkish field labels, decision rationale, uncertainty disclosure. A documentary decision is not a license to write code; code always requires Mod A mechanical approval.
3. **KÖPRÜ rule**: after producing the native implementation-readiness report, create the IR record at `docs/development/IR-<sira>.md` per §2.1 of the bridge doc. Copy the template from `docs/development/_template_IR.md` and fill fields with Turkish labels:
   - **Tarih** (date)
   - **Durum**: `hazırlanıyor` | `HAZIR` | `EKSİK`
   - **Araştırma girdileri**: E/R/D/C-id listesi
   - **Tasarım belgeleri**: PRD/UX/mimari dosya referansları
   - **Başarı kriterleri**: fonksiyonel, non-fonksiyonel, kullanıcı
   - **Teknik bağımlılıklar**: API'ler, kütüphaneler, altyapı, harici servisler
   - **Risk değerlendirmesi**: bilinen riskler + mitigation
   - **Eksikler**: eksik item → araştırma modu → tahmini süre
   - **Karar**: `HAZIR` | `EKSİK` + rationale
   - **Sonraki adım**: `sprint planlamaya geç` | `araştırmaya dön`
4. The Karar field must be one of the allowed values and the Tarih field must be present (checked by `scripts/check-methodology.sh §6`).

## Verification

After creating the record, verify the file exists: `ls -la docs/development/IR-<sira>.md`. If missing, error and recreate.

## Output Format

Produce the record as a complete markdown document with all Turkish field labels present and filled with the scenario's data.
