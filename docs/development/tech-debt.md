# Teknik Borç Takibi

> Bu dosya, projede birikmiş teknik borçları ve geri ödeme planını takip eder.
> Her sprint'te teknik borç için time-box ayrılmalıdır.

**Son güncelleme:** 2026-08-26

> **2026-08-26 — SkillOpt-tech-debt entegrasyonu tamamlandı.** 12 commit (957e5c2..8f2eb93) ile
> tüm 6 manifestodaki borç ödendi (TD-001/002/003/010/011/012), SkillOpt `techdebt` task
> kategorisi eklendi (6/6 benchmark), `commands/check-techdebt.sh` envanteri 5 bölümde
> mekanik denetliyor, baseline.json repoda (66/66), 151 test PASS, 3/3 negtest. Aktif
> borç: **0**. Bir sonraki borç döngüsü yeni P3 kayıtlarıyla başlayacak.

---

## Aktif Teknik Borçlar

### Kritik Öncelik (P0)

| ID | Tanım | Neden Eklendi | Ekleme Tarihi | Etki | Sahibi | Hedef Sprint |
|----|-------|---------------|---------------|------|--------|--------------|
| —    | —     | —             | —             | —    | —      | —            |

### Yüksek Öncelik (P1)

| ID | Tanım | Neden Eklendi | Ekleme Tarihi | Etki | Sahibi | Hedef Sprint |
|----|-------|---------------|---------------|------|--------|--------------|
| —    | —     | —             | —             | —    | —      | —            |

### Orta Öncelik (P2)

| ID | Tanım | Neden Eklendi | Ekleme Tarihi | Etki | Sahibi | Hedef Sprint |
|----|-------|---------------|---------------|------|--------|--------------|
| —    | —     | —             | —             | —    | —      | —            |

### Düşük Öncelik (P3)

| ID | Tanım | Neden Eklendi | Ekleme Tarihi | Etki | Sahibi | Hedef Sprint |
|----|-------|---------------|---------------|------|--------|--------------|
| — | — | — | — | — | — | — |

---

## Ödenmiş Borçlar (Tamamlanan)

| ID | Tanım | Çözüm | Tamamlanma Tarihi | Sprint | PR/QR |
|----|-------|-------|-------------------|--------|-------|
| TD-001 | Kırık test olarak işaretlenen `test_marketplace_json_content` (bmad-module-builder) — manifestoda P0 olarak duruyordu | 2026-08-26'da pytest ile doğrulandı: 9/9 test-scaffold-standalone-module + 7/7 test-scaffold-setup-skill + 21/21 test-validate-module (toplam 37/37) PASS. Scaffold `marketplace_name = f"bmad-{args.module_code}"` üretiyor, test `bmad-exc` bekliyor — uyumlu. Borç kaydı eski (2026-08-19) ve initial commit'ten beri scaffold doğru çalışıyordu; kayıt hatalı güncellenmiş | 2026-08-26 | — | 1fcc9fd |
| TD-003 | Diğer yüklenmiş skill'lerin test süitleri (bmad-workflow-builder hariç) hiç koşulmamış | 2026-08-26'da pytest ile doğrulandı — 9 test dosyası, **114/114 PASS**: bmad-architecture (28) + bmad-brainstorming (27) + bmad-customize (13) + bmad-eval-runner (4+11=15) + bmad-forge-idea (16) + bmad-workflow-builder (2+7+6=15). Tüm aktif skill testleri deterministik ve yeşil | 2026-08-26 | — | 1fcc9fd |
| TD-002 | Monitör false-positive: `tech-debt.md` şablon placeholder'ları gerçek borç sanılıyordu (`sprint-status.sh`/`tech-debt-monitor.sh` "4 aktif borç, P0:1" gösteriyordu) | `commands/check-techdebt.sh` 5 bölüm: (1) şablon/canlı özdeşlik, (2) aktif ID benzersiz + sıralı, (3) P0 hard limit (<=5), (4) aktif/ödenmiş çakışma yok, (5) orphan TODO; 3 aşamalı `--negtest`; `check-plugin.sh §6b` olarak entegre | 2026-08-26 | — | 1de54b1 |
| TD-010 | Tüm Python script'lerinde Windows UTF-8 bozulması (cp1254) | `subprocess.run(..., text=True)` çağrılarına `encoding="utf-8", errors="replace"` eklendi (14 dosya, 19 çağrı) | 2026-08-19 | — | — |
| TD-011 | `check-methodology.sh` §2b köprü denetimi false-positive (KÖPRÜ merge "yok" sanılıyordu) | §2b subprocess'ine `encoding="utf-8"` eklendi; `DURUM: SAĞLIKLI` | 2026-08-19 | — | — |
| TD-012 | SkillOpt API anahtarı kaynak kodunda hard-coded (`sk-*` setdefault fallback'leri) — güvenlik borcu + deterministik eğitimi bozuyor | 4 adım: (1) `.env.example` şablonu + `.gitignore` `.env` koruması, (2) `optimization/train.py` + `cli.py` + `envs/bmad/adapter.py` setdefault fallback'leri kaldırıldı, (3) `train._require_llm_env()` ile `--benchmark` dışı yollarda eksik env hata verir, (4) `check-plugin.sh §6a` 4 alt-kontrol + 3 aşamalı `--negtest` eklendi | 2026-08-26 | — | cf679ea |

---

## Teknik Borç Kategorileri

### 1. Code Quality
- **Tanım:** Kötü yazılmış kod, code smell'ler, duplicate kod
- **Örnekler:**
  - Kompleks fonksiyonlar (cyclomatic complexity yüksek)
  - Dead code (kullanılmayan fonksiyonlar/sınıflar)
  - Magic numbers (hardcoded sabitler)
  - God object'ler (çok fazla sorumluluk)

### 2. Test Debt
- **Tanım:** Eksik testler, flaky testler, düşük coverage
- **Örnekler:**
  - Unit test coverage < %80
  - Integration test eksikliği
  - E2E test coverage yetersiz
  - Flaky testler (intermittent failures)

### 3. Documentation Debt
- **Tanım:** Eksik veya güncel olmayan dokümantasyon
- **Örnekler:**
  - API dokümantasyonu eksik
  - Code comment'ler yetersiz
  - README güncel değil
  - Runbook eksik veya eski

### 4. Architecture Debt
- **Tanım:** Mimari kararlar, tight coupling, scalability sorunları
- **Örnekler:**
  - Monolith'ten microservice'e geçiş gerekli
  - Tight coupling (bağımlılıklar çok fazla)
  - Database schema normalizasyon sorunu
  - Scalability bottleneck'leri

### 5. Infrastructure Debt
- **Tanım:** Altyapı, deployment, monitoring eksiklikleri
- **Örnekler:**
  - Manual deployment adımları (otomasyon eksik)
  - Monitoring yetersiz
  - Log aggregation eksik
  - Disaster recovery planı yok

### 6. Dependency Debt
- **Tanım:** Eski bağımlılıklar, security vulnerability'ler
- **Örnekler:**
  - Deprecated kütüphaneler
  - Bilinen güvenlik açıkları
  - End-of-life teknolojiler

### 7. Performance Debt
- **Tanım:** Performans optimizasyonları, memory leak'ler
- **Örnekler:**
  - N+1 query problemi
  - Memory leak
  - Inefficient algorithm (O(n²) → O(n log n))
  - Caching eksikliği

---

## Teknik Borç Metrikleri

### Mevcut Durum
- **Toplam aktif borç:** [X item]
  - P0 (Kritik): [Y item]
  - P1 (Yüksek): [Z item]
  - P2 (Orta): [W item]
  - P3 (Düşük): [V item]
- **Tahmini geri ödeme süresi:** [X sprint / Y hafta]

### Sprint Allocation
- **Sprint başına teknik borç time-box:** [%20 veya X story points]
- **Son 3 sprint'te ödenen borç:** [X item]
- **Son 3 sprint'te eklenen borç:** [Y item]
- **Net borç değişimi:** [X - Y = Z] (pozitif = borç azalıyor, negatif = borç artıyor)

### Trend
```
Sprint    | Yeni Borç | Ödenen Borç | Net Değişim | Toplam Borç
----------|-----------|-------------|-------------|-------------
SP-001    | 5         | 2           | -3          | 15
SP-002    | 3         | 4           | +1          | 14
SP-003    | 2         | 3           | +1          | 13
```

---

## Geri Ödeme Stratejisi

### Prensip: Boy Scout Rule
> "Kodu bulduğundan daha temiz bırak." Her PR'da küçük iyileştirmeler yaparak borcu azalt.

### Time-Box Allocation
- **Her sprint:** %20 kapasiteyi teknik borç için ayır
- **Kritik borç (P0):** Acil sprint'e al, feature'dan önce
- **Yüksek borç (P1):** Önümüzdeki 2 sprint içinde planla
- **Orta/Düşük borç (P2/P3):** Opportunistic olarak ele al (refactoring sırasında)

### Borç Önceliklendirme Kriterleri
1. **Güvenlik riski:** Güvenlik açığı varsa P0
2. **Production incident riski:** Incident çıkarabilirse P0/P1
3. **Geliştirme hızı etkisi:** Yeni feature geliştirmeyi yavaşlatıyorsa P1
4. **Bakım maliyeti:** Sürekli bug üretiyorsa P1
5. **Code smell:** Sadece kötü kod ise P2/P3

---

## Borç Ekleme Kuralları

### Borç Eklenebilir Mi?
- ✓ **Evet:** Hızlı deliver etmek için geçici kestirme alındıysa (bilinçli karar)
- ✓ **Evet:** Test coverage geçici olarak düşürüldüyse (geri ödeme planıyla)
- ✗ **Hayır:** "Daha sonra düzeltiriz" diye kalitesiz kod yazılırsa (kabul edilemez)
- ✗ **Hayır:** Borç kaydedilmeden bırakılırsa (gizli borç yasaktır)

### Borç Ekleme Süreci
1. QR (Quality Review) sırasında tespit edildi
2. `tech-debt.md` dosyasına eklendi (ID, tanım, gerekçe, öncelik)
3. Code'da `// TODO: [TD-XXX] ...` comment eklendi
4. Hedef sprint belirlendi (P0/P1 için zorunlu)

### Borç Limiti
- **Hard limit:** P0 borç sayısı > 5 ise yeni feature alınmaz, önce borç ödenir
- **Soft limit:** Toplam aktif borç > 30 ise borç ödeme sprint'i düzenlenir

---

## TODO Comment Standardı

```python
# TODO: [TD-XXX] <Kısa açıklama>
# Detay: <Neyi düzeltmek gerekiyor>
# Ekleme: <YYYY-MM-DD> - <@username>
```

**Örnek:**
```python
# TODO: [TD-042] BFS algorithm'i O(n²), O(n log n)'e optimize edilmeli
# Detay: Nested loop yerine heap kullanarak priority queue implementasyonu
# Ekleme: 2026-08-15 - @ahmet
def bfs(graph):
    # Geçici implementation
    pass
```

---

## Gözden Geçirme

### Haftalık Review
- **Sahibi:** Tech Lead
- **Ne:** Yeni eklenen borçlar review edilir, öncelik güncellenir
- **Aksiyon:** Kritik borçlar sprint'e alınır

### Aylık Health Check
- **Sahibi:** Takım + Engineering Manager
- **Ne:** Teknik borç metrikleri gözden geçirilir, trend analizi yapılır
- **Aksiyon:** Borç ödeme stratejisi ayarlanır

### Quarterly Audit
- **Sahibi:** Tüm mühendislik organizasyonu
- **Ne:** Tüm teknik borçlar audit edilir, hangileri hâlâ geçerli
- **Aksiyon:** Eski/irrelevant borçlar silinir, yenileri eklenir

---

## Notlar

- Teknik borç **gizlenemez** (geliştirme dürüstlük kuralı 3)
- Her QR'da teknik borç kontrol edilir ve varsa kaydedilir
- Borç ödemesi **feature delivery kadar önemlidir**
- "Hızlı git ve kır" değil, "sürdürülebilir hızda git" prensibi

---

## İlgili Dökümanlar

- [Geliştirme Metodolojisi](../bmad/development-methodology.md)
- [Quality Review Template](_template_QR.md)
- [Sprint Template](_template_SP.md)
