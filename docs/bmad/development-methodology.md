# Geliştirme Metodolojisi Manifestosu

**Version:** 2.0.0
**Purpose:** BMAD geliştirme metodolojisinin temel kurallarını, süreç akışını ve kalite standartlarını tanımlar.

---

## §1 Geliştirme Akışı

```
Sprint Planning → Story Creation → Implementation → Testing → Code Review → Done
```

Her aşama bir öncekinin çıktısına bağlıdır.

---

## §2 Sprint Planning (Mod D)

### §2.1 Sprint Oluşturma
- `bmad-sprint-planning` ile `sprint-status.yaml` oluşturulur
- Sprint durumu: `backlog → in-progress → done`

### §2.2 Story Sıralaması
- Story'ler epic sırasına göre işlenir
- Her story bağımsız olarak tamamlanabilir
- Önceki story learnings'i sonraki story'ye aktarılır

### §2.3 Sprint Status Formatu
```yaml
development_status:
  epic-1: backlog
  1-1-user-auth: ready-for-dev
  1-2-account: in-progress
  epic-1-retrospective: optional
```

---

## §3 Story Creation (Mod C)

### §3.1 Story Oluşturma
- `bmad-create-story` ile story dosyası oluşturulur
- Story metadata'sı zorunlu: Experiment, Type, Measured, Verify
- Task↔AC eşleştirme zorunlu
- DoD identifier zorunlu

### §3.2 Story Formatı
```markdown
# Story X.Y: Title

Status: ready-for-dev
experiment_refs:
  - id: E-001
    scope: AC-001, AC-002
    status: ONAYLANDI

## Acceptance Criteria

1. [AC-001] **Given** ... **When** ... **Then** ...
   - Experiment: E-001
   - Type: agent-verifiable
   - Measured: true
   - Verify: curl

## Technical Tasks

- [ ] Task 1: Description (AC: AC-001)
  - [ ] Subtask 1.1: Detail

## Definition of Done

- [ ] DoD-001: All ACs met (AC: AC-001)
  - Verify: curl
  - Evidence: test output

## Quality Record (QR)

| DoD Item | Durum | Kanit | Tarih |
|----------|-------|-------|-------|
| DoD-001 | ⏳ pending | — | — |
```

### §3.3 Story Doğrulama
- Guard hook'u story metadata'sını doğrular
- Eksik metadata durumunda doğrulama **DENY** sonucu verilir
- Hipotez AC'ler implemente edilemez

### §3.4 Deney Onayı (Experiment Approval Gate)
- Story implementasyonuna geçiş prerequisite: tüm `experiment_refs[].status` alanları **`ONAYLANDI`** olmalıdır
- `ONAYLANDI` durumu olmayan story'ler `bmad-dev-story` (Mod A) tarafından kabul edilmez
- Guard hook, her experiment referansının durumunu `ONAYLANDI` olarak doğrular
- Deney onayı olmadan kod yazma izni verilmez

---

## §4 Implementation (Mod A)

### §4.1 Kod Yazma Kuralları
- Red-green-refactor döngüsü
- Test first development
- AC bazında implementasyon
- **Belgesel karar kod yazma izni VERMEZ**

### §4.1.1 Git İşlemleri
- Her implementasyon adımında değişiklikler commit edilmeli
- Commit mesajı formatı: `[Story X.Y] <değişiklik açıklaması>`
- Implementasyon tamamlandığında tüm değişikliklerin commit'lenmiş olması zorunludur
- Commit olmaksızın Testing (§5) aşamasına geçilemez

### §4.2 Guard Hook Entegrasyonu
- Kod yazma izni: Onaylı deney kaydı gerektirir
- Story metadata doğrulaması
- Experiment referansı kontrolü

### §4.3 Kod Kalite Standartları
- Mevcut testler geçmeli
- Yeni testler eklenmeli
- Linting ve static analysis
- Code review sonrası düzeltmeler

---

## §5 Testing (Mod A)

### §5.1 Test Stratejisi
- **Unit tests:** İş mantığı, core functionality
- **Integration tests:** Bileşen etkileşimleri
- **E2E tests:** Kullanıcı akışları
- **Regression tests:** Mevcut fonksiyonellik

### §5.2 AC Doğrulama
- Her AC'nin Verify yöntemi çalıştırılır
- Sonuçlar story dosyasına kaydedilir
- Başarısız AC = implementasyon durdurulur

### §5.3 Test Formatları
```markdown
## Test Sonuçları

### Unit Tests
- X passed, Y failed

### Integration Tests
- X passed, Y failed

### AC Doğrulama
| AC | Durum | Method | Evidence |
|----|-------|--------|----------|
| AC-001 | ✅ verified | curl | response body |
| AC-002 | ❌ failed | test | error log |
```

---

## §6 Code Review (Mod A)

### §6.1 Review Süreci
- `bmad-code-review` ile adversarial review
- Parallel review layers:
  - **Blind Hunter:** Genel kod kalitesi
  - **Edge Case Hunter:** Edge case analizi
  - **Acceptance Auditor:** AC metadata + Task↔AC + DoD kontrolü

### §6.2 Review Sonucu
- **Approve:** Story done — Approve sonrası §9 Oturum Kapanışı adımları tetiklenir
- **Changes Requested:** Düzeltilir → Tekrar review
- **Blocked:** Engeller kaldırılır → Tekrar review

### §6.3 Review Bulguları
```markdown
## Senior Developer Review (AI)

**Outcome:** Changes Requested
**Date:** 2026-08-20

### Action Items
- [ ] High: AC metadata eksik (AC-003)
- [x] Medium: Task↔AC eşleştirmesi düzeltilmiş
- [ ] Low: DoD-002 Verify alanı boş
```

---

## §7 Quality Record (QR) (Mod A)

### §7.1 QR Oluşturma
- Story tamamlandığında QR kaydı oluşturulur
- Her DoD item'ı için durum, kanıt ve tarih
- Kayıt zinciri: S → QR → PR

### §7.2 QR Formatı
```markdown
# Quality Record: QR-<sira>

| Alan | Değer |
|------|-------|
| Story | <story_key> |
| Tarih | YYYY-MM-DD |
| QR Status | pass | fail | partial |

## DoD Doğrulama Sonuçları

| DoD Item | Durum | Kanit | Tarih |
|----------|-------|-------|-------|
| DoD-001 | ✅ passed | curl output | 2026-08-20 |
| DoD-002 | ❌ failed | test output | 2026-08-20 |
```

### §7.3 QR Onayı
- Tüm DoD maddeleri passed = QR onaylı
- Kısmi onay = eksik maddeler listelenir
- Red = düzeltilmesi gereken maddeler

---

## §8 Metodoloji Uyumluluğu

### §8.1 Guard Hook Uyumluluğu
- Kod yazma izni: Deney onayı gerektirir
- Story metadata doğrulaması
- Experiment referansı kontrolü

### §8.2 Skill Uyumluluğu
| Skill | Mod | KÖPRÜ |
|-------|-----|-------|
| bmad-create-story | Mod C | #1 |
| bmad-dev-story | Mod A | #2 + #3 |
| bmad-code-review | Mod A | — |
| bmad-sprint-planning | Mod D | — |
| bmad-create-epics-and-stories | Mod C | — |

### §8.3 Kayıt Zinciri Uyumluluğu
```
E (Experiment) → IR (Implementation Readiness) → SP (Sprint Planning) → S (Story) → QR (Quality Record) → PR (Production Readiness)
```

Her aşama bir öncekinin çıktısına bağlıdır. Zincirin her halkası onay gerektirir.

**Not:** Implementation aşamasında her adımın ardından git commit yapılması zorunludur (§4.1.1). Commit olmadan Testing (§5) aşamasına geçilemez.

### §8.4 Kritik Kapı ve Kavramlar

| Kavram | Tanım | Detay |
|--------|-------|-------|
| **ONAYLANDI** | Experiment onay durumu | §3.4 - Story impl. prerequisite |
| **DENY** | Guard/stop hook engelleme kararı | Kod yazma veya oturum kapanışı engellenir |
| **Hipotez** | Deney onayı bekleyen AC | `[HYPOTHESIS]` etiketi, implemente edilemez |
| **QR** | Quality Record | `docs/quality/QR-XXX.md`, done sonrası zorunlu |
| **IR** | Implementation Readiness | `docs/development/IR-XXX.md`, Kapi 1 |
| **PR** | Production Readiness | `docs/development/PR-XXX.md`, Kapi 4 |

---

## §9 Oturum Kapanışı

Bir story tamamlandığında ve kod incelemesi onaylandığında oturum kapatılır. Bu işlem şu adımları içerir:
- Kalite Kaydı (QR) oluşturulur ve onaylanır (§7)
- Story durumu "done" olarak işaretlenir (§6.2)
- Gerekirse sprint durumu güncellenir (§2.1)

Oturum kapatılması, geliştirme döngüsünün son adımıdır ve bir sonraki story'ye geçiş için zorunludur.
