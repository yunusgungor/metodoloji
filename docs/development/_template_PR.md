# Production Readiness: PR-XXX — [Release Adı]

> Bu template, Production Readiness (PR) kayıtları için kullanılır.
> Geliştirme Kapı 4'ü temsil eder: production deploy öncesi operasyonel hazırlığı garanti eder.

## Production Readiness: PR-XXX — [Release adı]

- **Tarih:** [YYYY-MM-DD]
- **Durum:** hazırlanıyor | HAZIR | BEKLİYOR
- **Release tipi:** [Major / Minor / Patch / Hotfix]
- **Versiyon:** [v1.2.3]
- **Release kapsamı:** [QR-id listesi — bu release'e ne giriyor]
  - QR-001: [Story başlığı]
  - QR-002: [Story başlığı]
  - QR-003: [Story başlığı]

---

## Staging Test

### Deployment
- **Staging environment:** [URL veya environment adı]
- **Deploy tarihi:** [YYYY-MM-DD HH:MM]
- **Deploy yöntemi:** [CI/CD pipeline / manuel / script]
- **Deploy süresi:** [X dakika]
- **Deploy durumu:** ✓ SUCCESS / ✗ FAILED

### Smoke Tests
- **Test senaryoları:**
  - [Senaryo 1]: [Tanım] → ✓ PASS / ✗ FAIL
  - [Senaryo 2]: [Tanım] → ✓ PASS / ✗ FAIL
  - [Senaryo 3]: [Tanım] → ✓ PASS / ✗ FAIL
- **End-to-end test:** ✓ PASS / ✗ FAIL
- **Critical path test:** ✓ PASS / ✗ FAIL
- **Durum:** ✓ ALL PASS / ✗ FAILURES

### Integration Tests (Staging)
- **Database migration:** ✓ SUCCESS / ✗ FAILED
- **External services:** ✓ CONNECTED / ✗ FAILED
- **API endpoints:** [X/Y working]
- **Durum:** ✓ ALL SYSTEMS GO / ✗ ISSUES

---

## Rollback Planı

- **Rollback yöntemi:** [Blue-green / rolling / instant]
- **Rollback tetikleyicileri:** [Hangi durumda rollback yapılır]
  - [Trigger 1: error rate > %5]
  - [Trigger 2: latency > 500ms]
  - [Trigger 3: crash rate > %1]
- **Rollback süresi:** [Tahmini X dakika]
- **Rollback adımları:**
  1. [Adım 1: alarm tetiklendi, deploy durdur]
  2. [Adım 2: traffic'i önceki versiyona yönlendir]
  3. [Adım 3: yeni version'ı kaldır]
  4. [Adım 4: database rollback (gerekiyorsa)]
  5. [Adım 5: smoke test önceki version'da]
- **Rollback testi yapıldı mı:** ✓ Evet (staging'de) / ✗ Hayır
- **Database rollback:** [Gerekli mi? Nasıl?]
  - Migration geri alınabilir mi: ✓ Evet / ✗ Hayır (destructive)
  - Rollback SQL: [Varsa dosya referansı]

---

## Monitoring ve Alerting

### Metrikler
- **Business metrics:**
  - [Metrik 1: günlük aktif kullanıcı] → Dashboard: [link]
  - [Metrik 2: işlem başarı oranı] → Dashboard: [link]
- **Technical metrics:**
  - [Metrik 3: response time] → Dashboard: [link]
  - [Metrik 4: error rate] → Dashboard: [link]
  - [Metrik 5: CPU/memory usage] → Dashboard: [link]
- **Dashboard URL:** [Production monitoring dashboard link]

### Alertler
- **Critical alerts:**
  - [Alert 1: error rate > %5] → Kanal: [slack/pagerduty] → Sahibi: [kim]
  - [Alert 2: latency > 1000ms] → Kanal: [slack/pagerduty] → Sahibi: [kim]
- **Warning alerts:**
  - [Alert 3: memory > %80] → Kanal: [slack] → Sahibi: [kim]
- **Alert testi yapıldı mı:** ✓ Evet / ✗ Hayır

### Logging
- **Log aggregation:** [Tool: ELK / Splunk / CloudWatch]
- **Log retention:** [X gün]
- **Structured logging:** ✓ Evet / ✗ Hayır
- **Log queryability:** ✓ Test edildi / ✗ Edilmedi

---

## Feature Flags

- **Feature flag kullanılıyor mu:** ✓ Evet / ✗ Hayır
- **Flag planı:**
  - [Feature 1]: [flag adı] → Rollout: [%0 → %10 → %50 → %100]
  - [Feature 2]: [flag adı] → Rollout: [%0 → %100 (instant)]
- **Kill switch:** ✓ Var / ✗ Yok
  - [Hangi feature'lar anında kapatılabilir]
- **Gradual rollout süresi:** [X saat/gün]

---

## Runbook

### Deploy Adımları
1. [Pre-deploy: database backup]
2. [Pre-deploy: notify team]
3. [Deploy: CI/CD pipeline trigger]
4. [Deploy: wait for green deployment]
5. [Post-deploy: smoke test]
6. [Post-deploy: monitor 30 min]
7. [Post-deploy: notify completion]

### Troubleshooting
- **Yaygın sorunlar ve çözümleri:**
  - [Sorun 1]: [Tanım] → Çözüm: [adımlar]
  - [Sorun 2]: [Tanım] → Çözüm: [adımlar]
- **Runbook URL:** [Detaylı runbook wiki/doc linki]

### Rollback Adımları (Detaylı)
[Rollback Planı bölümünde yazılanların detayı, komutlar dahil]

---

## Incident Response

### İletişim Planı
- **Incident lead:** [Ad Soyad, iletişim]
- **Technical lead:** [Ad Soyad, iletişim]
- **Stakeholder iletişim:** [Kanal: email/slack]
- **On-call roster:** [PagerDuty/Opsgenie link veya liste]

### Incident Severity
- **SEV1 (Critical):** [Tanım, SLA: X dakika response]
- **SEV2 (Major):** [Tanım, SLA: Y saat response]
- **SEV3 (Minor):** [Tanım, SLA: Z gün response]

### Post-Mortem
- **Post-mortem gerekli mi:** [SEV1/SEV2 için zorunlu]
- **Template:** `docs/development/incidents/PM-XXX.md`

---

## Deploy Penceresi

- **Planlanan deploy zamanı:** [YYYY-MM-DD HH:MM UTC]
- **Deploy penceresi:** [X saat — deploy + monitoring]
- **Freeze period:** [Varsa hangi günler/saatler deploy yapılmaz]
- **Change approval:** ✓ Onaylandı (kim: [ad], tarih: [YYYY-MM-DD]) / ✗ Bekliyor

---

## Karar

- **Karar:** HAZIR | BEKLİYOR → [Gerekçe]
- **Blokerleri (varsa):**
  - [Bloker 1: staging smoke test failed]
  - [Bloker 2: rollback plan eksik]
- **Sonraki adım:** production deploy | eksikleri tamamla

---

## Deploy Sonucu (Post-Deploy)

> Bu bölüm deploy sonrasında doldurulur

- **Deploy tarihi:** [YYYY-MM-DD HH:MM UTC]
- **Deploy süresi:** [X dakika]
- **Deploy durumu:** ✓ SUCCESS / ✗ FAILED / ⚠ ROLLED BACK
- **Post-deploy metrics (ilk 1 saat):**
  - Error rate: [%X] (baseline: [%Y])
  - Latency p95: [X ms] (baseline: [Y ms])
  - Traffic: [X req/sec] (baseline: [Y req/sec])
- **Incident varsa:** [PM-XXX referansı]
- **Notlar:** [Deploy sırasında öğrenilen dersler, iyileştirme önerileri]

---

## Checklist (Kapı 4 Kontrolü)

### Staging
- [ ] Staging'e başarılı deploy edildi
- [ ] Smoke tests geçti
- [ ] End-to-end integration test geçti

### Rollback
- [ ] Rollback planı hazır ve net
- [ ] Rollback tetikleyicileri tanımlı
- [ ] Rollback testi staging'de yapıldı (veya dry-run)
- [ ] Database rollback planı var (gerekiyorsa)

### Monitoring
- [ ] Dashboard kuruldu ve erişilebilir
- [ ] Critical alertler kuruldu ve test edildi
- [ ] Logging yapılandırıldı ve query test edildi

### Feature Flags (varsa)
- [ ] Feature flag planı tanımlı
- [ ] Kill switch hazır
- [ ] Gradual rollout stratejisi net

### Runbook
- [ ] Deploy adımları dokümante edildi
- [ ] Troubleshooting guide hazır
- [ ] Rollback adımları detaylı yazıldı

### Incident Response
- [ ] On-call roster güncel
- [ ] İletişim kanalları tanımlı
- [ ] Incident severity ve SLA net

### Approval
- [ ] Change approval alındı
- [ ] Deploy penceresi belirlendi
- [ ] Stakeholder'lar bilgilendirildi

**Deploy Kriteri:** Tüm checklist itemleri tamamlanmış olmalı. Rollback planı yoksa, monitoring eksikse deploy engellenir.
