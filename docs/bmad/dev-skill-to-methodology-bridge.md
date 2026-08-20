# Dev Skill → Methodology Bridge

**Version:** 4.0.0
**Purpose:** Connect BMAD native story workflows to the research methodology's experiment-gated development model.

---

## §1 Genel Bağlam

Bu belge, `bmad-create-story` ve `bmad-dev-story` skill'lerinin araştırma metodolojisiyle nasıl entegre olduğunu tanımlar. Metodoloji zinciri:

```
Epic/Story → Experiment Record (E) → Story Implementation (S) → Quality Record (QR)
```

Her story, bir veya birden fazla onaylı deney kaydına bağlanmalıdır. Bağlantı kurulmayan story'ler "hypothesis" olarak işaretlenir — kod yazımı deney onayı gerektirir.

---

## §2 Acceptance Criteria Dinamik İşleme Kuralları

### §2.1 AC ↔ Experiment Bağlantısı

Her Acceptance Criterion'un bir deney kaydıyla ilişkilendirilmesi gerekir:

```yaml
# Story YAML frontmatter'da
experiment_refs:
  - id: E-001
    scope: "AC #1 ve #2 — kullanıcı kimlik doğrulama akışı"
    status: ONAYLANDI  # ONAYLANDI | BEKLİYOR | REDDEDİLDİ
  - id: E-002
    scope: "AC #3 — şifre sıfırlama"
    status: BEKLİYOR   # Bu AC henüz deney onayı almamış
```

**Kural:** `status: BEKLİYOR` veya `status: REDDEDİLDİ` olan AC'ler implemente edilemez. Story dosyasında bu AC'ler `[HYPOTHESIS]` olarak işaretlenir.

### §2.2 AC Metadata Slotları

Story template'inde her AC için aşağıdaki metadata alanları zorunludur:

```markdown
## Acceptance Criteria

1. [AC-001] **Given** ... **When** ... **Then** ...
   - Experiment: E-001
   - Type: agent-verifiable | user-evaluable | hybrid
   - Measured: true | false
   - Verify: curl | puppeteer | lighthouse | test | manual

2. [AC-002] **Given** ... **When** ... **Then** ... [HYPOTHESIS]
   - Experiment: — (deney onayı bekliyor)
   - Type: agent-verifiable
   - Measured: false
   - Verify: test
```

### §2.2a Technical Tasks ↔ AC Eşleştirme

Her Technical Task'ın bir AC'ye bağlı olması zorunludur:

```markdown
## Technical Tasks

- [ ] Task 1: API endpoint oluştur (AC: AC-001)
  - [ ] Subtask 1.1: Route tanımla
  - [ ] Subtask 1.2: Handler yaz
- [ ] Task 2: Validasyon ekle (AC: AC-001, AC-002)
  - [ ] Subtask 2.1: Input doğrulama
```

**Kural:** AC referansı olmayan task = validation uyarısı. Guard hook'u bu eşleştirmeyi doğrular.

### §2.2b Definition of Done ↔ AC Eşleştirme

Her DoD item'ı bir AC'ye bağlı olmalı ve doğrulama yöntemi tanımlı olmalıdır:

```markdown
## Definition of Done

- [ ] DoD-001: Tüm AC'ler karşılandı (AC: AC-001, AC-002)
  - Verify: curl + puppeteer
  - Evidence: test output
- [ ] DoD-002: Testler geçti (AC: AC-001)
  - Verify: pytest
  - Evidence: test output
```

### §2.3 Metodoloji Kaydı Oluşturma (KÖPRÜ #1)

`bmad-create-story` tamamlandığında:

1. Native story dosyası (`{implementation_artifacts}/<story-key>.md`) üretilir
2. `docs/development/stories/S-<sira>.md` metodoloji kaydı oluşturulur
3. Metodoloji kaydındaki alanlar:

```markdown
# Metodoloji Kaydı: S-<sira>

| Alan | Değer |
|------|-------|
| Tarih | YYYY-MM-DD |
| Durum | backlog \| sprint \| in-progress \| review \| done \| blocked |
| Story Başlığı | <story title> |
| Epic | <epic num> |
| Acceptance Criteria | <AC listesi —ettooling formatında> |
| Experiment Refs | <E-XXX listesi> |
| Dosya Listesi | <boş — implementasyon sonrası doldurulur> |
| Sprint Ref | <sprint-status.yaml referansı> |
| Native Story | <story dosya yolu> |
```

4. Native story dosyasına referans eklenir:
   ```
   <!-- Metodoloji kaydı: docs/development/stories/S-<sira>.md -->
   ```

### §2.4 Implementasyon Sonrası Güncelleme (KÖPRÜ #2)

`bmad-dev-story` tamamlandığında:

1. Metodoloji kaydının Durum alanı `in-progress` → `review` olarak güncellenir
2. Dev Agent Record bölümleri doldurulur:
   - **Debug Log**: Uygulanan düzeltmeler ve karşılaşılıan sorunlar
   - **Completion Notes**: Kısa özet
   - **File List**: Değiştirilen dosyalar (proje root'a görerel)
   - **Change Log**: Değişiklik özeti
3. Experiment Refs alanına deney sonuçları eklenir (varsa)
4. Native story dosyasındaki ilgili section da güncellenir

### §2.5 Quality Record (QR) Oluşturma (KÖPRÜ #3)

`bmad-dev-story` Step 9'da tüm DoD maddeleri doğrulandığında QR kaydı oluşturulur:

1. `docs/quality/QR-<sira>.md` dosyası oluşturulur
2. QR içeriği:

```markdown
# Quality Record: QR-<sira>

| Alan | Değer |
|------|-------|
| Story | <story_key> |
| Story File | <story dosya yolu> |
| Tarih | YYYY-MM-DD |
| QR Status | pass | fail | partial |

## DoD Doğrulama Sonuçları

| DoD Item | Durum | Kanit | Tarih |
|----------|-------|-------|-------|
| DoD-001 | ✅ passed | curl output | 2026-08-20 |
| DoD-002 | ✅ passed | pytest output | 2026-08-20 |
| DoD-003 | ❌ failed | test output | 2026-08-20 |

## AC Doğrulama Sonuçları

| AC | Durum | Method | Evidence |
|----|-------|--------|----------|
| AC-001 | ✅ verified | curl | response body |
| AC-002 | ⏳ pending | — | — |

## Test Özeti

- Unit tests: X passed, Y failed
- Integration tests: X passed, Y failed
- Regression: pass/fail

## Dosya Listesi

- file1.ts (new)
- file2.ts (modified)

## Değişiklik Özeti

<change log summary>
```

3. Story dosyasındaki Quality Record section güncellenir:
   - Her DoD item'ı ✅ veya ❌ olarak işaretlenir
   - QR Record Path alanı doldurulur
4. Kayıt zinciri tamamlanır: S → QR → PR

---

## §3 Guard Hook Entegrasyonu

### §3.1 Story-Experiment Eşleştirme Kontrolü

Guard hook'u kod yazma izni verirken sadece `docs/experiments/` kayıtlarına bakmaz — aynı zamanda story dosyasındaki AC'lerin deney bağlantısını doğrular:

1. **Hedef dosya bir story dosyasıysa** (`{implementation_artifacts}/*-*.md`):
   - YAML frontmatter'daki `experiment_refs` alanını okur
   - Her referansın `docs/experiments/` altında mevcut ve `ONAYLANDI` olduğunu doğrular
   - Eksik veya onaysız referans varsa DENY

2. **Hedef dosya bir kod dosyasıysa**:
   - Mevcut davranış korunur: `docs/experiments/` kaydı aranır
   - Ek olarak: Değiştirilen dosyanın ait olduğu story'nin AC'lerinin deney bağlantısı kontrol edilir (opsiyonel, hard gate değil)

### §3.2 AC Metadata Doğrulama

Guard hook'u story dosyası yazılırken AC metadata'sını doğrular:

- Her AC'de `[AC-XXX]` identifier var mı?
- Her AC'de `Experiment:` alanı dolu mu?
- Her AC'de `Type:` alanı tanımlı mı?
- Her AC'de `Measured:` alanı var mı?
- Her AC'de `Verify:` alanı var mı?
- Experiment=— olan AC'lerde `[HYPOTHESIS]` etiketi var mı?

Eksik metadata = DENY.

### §3.3 Task↔AC Eşleştirme Kontrolü

Guard hook'u Technical Tasks bölümünü doğrular:

- Her task'ta `AC: AC-XXX` referansı var mı?
- Referans verilen AC story'de tanımlı mı?

Eksik referans = DENY.

### §3.4 DoD Yapısal Kontrol

Guard hook'u Definition of Done bölümünü doğrular:

- Her DoD item'ında `[DoD-XXX]` identifier var mı?
- Her DoD item'ında `Verify:` alanı var mı?

Eksik identifier = DENY.

### §3.5 Hypothesis Koruması

`[HYPOTHESIS]` olarak işaretli AC'ler:
- Implemente edilemez (guard hook'u DENY)
- Story durumu `blocked` olarak güncellenir
- Kullanıcıya "Bu AC için deney onayı gerekli" mesajı gösterilir

### §3.6 Methodology Chain Validation (YENİ)

Guard hook'u story dosyası yazılırken methodology zincirini doğrular:

- **Status = done**: QR kaydı (docs/quality/QR-XXX.md) mevcut olmalı
- **Status = review/done**: Metodoloji kaydı (docs/development/stories/S-XXX.md) mevcut olmalı
- Eksik kayıt = DENY + "Run: python3 scripts/create-qr-record.py" veya "python3 scripts/create-methodology-record.py" mesajı

### §3.7 Programatik Zorlama Özeti

| Kontrol | Zorlama Türü | Hata Durumu |
|---------|-------------|-------------|
| Experiment onayı | Hard gate (DENY) | Kod yazılamaz |
| Experiment refs | Hard gate (DENY) | Story yazılamaz |
| AC metadata | Hard gate (DENY) | Story yazılamaz |
| Task↔AC | Hard gate (DENY) | Story yazılamaz |
| DoD identifier | Hard gate (DENY) | Story yazılamaz |
| Methodology chain | Hard gate (DENY) | Story yazılamaz |
| Methodology compliance | Soft (warning) | Audit log'a yazılır |

---

## §4 Dosya Yapısı

```
docs/
├── bmad/
│   ├── dev-skill-to-methodology-bridge.md  ← Bu belge (v4.0)
│   ├── research-methodology.md              ← Metodoloji manifestosu
│   └── development-methodology.md           ← Geliştirme metodolojisi
├── development/
│   ├── _template_S.md                       ← Metodoloji kayıt şablonu
│   └── stories/
│       ├── S-001.md                         ← Story metodoloji kayıtları
│       └── S-002.md
├── experiments/
│   ├── E-001.md                             ← Deney kayıtları
│   └── E-002.md
└── quality/
    └── QR-001.md                            ← Quality Record kayıtları

scripts/
├── check-methodology.sh                     ← Methodology chain validation
├── create-methodology-record.py             ← KÖPRÜ #1: S-XXX.md oluştur
├── create-qr-record.py                      ← KÖPRÜ #3: QR-XXX.md oluştur
└── run_experiment.py                        ← Deney onay sistemi
```

---

## §5 Kontrol Listesi

Story lifecycle'ında her adımda kontrol edilecekler:

- [ ] **Create Story**: AC'lerin her birinde `Experiment` alanı dolu mu?
- [ ] **Create Story**: AC'lerde `Type`, `Measured`, `Verify` alanları var mı?
- [ ] **Create Story**: `experiment_refs` frontmatter'da tanımlı mı?
- [ ] **Create Story**: Her task'ta `AC: AC-XXX` referansı var mı?
- [ ] **Create Story**: Her DoD item'ında `[DoD-XXX]` ve `Verify:` var mı?
- [ ] **Create Story**: Metodoloji kaydı (S-XXX) oluşturuldu mu?
- [ ] **Dev Story**: Implementasyon öncesi deney onayı doğrulandı mı?
- [ ] **Dev Story**: Hypothesis olarak işaretli AC'ler atlandı mı?
- [ ] **Dev Story**: Her AC'nin `Verify` yöntemi çalıştırıldı mı?
- [ ] **Dev Story**: Her DoD item'ı için kanıt toplandı mı?
- [ ] **Dev Story**: QR kaydı (QR-XXX) oluşturuldu mu?
- [ ] **Dev Story**: Tamamlanma sonrası metodoloji kaydı güncellendi mi?
- [ ] **Code Review**: AC'lerin deney sonuçlarıyla eşleşmesi doğrulandı mı?
- [ ] **Code Review**: AC metadata'sı (Experiment, Type, Measured) doğrulandı mı?
- [ ] **Code Review**: Task↔AC eşleştirmesi doğrulandı mı?
- [ ] **Code Review**: DoD maddelerinin kanıtları tam mı?

---

## §6 Uyumluluk

Bu belge aşağıdaki skill'lerle uyumludur:

| Skill | Uyumluluk | Not |
|-------|-----------|-----|
| bmad-create-story | ✅ KÖPRÜ #1 | Story oluşturma sırasında metodoloji kaydı |
| bmad-dev-story | ✅ KÖPRÜ #2 + #3 | Implementasyon sonrası güncelleme + QR oluşturma |
| bmad-create-epics-and-stories | ⚠️ Kısmi | AC formatı uyumlu ama experiment bağlama yok |
| bmad-code-review | ✅ | Acceptance Auditor AC metadata + Task↔AC + DoD kontrolü |
| guard hook | ✅ | Experiment + AC metadata + Task↔AC + DoD doğrulama |
| stop hook | ✅ | Story durumu kontrolü (in-progress = block) |
| audit hook | ✅ | Methodology compliance uyarıları |
| bmad-edit-prd | ❌ KALDIRILDI | DEPRECATED — bmad-prd'ye birleştirildi |
| bmad-testarch-atdd | ❌ Bağlantısız | Ayrı test workflow'u, AC'lerle bağlantılı değil |
