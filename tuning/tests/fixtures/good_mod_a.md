<kayit tip="E" id="E-001">
- **Tarih:** 23.08.2026
- **Durum:** planlandı
- **Teori:** Kuyruk teorisi — istek oranı servis kapasitesine yaklaştıkça p95 gecikme üstel artar.
- **Hipotez:** H-001: "p95 gecikme >= 800ms mevcut durumda; önbellek ile p95 <= 200ms bekleniyor"
- **Ölçüm metrikleri:** p95 gecikme (ms), örneklem n=1000 istek
- **Deney tasarımı:** A/B yük testi; aynı veri seti, 3 tekrar, kontrol değişkeni: aynı donanım.
- **Kod kapsamı:** src/api/search/**
- Beklenen ölçüm kapı çalıştıktan sonra kaydedilecek; şu an değer verilmiyor (tahmin olarak işaretlendi).
</kayit>
<iletisim>
Merhaba, isteğiniz için Mod A (sayısal/empirik) deney kaydını E-001 olarak planladım. Hipotez falsifiable
biçimde yazıldı ve ölçüm yalnızca kapı çalıştıktan sonra kayda geçecek. Sonraki adım: kapıyı çalıştırıp
sonucu kayda işlemek. Size onay için hazır olduğunda haber vereceğim.
</iletisim>
