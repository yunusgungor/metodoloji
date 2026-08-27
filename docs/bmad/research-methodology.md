# Araştırma Metodolojisi Manifestosu

**Version:** 2.0.0
**Purpose:** BMAD (Behavior-Driven Methodology for AI Development) araştırma metodolojisinin temel kurallarını, modüler yapısını ve kapı kurallarını tanımlar.

---

## §1 Temel İlkeler

### §1.1 Kayıt Zinciri
Metodoloji zinciri şu sırayla ilerler:

```
Experiment (E) → Implementation Readiness (IR) → Sprint Planning (SP) → Story (S) → Quality Record (QR) → Production Readiness (PR)
```

Her aşama bir öncekinin çıktısına bağlıdır. Zincirin her halkası onay gerektirir.

> **Zorunlu kayıt zinciri kuralları:** IR olmadan Sprint Planning başlatılamaz; her onaylı geçiş git commit ile kalıcı kayıt altına alınır; story, QR ve PR çıktılarında Deney Onayı alanı zorunludur.

### §1.2 Temel Kural
> **Belgesel karar kod yazma izni değildir. Kod her durumda Mod A mekanik onayına bağlıdır.**

Bu kural tüm modlar için geçerlidir. PRD, mimari, UX tasarımı gibi belgesel çıktıları kod yazma izni vermez. Kod yazımı her zaman deney onayı gerektirir.

### §1.3 Gerçekleme Kuralı
> **Gerçekleme sayısal doğrulamayla gelir: tasarım özellik dönüşürse Mod A ölçümune bağlanır (D-id → E-id).**

Tasarım kararları özellik haline geldiğinde, deney ölçümüne bağlanmalıdır.

---

## §2 Mod Sistemi

### §2.1 Mod A — Kod (Implementation)
- **Kapsam:** Kod yazımı, test, deploy
- **Kapı:** Guard hook (PreToolUse) — onaylı deney kaydı gerektirir
- **Kanıt Türü:** Experiment record (E-XXX), test output, deployment log
- **Kayıt Formatı:** `docs/experiments/E-XXX.md`, story dosyası, QR kaydı
- **Koruma:** Guard hook kod yazmasını engeller (fail-closed)

### §2.2 Mod B — Çerçeveleme, Keşif, Sentez (Framing)
- **Kapsam:** Brainstorming, fikir üretimi, konsept geliştirme
- **Kapı:** Belgesel kalite kontrolü
- **Kanıt Türü:** Brainstorm output, concept brief
- **Kayıt Formatı:** Proje dosyaları, docs/ dizini
- **Koruma:** Yok (fail-open)

### §2.3 Mod C — İhtiyaç, PRD, Gereksinimler, UX, Mimari (Design)
- **Kapsam:** PRD, UX tasarımı, mimari kararlar, gereksinim analizi
- **Kapı:** Belgesel kalite kontrolü + implementasyon hazırlık kontrolü
- **Kanıt Türü:** PRD, architecture doc, UX spec, epics.md
- **Kayıt Formatı:** `docs/planning/` dizini
- **Koruma:** Yok (fail-open) — ama kod yazma izni vermez

### §2.4 Mod D — Sprint Yönetimi, Dokümantasyon (Management)
- **Kapsam:** Sprint planning, retrospektif, dokümantasyon
- **Kapı:** Belgesel kalite kontrolü
- **Kanıt Türü:** Sprint status, retrospective notes, documentation
- **Kayıt Formatı:** `sprint-status.yaml`, docs/ dizini
- **Koruma:** Yok (fail-open)

---

## §3 Kapı Kuralları (Gate Rules)

Her modun kapı kuralları, o modun çıktısının kalitesini ve uyumluluğunu belirler.

### §3.1 Mod A Kapı Kuralları
1. **Deney Onayı:** Kod yazmadan önce kapsamı eşleşen VERIFIED deney onayı gerekir
2. **Guard Hook:** PreToolUse hook'u kod yazmasını engeller (fail-closed)
3. **Stop Hook:** İncomplete story varsa session kapanışını engeller
4. **Story Metadata:** AC metadata tamlığı kontrolü (Experiment, Type, Measured, Verify)
5. **Task↔AC:** Her task'ın bir AC'ye bağlı olması zorunludur
6. **DoD:** Her DoD item'ının identifier ve verify alanı zorunludur

### §3.2 Mod B Kapı Kuralları
1. **Belgesel Çıktı:** Her çalışma bir çıktı üretmelidir
2. **Kanıt Formatı:** Çıktılar net ve doğrulanabilir olmalıdır
3. **Kayıt:** Çıktılar docs/ dizinine kaydedilmelidir

### §3.3 Mod C Kapı Kuralları
1. **Belgesel Tamliği:** PRD, mimari, UX spec tam olmalıdır
2. **Gereksinim Eşleştirme:** Her gereksinim bir story'ye bağlanmalıdır
3. **Kod Yazma İzni:** Belgesel karar kod yazma izni VERMEZ
4. **Mod A Bağlantısı:** Özellik dönüşümü Mod A ölçümüne bağlanır (D-id → E-id)

### §3.4 Mod D Kapı Kuralları
1. **Sprint Status:** sprint-status.yaml güncellenmiş olmalıdır
2. **Story Durumu:** Story'ler doğru sıralanmış olmalıdır
3. **Retrospektif:** Action items kaydedilmiş olmalıdır

---

## §4 Deney (Experiment) Kuralları

### §4.1 Deney Oluşturma
- Her deney `docs/experiments/E-XXX.md` dosyasında kayıtlı olmalıdır
- Deney kaydı şu alanları içermelidir (Türkçe etiketler zorunlu — kapı bu etiketleri ayrıştırır):
  - **Teori:** Hangi teoriden/çerçeveden geldiği
  - **Hipotez:** H-NNN: "metrik >= eşik" formatında test edilen varsayım
  - **Ölçüm metrikleri:** Metrik adı + eşik değeri
  - **Deney tasarımı:** Girdiler, prosedür, kontrol değişkenleri
  - **Kod kapsamı:** Onayın açtığı dosya glob'ları
  - **Durum:** planlandı → ONAYLANDI | REDDEDİLDİ (kapı yazar)

### §4.2 Deney Onayı
- Deney onayı `run_experiment.py --verify` ile doğrulanır
- Onaylı deney: `status: ONAYLANDI` ve HMAC imzası geçerli
- Onaysız deney: Kod yazımı engellenir (guard hook)

### §4.3 Hipotez (Hypothesis) Koruması
- Deney onayı olmayan AC'ler `[HYPOTHESIS]` olarak işaretlenir
- Hipotez AC'ler implemente edilemez
- Kullanıcıya "Bu AC için deney onayı gerekli" mesajı gösterilir

---

## §5 Story Kuralları

### §5.1 Story Oluşturma
- Her story bir deney kaydına bağlı olmalıdır
- Story dosyası `{implementation_artifacts}/<story-key>.md` konumunda olmalıdır
- Story metadata'sı zorunlu: Experiment, Type, Measured, Verify
- Her story kaydında `Deney Onayı` alanı zorunludur: E-id, status, doğrulama yöntemi, timestamp, git commit ref.

### §5.2 Story → Metodoloji Kaydı
- Story oluşturulduğunda `docs/development/stories/S-<sira>.md` kayıt dosyası da oluşturulur
- Metodoloji kaydı: Tarih, Durum, Story Başlığı, Epic, AC, Experiment Refs, Dosya Listesi

### §5.3 Story Durum Akışı
```
backlog → ready-for-dev → in-progress → review → done
```

### §5.4 Story Metadata Zorunlulukları
Her AC için:
- `[AC-XXX]` identifier
- `Experiment:` alanı (E-XXX veya —)
- `Type:` alanı (agent-verifiable | user-evaluable | hybrid)
- `Measured:` alanı (true | false)
- `Verify:` alanı (doğrulama yöntemi)

Her Task için:
- `(AC: AC-XXX)` referansı

Her DoD için:
- `[DoD-XXX]` identifier
- `Verify:` alanı

---

## §6 Quality Record (QR) Kuralları

### §6.1 QR Oluşturma
- **QR** zorunludur: story tamamlandığında `docs/quality/QR-<sira>.md` oluşturulur; QR onayı olmadan story `done` kabul edilemez
- QR: Her DoD item'ı için durum, kanıt ve tarih içerir
- QR, story dosyasındaki Quality Record section'ını günceller

### §6.2 QR Onayı
- QR onayı: Tüm DoD maddelerinin passed olması gerekir
- Kısmi onay: `status: partial` — eksik maddeler listelenir
- Red: `status: fail` — düzeltilmesi gereken maddeler listelenir

---

## §7 Production Readiness (PR) Kuralları

### §7.1 PR Oluşturma
- QR onayından sonra deploy hazırlığı yapılır
- PR kaydı `docs/development/PR-XXX.md` konumunda oluşturulur
- **PR Durum:** HAZIR | BEKLİYOR

### §7.2 PR Döngüsü
- BEKLİYOR → Hazırlıklar tamamlanır → HAZIR
- HAZIR → Deploy yapılır → Story `done` durumuna geçer

---

## §8 Guard Hook Kuralları

### §8.1 Kod Yazma Engeli (DENY)
- Kod yazma izni bulunmadığında guard hook sonucu **DENY** olur: onaysız deney, eksik story metadata veya Hipotez AC'si
- Onaysız deney kaydı olan dosyalara kod yazılamaz
- Story metadata'sı eksik olan dosyalar engellenir

### §8.2 Story Metadata Doğrulama
- AC metadata tamlığı kontrolü
- Task↔AC eşleşme kontrolü
- DoD yapısal kontrolü

### §8.3 Stop Hook
- İncomplete story varsa session kapanışı engellenir
- Onaysız kod değişiklikleri varsa session kapanışı engellenir

### §8.4 Audit Hook
- Tool kullanımı loglanır
- Methodology uyumluluğu kontrol edilir (uyarı seviyesinde)

---

## §9 Modül Haritası

| Mod | Kapsam | Kapı | Koruma | Kanıt Türü |
|-----|--------|------|--------|------------|
| Mod A | Kod | Guard hook | fail-closed | E-XXX, test, deploy |
| Mod B | Çerçeveleme | Belgesel kalite | fail-open | Brainstorm, concept |
| Mod C | PRD/UX/Mimari | Belgesel tamlik | fail-open | PRD, arch, UX spec |
| Mod D | Sprint/Doküman | Belgesel kalite | fail-open | Sprint status, retro |

---

## §10 Uyumluluk

Bu metodoloji aşağıdaki bileşenlerle uyumludur:

| Bileşen | Durum | Mod |
|---------|-------|-----|
| guard hook | ✅ Aktif | Mod A |
| audit hook | ✅ Aktif | Tüm modlar |
| stop hook | ✅ Aktif | Mod A |
| bmad-agent-dev | ✅ Mod A | Kod |
| bmad-create-story | ✅ Mod C | Story oluşturma |
| bmad-dev-story | ✅ Mod A | Story gerçekleştirme |
| bmad-code-review | ✅ Mod A | Değişiklik denetimi |
| bmad-sprint-planning | ✅ Mod D | Sprint yönetimi |
| bmad-create-epics-and-stories | ✅ Mod C | Epik/story ayrıştırma |
| bridge doc | ✅ v3.0 | Köprü belgesi |

---

## §11 Zorunlu Denetim ve Kayıt Kuralları

### §11.1 Zorunlu Terimler
- **onaylı deney**: yalnızca `status: ONAYLANDI` ve HMAC imzası geçerli deney; yoksa kod yazma **DENY** edilir.
- **Hipotez**: deney onayı bekleyen AC. `[HYPOTHESIS]` etiketiyle işaretlenir, implemente edilemez.
- **DENY**: guard/stop hook'un engelleme kararı. Kod yazma veya oturum kapanışı engellenir.
- **QR (Quality Record)**: `docs/quality/QR-<sira>.md` — story tamamlandığında zorunlu. QR onayı olmadan `done` kabul edilmez.
- **IR (Implementation Readiness)**: `docs/development/IR-<sira>.md` — Kapi 1. Sprint Planning öncesi zorunlu.
- **PR (Production Readiness)**: `docs/development/PR-<sira>.md` — Kapi 4. Deploy öncesi zorunlu.

### §11.2 Zorunlu Kayıt Yolları
| Kayıt | Yol | Geçerli Durum Değerleri |
|-------|-----|------------------------|
| Deney (E) | `docs/experiments/E-XXX.md` | planlandı → ONAYLANDI \| REDDEDİLDİ |
| IR | `docs/development/IR-XXX.md` | HAZIR \| EKSİK |
| SP | `docs/development/SP-XXX.md` | planlandı \| devam ediyor \| tamamlandı \| iptal |
| Story (S) | `docs/development/stories/S-XXX.md` | backlog \| sprint \| in-progress \| review \| done \| blocked |
| QR | `docs/quality/QR-XXX.md` | ONAYLANDI \| REDDEDİLDİ \| REVİZE |
| PR | `docs/development/PR-XXX.md` | HAZIR \| BEKLİYOR |
