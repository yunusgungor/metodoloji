# Implementation Readiness: IR-XXX — [Kısa Başlık]

> Bu template, Implementation Readiness (IR) kayıtları için kullanılır.
> Geliştirme Kapı 1'i temsil eder: araştırmadan gelen bulguların geliştirme için hazır olup olmadığını kontrol eder.

## Implementation Readiness: IR-XXX — [Kısa başlık]

- **Tarih:** [YYYY-MM-DD]
- **Durum:** hazırlanıyor | HAZIR | EKSİK
- **Araştırma girdileri:** [E/R/D/C-id listesi]
  - Örnek: E-001 (BFS optimizasyonu), D-005 (kullanıcı akış tasarımı), R-010 (kullanıcı ihtiyaç bulgusu)
- **Tasarım belgeleri:** [PRD/UX/mimari dosya referansları]
  - PRD: [dosya yolu veya "yok"]
  - UX Speci: [dosya yolu veya "yok"]
  - Mimari Plan: [dosya yolu veya "yok"]
- **Başarı kriterleri:** [Ne olursa başarılı sayılır]
  - Fonksiyonel: [Özellik tam çalışıyor, test coverage %80+]
  - Non-fonksiyonel: [Performans hedefi, güvenlik standardı]
  - Kullanıcı: [Kullanıcı kabul kriterleri]
- **Teknik bağımlılıklar:** [API'ler, kütüphaneler, altyapı]
  - API'ler: [hangi API'ler gerekli, mevcut mu]
  - Kütüphaneler: [yeni bağımlılık eklenecek mi, versiyonlar]
  - Altyapı: [database, cache, queue vs. hazır mı]
  - Harici servisler: [3rd party entegrasyonlar]
- **Risk değerlendirmesi:** [Bilinen riskler + mitigation planı]
  - Risk 1: [tanım] → Mitigation: [nasıl azaltılacak]
  - Risk 2: [tanım] → Mitigation: [nasıl azaltılacak]
- **Eksikler:** [Eksik ise ne eksik, nasıl tamamlanacak]
  - [Eksik item 1] → [Araştırma modu: A/B/C/D] → [Tahmini süre]
  - [Eksik item 2] → [Araştırma modu: A/B/C/D] → [Tahmini süre]
- **Karar:** HAZIR | EKSİK → [Gerekçe]
- **Sonraki adım:** sprint planlamaya geç | araştırmaya dön: [hangi mod, hangi soru]

---

## Notlar

- **HAZIR:** Tüm girdiler tamamlanmış, bağımlılıklar hazır, sprint planlanabilir
- **EKSİK:** Eksikler belirlenmiş, her eksik için araştırma planı var
- Eksik varsa sprint başlatılmaz; önce araştırma kanadına dönülür
- Bu kayıt geliştirme kanadının "giriş kapısı"dır: araştırma → geliştirme geçişi

---

## Checklist (Kapı 1 Kontrolü)

- [ ] En az bir onaylı araştırma kaydı var (E/R/D/C-id)
- [ ] PRD veya story tanımlı
- [ ] UX speci hazır (gerekiyorsa)
- [ ] Mimari plan hazır (gerekiyorsa)
- [ ] Başarı kriterleri net ve ölçülebilir
- [ ] Teknik bağımlılıklar belirlendi
- [ ] Risk değerlendirmesi yapıldı
- [ ] Eksikler için plan var (varsa)
