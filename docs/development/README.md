# Geliştirme Kanadı Kayıtları

Bu klasör, BMAD metodolojisinin **geliştirme kanadı** kayıtlarını içerir. Araştırma kanadı "ne yapmalı, neden, nasıl doğrularız" sorularını yanıtlarken; geliştirme kanadı "bunu nasıl üretime taşırız" sorusunu yanıtlar.

## Klasör Yapısı

```
docs/development/
├── README.md                    (bu dosya)
├── tech-debt.md                 (teknik borç takibi)
│
├── _template_IR.md              (Implementation Readiness template)
├── _template_SP.md              (Sprint template)
├── _template_QR.md              (Quality Review template)
├── _template_PR.md              (Production Readiness template)
│
├── IR-001.md, IR-002.md, ...   (Implementation Readiness kayıtları)
├── SP-001.md, SP-002.md, ...   (Sprint kayıtları)
├── QR-001.md, QR-002.md, ...   (Quality Review kayıtları)
├── PR-001.md, PR-002.md, ...   (Production Readiness kayıtları)
│
├── stories/
│   ├── _template_S.md           (Story template)
│   └── S-001.md, S-002.md, ...  (Story kayıtları)
│
└── incidents/
    ├── _template_PM.md          (Post-Mortem template)
    └── PM-001.md, PM-002.md, ... (Post-Mortem kayıtları)
```

---

## Kayıt Tipleri ve Kullanımları

### 1. Implementation Readiness (IR-id)

**Ne zaman:** Araştırmadan gelen bulguları geliştirmeye geçirmeden önce  
**Amaç:** Geliştirmeye başlamak için tüm girdilerin hazır olduğunu garanti etmek  
**Kapı:** Kapı 1 (Hazırlık Kontrolü)

**Yeni kayıt oluşturma:**
```bash
# Template'i kopyala
cp _template_IR.md IR-001.md

# İçeriği doldur
# - Araştırma girdilerini listele (E/R/D/C-id'ler)
# - Tasarım belgelerini referans et
# - Başarı kriterlerini tanımla
# - Teknik bağımlılıkları belirle
# - Risk değerlendirmesi yap
```

**Checklist:** Template içinde detaylı checklist var

---

### 2. Sprint (SP-id)

**Ne zaman:** Her sprint başlangıcında  
**Amaç:** Sprint kapsamını net, ölçülebilir ve gerçekçi şekilde tanımlamak  
**Kapı:** Kapı 2 (Kapsam Onayı)

**Yeni kayıt oluşturma:**
```bash
cp _template_SP.md SP-001.md

# İçeriği doldur
# - Sprint hedefini tanımla (tek cümle)
# - Story'leri listele (S-id + öncelik + points)
# - Kapasiteyi kontrol et (velocity'ye göre)
# - Teknik borç için time-box ayır
# - Blokerleri ve bağımlılıkları belirle
```

**Sprint boyunca:** Günlük notlar eklenebilir (opsiyonel)  
**Sprint sonunda:** Review ve retrospective bölümlerini doldur

---

### 3. Story (S-id)

**Ne zaman:** Sprint planlama sırasında  
**Amaç:** Uygulamaya hazır, net acceptance criteria'lı iş birimi tanımlamak  
**Format:** User story (As a ... I want ... So that ...)

**Yeni kayıt oluşturma:**
```bash
cd stories/
cp _template_S.md S-001.md

# İçeriği doldur
# - User story cümlesini yaz
# - Acceptance criteria tanımla (Given/When/Then)
# - Technical task'lara böl
# - Definition of done'ı kontrol et
```

**Story durumları:**
- `backlog` → `sprint` → `in-progress` → `review` → `done`
- Blocked olursa: durumu güncelle, bloker notuna ekle

---

### 4. Quality Review (QR-id)

**Ne zaman:** Her PR/MR için, merge'den önce  
**Amaç:** Kod kalite standartlarını zorlamak  
**Kapı:** Kapı 3 (Kalite Kapısı)

**Yeni kayıt oluşturma:**
```bash
cp _template_QR.md QR-001.md

# Otomatik kontroller bölümünü doldur
# - Test coverage
# - Test sonuçları
# - Linter/formatter
# - Security scan
# - Performance regression

# Manuel kontroller bölümünü doldur
# - Code review feedback
# - Dokümantasyon durumu
# - Breaking changes
# - Teknik borç
```

**Merge kriteri:** Tüm mekanik kontroller PASS + en az bir code review APPROVED

---

### 5. Production Readiness (PR-id)

**Ne zaman:** Production deploy'dan önce  
**Amaç:** Operasyonel hazırlığı ve rollback planını garanti etmek  
**Kapı:** Kapı 4 (Üretim Hazırlığı)

**Yeni kayıt oluşturma:**
```bash
cp _template_PR.md PR-001.md

# İçeriği doldur
# - Release kapsamını listele (QR-id'ler)
# - Staging test sonuçlarını kaydet
# - Rollback planını detaylandır
# - Monitoring ve alerting'i doğrula
# - Feature flag planı yap
# - Runbook'u hazırla
# - Incident response planı tanımla
```

**Deploy sonrası:** "Deploy Sonucu" bölümünü doldur (metrics, incident varsa PM-id)

---

### 6. Post-Mortem (PM-id)

**Ne zaman:** Her SEV1/SEV2 production incident'tan sonra  
**Amaç:** Öğrenme ve iyileştirme (suçlama değil)  
**Zorunluluk:** SEV1/SEV2 için zorunlu, SEV3 için opsiyonel

**Yeni kayıt oluşturma:**
```bash
cd incidents/
cp _template_PM.md PM-001.md

# İçeriği doldur (24-48 saat içinde)
# - Özet (executive summary)
# - Timeline (tüm zamanlar UTC)
# - Impact (kullanıcı, business, teknik)
# - Root cause (5 Whys)
# - Detection ve response analizi
# - Lessons learned
# - Action items (sahibi, deadline, durum)
```

**Blameless culture:** Amaç suçlu bulmak değil, sistemi iyileştirmektir

---

### 7. Teknik Borç (tech-debt.md)

**Ne zaman:** Her QR'da kontrol edilir, borç varsa eklenir  
**Amaç:** Teknik borçları şeffaf takip etmek ve geri ödeme planı yapmak  
**Format:** Tablo + kategoriler + metrikler

**Borç ekleme:**
1. QR sırasında tespit edildi
2. `tech-debt.md` dosyasına yeni satır ekle
3. TODO comment ekle: `// TODO: [TD-XXX] açıklama`
4. Öncelik belirle (P0/P1/P2/P3)
5. Hedef sprint belirle (P0/P1 için zorunlu)

**Borç ödeme:**
1. Borç çözüldü
2. "Aktif Borçlar" tablosundan "Ödenmiş Borçlar" tablosuna taşı
3. Çözüm detayını, sprint'i, QR-id'yi kaydet
4. TODO comment'i sil

---

## Geliştirme Akışı

### Akış 1: Araştırmadan Geliştirmeye

```
1. Araştırma bulgusu onaylandı (E/R/D/C-id)
   ↓
2. Implementation Readiness (IR-id) — Kapı 1
   ↓
3. Sprint Planlama (SP-id) — Kapı 2
   ↓
4. Story'leri uygula (S-id)
   ↓
5. Quality Review (QR-id) — Kapı 3
   ↓
6. Production Readiness (PR-id) — Kapı 4
   ↓
7. Deploy → Monitoring → (Incident varsa PM-id)
```

### Akış 2: Geliştirmeden Araştırmaya Dönüş

```
1. İmplementasyon sırasında soru çıktı
   ↓
2. Soruyu formüle et (yeni araştırma sorusu)
   ↓
3. Uygun modu seç (A/B/C/D)
   ↓
4. Araştırma kaydı aç (E/R/D/C-id)
   ↓
5. Onaylandıktan sonra geliştirmeye dön
```

---

## Kayıt Zincirleme Örnekleri

### Örnek 1: Özellik Geliştirme
```
E-045 (BFS optimizasyonu onaylandı)
  → IR-012 (implementation readiness: HAZIR)
    → SP-003 (Sprint 3 planlandı)
      → S-027 (Story: BFS implementasyonu)
        → QR-028 (code review: ONAYLANDI)
          → PR-007 (production readiness: HAZIR)
            → Deploy başarılı
```

### Örnek 2: Incident ve İyileştirme
```
PR-007 (deploy edildi)
  → PM-003 (incident: memory leak)
    → TD-042 (teknik borç: memory profiling eksik)
      → SP-004 (sonraki sprint: borç ödeme)
        → S-031 (Story: memory profiling ekle)
          → QR-032 (review: ONAYLANDI)
            → TD-042 (borç ödendi)
```

### Örnek 3: Araştırma → Geliştirme → Araştırma Döngüsü
```
D-023 (tasarım: yeni onboarding akışı)
  → IR-015 (readiness: HAZIR)
    → SP-005 (Sprint 5)
      → S-035 (Story: onboarding UI)
        → Kullanıcı testi: akış anlaşılmıyor
          → B-024 (nitel araştırma: kullanıcı feedback)
            → D-025 (tasarım revizyonu)
              → IR-016 (yeni readiness)
                → Devam...
```

---

## En İyi Pratikler

### 1. Kayıt Disiplini
- Her karar/çıktı kayda bağlanır
- Kayıtsız iddia olmaz
- Template'leri takip et, özel alan ekleme

### 2. Dürüstlük
- Test sonuçlarını çarpıtma
- Teknik borcu gizleme
- Incident'ları raporla
- Rollback'e açık ol

### 3. İterasyon
- Gerektiğinde önceki aşamaya dön
- Geliştirmede soru çıkarsa araştırmaya dön
- Sprint retrospective'i ciddiye al

### 4. Kalite Standartları
- Test coverage >= %80
- Code review zorunlu
- Security scan clean
- Dokümantasyon güncel

### 5. Şeffaflık
- Teknik borç görünür
- Incident post-mortem paylaşımlı
- Metrikler takip edilir
- Blokerler hemen iletilir

---

## İlgili Dökümanlar

- [Geliştirme Metodolojisi](../bmad/development-methodology.md) — Geliştirme kanadı manifestosu
- [Araştırma Metodolojisi](../bmad/research-methodology.md) — Araştırma kanadı manifestosu
- [Proje Bağlamı](../project-context.md) — İki kanat yapısı ve entegrasyon
- [Kullanım Klavuzu](../bmad/usage-guide.md) — Her iki kanadı nasıl kullanacağın

---

## Sorular ve Yardım

- Hangi template'i kullanacağını bilmiyor musun? Yukarıdaki "Ne zaman" bölümlerine bak
- Template eksik mi? [Geliştirme Metodolojisi](../bmad/development-methodology.md) §3'te format detayları var
- Araştırma ↔ Geliştirme geçişi nasıl? [Geliştirme Metodolojisi](../bmad/development-methodology.md) §4'te köprü mekanizması açıklanmış
- Teknik borç nasıl yönetilir? `tech-debt.md` dosyasındaki rehberi oku
