# Deney Kaydı Şablonu — docs/experiments/<deney-id>.md

Bu şablon zorunludur. Her alan doldurulur; boş alan deneyin o aşamadan geçmediği anlamına
gelir. `Ham sonuçlar`, `Belirsizlik`, `Metrik`, `Karar`, `Kapı kanıtı`, `Sonraki adım` ve
`durum` alanlarını onay kapısı yazar — elle doldurulmaz.

```
## Deney: <deney-id> — <kısa başlık>
- **Tarih:** <GG.AA.YYYY>
- **Durum:** planlandı | yürütülüyor | tamamlandı | REDDEDİLDİ
- **Teori:** <hangi teoriden/çerçeveden geldiği — "merak ettim" yeterli değil>
- **Hipotez:** H-NNN: "metrik >= eşik"   <!-- ör. H-001: "accuracy >= 0.90" — yanlışlanabilir iddia, eşik birimsiz sayısal -->
- **Ölçüm metrikleri:** <metrik adı + eşik, ör. "latency <= 100" (birimsiz sayısal eşik kullanın)
- **Deney tasarımı:** <girdiler, prosedür, kontrol değişkenleri, tekrarlanabilirlik>
- **Örneklem n:** <opsiyonel — örneklem büyüklüğü; yoksa kapı "n bilinmiyor" uyarısı yazar>
- **Ham sonuçlar:** <sayılar/çıktılar — olduğu gibi; ham dosyalar: docs/experiments/<deney-id>/raw/>
- **Belirsizlik:** <kapı yazar: örneklem küçük | yok | n bilinmiyor — elle doldurulmaz>
- **Metrik:** <kapı yazar: uyumlu | UYUMSUZ | n/a>
- **Karar:** <kapı yazar: ONAYLANDI | REDDEDİLDİ — gerekçe>
- **Kapı kanıtı:** <GATE-OK-... jetonu — kapı betiği tarafından yazılır>
- **Sonraki adım:** Kod'a geç | Teori'ye dön | Ek deney
```

## Notlar

- `karar`, `{skill-root}/scripts/run_experiment.py` çıktısına (PASS/FAIL) dayanır.
  Kapı PASS vermeden `ONAYLANDI` yazılamaz.
- `REDDEDİLDİ` kararı silinmez, gizlenmez; olduğu gibi raporlanır.
- Yeni hipotez → yeni deney id'si (`H-002`, `E-002`, ...). Aynı deney kaydı yeniden
  yazılarak hipotez değiştirilmez — bu sahtekarlıktır.
