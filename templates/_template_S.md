# Story: S-XXX — [Story Başlığı]

> Bu template, User Story (S) kayıtları için kullanılır.
> Story, sprint planlama sırasında oluşturulur ve implementasyon boyunca takip edilir.

## Story: S-XXX — [Story başlığı]

- **Tarih:** [YYYY-MM-DD]
- **Durum:** backlog | sprint | in-progress | review | done | blocked
- **Sprint:** [SP-id referansı, örn. SP-003]
- **Öncelik:** Kritik / Yüksek / Orta / Düşük
- **Story points:** [X points]
- **Atanan:** [@username]
- **Epic:** [Epic-id veya "standalone"]

---

## User Story

**As a** [kullanıcı rolü]  
**I want** [ne yapabilmek isterim]  
**So that** [amacım/değerim ne]

### Örnek
**As a** sistem yöneticisi  
**I want** kullanıcı aktivitelerini filtreleyebilmek  
**So that** sorunlu davranışları hızlıca tespit edebilirim

---

## Acceptance Criteria

> Story'nin "done" sayılması için tüm kriterler karşılanmalı

- [AC-001] **Given** [başlangıç durumu] **When** [aksiyon] **Then** [beklenen sonuç]
  - Experiment: E-XXX
  - Type: agent-verifiable | manual
  - Measured: true | false
  - Verify: [test komutu]
- [AC-002] **Given** [başlangıç durumu] **When** [aksiyon] **Then** [beklenen sonuç]
  - Experiment: E-XXX
  - Type: agent-verifiable | manual
  - Measured: true | false
  - Verify: [test komutu]
- [AC-003] **Given** [başlangıç durumu] **When** [aksiyon] **Then** [beklenen sonuç]
  - Experiment: E-XXX
  - Type: agent-verifiable | manual
  - Measured: true | false
  - Verify: [test komutu]

### Örnek
- [AC-001] **Given** ben admin panelindeyim **When** "son 7 gün" filtresini seçersem **Then** yalnızca son 7 günün loglarını görürüm
  - Experiment: E-001
  - Type: agent-verifiable
  - Measured: true
  - Verify: curl http://localhost:8000/api/logs?days=7
- [AC-002] **Given** log listesi yüklüyken **When** filtreyi değiştirirsem **Then** loading spinner görürüm
  - Experiment: E-001
  - Type: agent-verifiable
  - Measured: true
  - Verify: check_ui_spinner.py
- [AC-003] **Given** hiç log yoksa **When** sayfayı yüklersem **Then** "Log bulunamadı" mesajı görürüm
  - Experiment: E-001
  - Type: agent-verifiable
  - Measured: true
  - Verify: check_empty_state.py

---

## Technical Tasks

> Story'yi tamamlamak için gereken teknik adımlar

- [ ] Task 1: API endpoint implementasyonu (AC: AC-001) — [@username]
- [ ] Task 2: Frontend component (AC: AC-002, AC-003) — [@username]
- [ ] Task 3: Database migration (AC: AC-001) — [@username]
- [ ] Task 4: Unit tests (AC: AC-001, AC-002, AC-003) — [@username]
- [ ] Task 5: Integration tests (AC: AC-001) — [@username]
- [ ] Task 6: Dokümantasyon — [@username]

---

## Definition of Done

> Story'nin gerçekten bitmiş sayılması için genel kriterler

- [DoD-001] Tüm acceptance criteria karşılandı (AC: AC-001, AC-002, AC-003)
  - Verify: pytest tests/
  - Evidence: test output
- [DoD-002] Code review yapıldı ve onaylandı
  - Verify: QR-001 record exists
  - Evidence: QR record
- [DoD-003] Unit test coverage >= %80
  - Verify: coverage report
  - Evidence: coverage output
- [DoD-004] Integration test yazıldı ve geçti
  - Verify: pytest tests/integration/
  - Evidence: test output
- [DoD-005] Dokümantasyon güncellendi
  - Verify: docs/ updated
  - Evidence: git diff
- [DoD-006] Staging'de test edildi
  - Verify: manual test
  - Evidence: test results
- [DoD-007] Product owner kabul etti
  - Verify: PO sign-off
  - Evidence: approval message

---

## Bağımlılıklar

- **Bu story'ye bağımlı:** [Diğer S-id'ler — bu bitmeden başlayamazlar]
- **Bu story bağımlı:** [Diğer S-id'ler — bunlar bitmeden başlayamaz]
- **API bağımlılığı:** [Hangi API'ler gerekli, hazır mı]
- **Altyapı bağımlılığı:** [Database, queue vs.]

---

## Design / UX

- **Mockup:** [Figma/Sketch link veya dosya]
- **UX flow:** [Kullanıcı akış diyagramı]
- **Design review:** ✓ Yapıldı / ✗ Gerekmiyor / ⚠ Bekliyor

---

## Notlar / İzleme

### Blokerler
- [YYYY-MM-DD]: [Bloker tanımı] → Sahibi: [kim] → Durum: [açık/çözüldü]

### İlerleme Güncellemeleri
- [YYYY-MM-DD]: [Günceleme notu, örn. "API tamamlandı, frontend başladı"]
- [YYYY-MM-DD]: [Günceleme notu]

### Kararlar
- [YYYY-MM-DD]: [Alınan teknik/tasarım kararı ve gerekçesi]

---

## Test Stratejisi

### Unit Tests
- [Hangi modüller/fonksiyonlar test edilecek]
- [Test coverage hedefi: %X]

### Integration Tests
- [Hangi entegrasyon noktaları test edilecek]
- [API endpoint tests, database tests]

### Manual Tests
- [Manuel test senaryoları — QA için]

---

## Araştırma Girdileri

> Bu story hangi araştırma bulgularına dayanıyor

- [E-id / R-id / D-id / C-id referansları]
- Örnek: E-045 (performans optimizasyonu onayı), D-012 (kullanıcı akış tasarımı)

---

## Tamamlama

- **Tamamlanma tarihi:** [YYYY-MM-DD]
- **PR/MR:** [Pull request link]
- **QR kaydı:** [QR-id referansı]
- **Demo:** [Demo link/video veya "yapıldı"]
- **Retrospective notları:** [Bu story'den öğrenilen dersler]
