---
name: bmad-code-docs
description: 'Code docs yönetimi — hatırlama, sorgulama, üretme, otomatik yükleme.'
triggers: ["bmad-code-docs", "recall", "hatırla", "code docs", "geçmiş"]
---

# Code Docs

**Goal:** Proje geçmişini hatırlamak, yeni bilgi üretmek ve otomatik bağlam yüklemek.

## Kurallar

1. Her code-doc geçerli YAML frontmatter içermelidir: id, type, title, date, tags
2. Bölümler Türkçe etiketlerle yazılır
3. Doc türü doğru seçilmelidir: P, T, D, L, A, X
4. İlişkili deney ve story'ler link olarak eklenir
5. Index otomatik güncellenir
6. **Her görev başlangıcında ilgili code-doc'lar otomatik yüklenir**

## Doc Türleri

- **P (Pattern):** Kalıp, kullanım, örnek, avantaj/dezavantaj
- **T (Troubleshooting):** Hata, neden, çözüm, önleme
- **D (Decision):** Karar, gerekçe, sonuçlar
- **L (Learning):** Öğrenilen, bağlam, kanıt, uygulama
- **A (API):** İmza, kullanım, dikkat edilecekler
- **X (Pending):** Bekleyen işler, TODO/FIXME, gelecek planları

## Otomatik Yükleme Kuralları

Görev başlangıcında şu adımları izle:

1. **Görev açıklamasından keyword çıkar** (auth, guard, experiment, vb.)
2. **Keyword'lere göre tag'lerde ara** → ilgili doc'ları bul
3. **Deney referanslarını kontrol et** (E-NNN) → ilişkili doc'ları bul
4. **Bekleyen işleri her zaman yükle** (dikkat gerektirenler)
5. **Yüklenen bağlamı kullan** → aynı hataları tekrarlama, bilinen kalıpları uygula

## Ne Zaman Yeni Doc Üret

- **Yeni karar alındığında** → D doc
- **Tekrar eden kalıp tespit ettiğinde** → P doc
- **Deney sonucunda** → L doc
- **Yeni API kullandığında** → A doc
- **Hata çözdüğünde** → T doc
- **TODO/FIXME gördüğünde veya gelecek planlandığında** → X doc

## Pending (X) Doc Kuralları

### Oluşturma Zamanı
- TODO/FIXME yorumu görüldüğünde
- Gelecek adım planlandığında
- Deney başarısız olduğunda (teori revizyonu)
- Bağımlılık tespit edildiğinde
- Yüksek öncelikli iş belirlendiğinde

### Öncelik Seviyeleri
- **urgent**: Sprint'i bloke eden, güvenlik sorunu
- **high**: Deney sonucuna bağlı, kritik geliştirme
- **normal**: Standart geliştirme işleri
- **low**: İyileştirme, optimizasyon

### Güncelleme Kuralları
- Tamamlanan iş: `status: pending` → `status: done`
- Tamamlanma tarihi ekle
- İlişkili deney/story referanslarını güncelle

### Bağımlılık Takibi
- Bağımlı işleri belirt: "E-148 deneyinden sonra yapılmalı"
- Sıralama: Bağımlılık önce tamamlanmalı
- Cross-reference: İlişkili pending'leri linkle
