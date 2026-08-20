# Story {{epic_num}}.{{story_num}}: {{story_title}}

Status: ready-for-dev

<!-- YAML Frontmatter (otomatik doldurulur) -->
<!--
baseline_commit: {{commit_hash}}
experiment_refs:
  - id: E-001
    scope: "AC-001, AC-002"
    status: ONAYLANDI  # ONAYLANDI | BEKLİYOR | REDDEDİLDİ
  - id: E-002
    scope: "AC-003"
    status: ONAYLANDI
-->

<!-- Metodoloji kaydi: (bmad-create-story tarafindan otomatik doldurulur) -->
<!-- Metodoloji kaydi yolu: docs/development/stories/S-<sira>.md -->

## Story

As a {{role}},
I want {{action}},
so that {{benefit}}.

## Acceptance Criteria

<!-- ZORUNLU: Her AC icin asagidaki metadata alanlari doldurulmalidir.
     Eksik metadata = story validate edilemez.
     
     alan aciklamalari:
     - [AC-XXX]       : Benzersiz AC identifier (hikaye icinde benzersiz olmali)
     - Experiment     : Bagli deney kayit ID'si (E-XXX) veya — (henuz baglanmadi)
     - Type           : agent-verifiable | user-evaluable | hybrid
     - Measured       : true | false (deney sonucu olup olmadigi)
     - Verify         : Dogrulama yontemi (curl, puppeteer, lighthouse, manual, vs.)
     - [HYPOTHESIS]   : Deney onaysiz AC icin zorunlu etiket
-->

1. [AC-001] **Given** {{precondition}} **When** {{action}} **Then** {{expected_outcome}}
   - Experiment: {{experiment_id}}
   - Type: agent-verifiable
   - Measured: {{true|false}}
   - Verify: {{verification_method}}

2. [AC-002] **Given** {{precondition}} **When** {{action}} **Then** {{expected_outcome}}
   - Experiment: {{experiment_id}}
   - Type: hybrid
   - Measured: {{true|false}}
   - Verify: {{verification_method}}

## Technical Tasks

<!-- ZORUNLU: Her task'in hangi AC'yi hedefledigini belirt (AC: # formatinda).
     Bir task birden fazla AC'yi hedefleyebilir.
     Bir AC birden fazla task ile karsilanabilir.
     AC referansi olmayan task = validation'da uyari verir.
-->

- [ ] Task 1: {{task_description}} (AC: AC-001)
  - [ ] Subtask 1.1: {{subtask_description}}
  - [ ] Subtask 1.2: {{subtask_description}}
- [ ] Task 2: {{task_description}} (AC: AC-002)
  - [ ] Subtask 2.1: {{subtask_description}}

## Definition of Done

<!-- ZORUNLU: Her DoD item'i asagidaki formatinda olmalidir.
     AC ile iliskili maddeler icin AC-XXX referansi zorunludur.
     Dogrulama yontemi tanimlanmali (otomatik test, manual kontrol, vs.)
-->

- [ ] DoD-001: Tüm acceptance criteria karşılandı (AC: AC-001, AC-002, AC-003)
  - Verify: Otomatik test + curl/puppeteer dogrulama
  - Evidence: {{test_output_or_screenshot}}
- [ ] DoD-002: Birim testleri eklendi ve geçiyor (AC: AC-001)
  - Verify: `npm test` veya `pytest` ciktisi
  - Evidence: {{test_output}}
- [ ] DoD-003: Regression testleri geciyor
  - Verify: Mevcut test suite'in tamami pass
  - Evidence: {{test_output}}
- [ ] DoD-004: Code review tamamlandi
  - Verify: QR kaydi olusturuldu
  - Evidence: {{qr_record_path}}
- [ ] DoD-005: Canli ortamda dogrulandı (gerekirse)
  - Verify: {{verification_method}}
  - Evidence: {{evidence}}

## Dev Notes

- Relevant architecture patterns and constraints
- Source tree components to touch
- Testing standards summary

### Project Structure Notes

- Alignment with unified project structure (paths, modules, naming)
- Detected conflicts or variances (with rationale)

### References

- Cite all technical details with source paths and sections, e.g. [Source: docs/<file>.md#Section]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

### Change Log

## Quality Record (QR)

<!-- Implementasyon tamamlandiktan sonra doldurulur.
     QR kaydi, DoD maddelerinin kanitini icerir.
     Kayit zinciri: S → QR → PR
-->

| DoD Item | Durum | Kanit | Tarih |
|----------|-------|-------|-------|
| DoD-001 | ⏳ pending | — | — |
| DoD-002 | ⏳ pending | — | — |
| DoD-003 | ⏳ pending | — | — |
| DoD-004 | ⏳ pending | — | — |
| DoD-005 | ⏳ pending | — | — |

### QR Summary

- **Total DoD Items**: {{total}}
- **Passed**: {{passed}}
- **Failed**: {{failed}}
- **QR Record Path**: docs/quality/QR-{{sira}}.md
