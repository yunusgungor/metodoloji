# Quality Review: QR-XXX — [Story/PR Referansı]

> Bu template, Quality Review (QR) kayıtları için kullanılır.
> Geliştirme Kapı 3'ü temsil eder: kod merge edilmeden önce kalite standartlarını zorlar.

## Quality Review: QR-XXX — [Story/PR referansı]

- **Tarih:** [YYYY-MM-DD]
- **Durum:** review'da | ONAYLANDI | REDDEDİLDİ | REVİZE
- **Story:** [S-id referansı, örn. S-001]
- **PR/MR:** [Pull request linki veya ID]
- **Branch:** [feature/branch-adı]
- **Değişen dosyalar:** [Kaç dosya, kaç satır +/−]

---

## Mekanik Kontroller (Otomatik)

### Test Coverage
- **Oran:** [X%]
- **Eşik:** %80 (minimum)
- **Durum:** ✓ PASS / ✗ FAIL
- **Notlar:** [Coverage düşükse hangi modüller eksik]

### Test Sonuçları
- **Unit tests:** [X passed / Y total] → ✓ PASS / ✗ FAIL
- **Integration tests:** [X passed / Y total] → ✓ PASS / ✗ FAIL
- **E2E tests:** [X passed / Y total] → ✓ PASS / ✗ FAIL
- **Flaky tests:** [Varsa hangileri, neden flaky]
- **Durum:** ✓ ALL PASS / ✗ FAILURES

### Linter / Formatter
- **Linter:** ✓ PASS / ✗ FAIL
  - [Varsa linter hataları/uyarıları]
- **Formatter:** ✓ PASS / ✗ FAIL
  - [Format hataları]
- **Durum:** ✓ PASS / ✗ FAIL

### Security Scan
- **Vulnerability scan:** ✓ CLEAN / ✗ FOUND
  - [Varsa bulgular: severity, CVE ID, paket]
- **Dependency check:** ✓ PASS / ✗ FAIL
  - [Bilinen güvenlik açığı olan dependency var mı]
- **Secret scanning:** ✓ CLEAN / ✗ FOUND
  - [Hardcoded secret, API key, password bulundu mu]
- **Durum:** ✓ CLEAN / ✗ ISSUES FOUND

### Performance Regression
- **Benchmarks:** [Kritik fonksiyonların performansı]
  - [Fonksiyon 1]: [X ms] (önceki: [Y ms]) → [% değişim]
  - [Fonksiyon 2]: [X ms] (önceki: [Y ms]) → [% değişim]
- **Memory usage:** [X MB] (önceki: [Y MB]) → [% değişim]
- **Durum:** ✓ NO REGRESSION / ✗ REGRESSION DETECTED

---

## Belgesel Kontroller (Manual Review)

### Code Review
- **Reviewer(lar):** [@username1, @username2]
- **Review tarihi:** [YYYY-MM-DD]
- **Yorumlar (özet):**
  - [Önemli feedback 1]
  - [Önemli feedback 2]
  - [Önemli feedback 3]
- **Code quality:**
  - Okunabilirlik: ✓ İyi / ⚠ Orta / ✗ Zayıf
  - Maintainability: ✓ İyi / ⚠ Orta / ✗ Zayıf
  - Design patterns: ✓ Uygun / ⚠ İyileştirilebilir / ✗ Sorunlu
- **Onay:** ✓ APPROVED / ⚠ APPROVED WITH COMMENTS / ✗ CHANGES REQUESTED
- **Gerekçe:** [Onay/red gerekçesi]

### Dokümantasyon
- **Code comments:** ✓ Yeterli / ⚠ Eksik / ✗ Yok
- **API dokümantasyonu:** ✓ Güncellendi / ⚠ Kısmi / ✗ Eksik
- **README/guides:** ✓ Güncellendi / ⚠ Kısmi / ✗ Eksik
- **Changelog:** ✓ Eklendi / ✗ Eksik
- **Durum:** ✓ COMPLETE / ⚠ NEEDS WORK / ✗ MISSING

### Breaking Changes
- **Breaking change var mı:** ✓ Evet / ✗ Hayır
- **Migration plan:** [Varsa nasıl migrate edilecek]
  - [Adım 1]
  - [Adım 2]
- **Deprecation notice:** [Varsa eski API'nin ne zaman kaldırılacağı]
- **Backward compatibility:** ✓ Korundu / ⚠ Kısmen / ✗ Bozuldu

### Teknik Borç
- **Yeni borç eklendi mi:** ✓ Evet / ✗ Hayır
- **Borç detayı:**
  - [Borç 1]: [Tanım] — [Neden eklendi, TODO referansı]
  - [Borç 2]: [Tanım] — [Neden eklendi, TODO referansı]
- **Borç kaydedildi mi:** ✓ Evet (`docs/development/tech-debt.md`) / ✗ Hayır

---

## Karar

- **Karar:** ONAYLANDI | REDDEDİLDİ | REVİZE → [Gerekçe]
- **Red nedeni (varsa):**
  - [Neden 1: test coverage düşük]
  - [Neden 2: security issue]
  - [Neden 3: code review değişiklik istedi]
- **Sonraki adım:** merge | revize gerekli | deploy planla

---

## Checklist (Kapı 3 Kontrolü)

### Mekanik (otomatik, zorunlu)
- [ ] Test coverage >= %80
- [ ] Tüm testler geçti (unit, integration, e2e)
- [ ] Linter ve formatter clean
- [ ] Security scan clean (bilinen vulnerability yok)
- [ ] Performance regression yok

### Belgesel (manual review, zorunlu)
- [ ] En az bir reviewer onayladı
- [ ] Code quality kabul edilebilir
- [ ] Dokümantasyon güncellendi
- [ ] Breaking change varsa migration plan hazır
- [ ] Teknik borç kaydedildi (varsa)

### Merge Kriteri
- [ ] Tüm mekanik kontroller PASS
- [ ] En az bir code review APPROVED
- [ ] Dokümantasyon COMPLETE veya NEEDS WORK (minör eksikler kabul edilebilir)
- [ ] Karar: ONAYLANDI

**Not:** Herhangi bir mekanik veya kritik belgesel kontrol başarısız ise merge engellenir.
