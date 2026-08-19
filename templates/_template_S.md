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

- [ ] **Given** [başlangıç durumu] **When** [aksiyon] **Then** [beklenen sonuç]
- [ ] **Given** [başlangıç durumu] **When** [aksiyon] **Then** [beklenen sonuç]
- [ ] **Given** [başlangıç durumu] **When** [aksiyon] **Then** [beklenen sonuç]

### Örnek
- [ ] **Given** ben admin panelindeyim **When** "son 7 gün" filtresini seçersem **Then** yalnızca son 7 günün loglarını görürüm
- [ ] **Given** log listesi yüklüyken **When** filtreyi değiştirirsem **Then** loading spinner görürüm
- [ ] **Given** hiç log yoksa **When** sayfayı yüklersem **Then** "Log bulunamadı" mesajı görürüm

---

## Technical Tasks

> Story'yi tamamlamak için gereken teknik adımlar

- [ ] [Task 1: API endpoint implementasyonu] — [@username]
- [ ] [Task 2: Frontend component] — [@username]
- [ ] [Task 3: Database migration] — [@username]
- [ ] [Task 4: Unit tests] — [@username]
- [ ] [Task 5: Integration tests] — [@username]
- [ ] [Task 6: Dokümantasyon] — [@username]

---

## Definition of Done

> Story'nin gerçekten bitmiş sayılması için genel kriterler

- [ ] Tüm acceptance criteria karşılandı
- [ ] Code review yapıldı ve onaylandı (QR-xxx)
- [ ] Unit test coverage >= %80
- [ ] Integration test yazıldı ve geçti
- [ ] Dokümantasyon güncellendi
- [ ] Staging'de test edildi
- [ ] Product owner kabul etti

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
