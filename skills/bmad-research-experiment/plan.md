# bmad-research-experiment — Plan (bmad-builder formatı)

- **Skill adı:** bmad-research-experiment
- **Tip:** workflow skill (tek workflow, tek kullanım alanı)
- **Modül:** bmm (software-development)
- **Amaç:** Bilimsel metodolojinin kalbi olan **Teori→Hipotez→Deney→Ölçüm→Onay** akışını
  eksiksiz yürütür. Onay kapısı PASS vermeden çıktı "ONAYLANDI" olamaz.
- **Kurulum yeri:** `{metodoloji-root}/skills/bmad-research-experiment/`
- **Çıktılar:** `docs/experiments/<deney-id>.md` + `docs/experiments/<deney-id>/raw/` (ham veri)
- **Kapı araçları:** onay mekanizmasını HİÇBİR şekilde test etmeden (assert-based `__main__`
  doğrulaması olmadan) yazmayı REDDET — test edilmemiş kapı, metodolojiyi koruyamaz.

## Bileşenler

| Dosya | Amaç |
|-------|------|
| `SKILL.md` | Aktivasyon + 6 adım akışı (Teori→Hipotez→Deney→Ölçüm→Onay→Sonuç) + dürüstlük kuralları |
| `customize.toml` | Yüzey: `persistent_facts` manifesto yükleme, `activation_steps_append` (manifesto + Stage-6 doğrulama) |
| `experiment-log.md` | Zorunlu deney kaydı şablonu (manifestodaki format) |
| `scripts/run_experiment.py` | Ölçüm çalıştırıcısı: hipotez eşiğine karşı mekanik onay kapısı (assert tabanlı) |

## Deney kaydı şablonu (zorunlu alanlar)

- `deney-id`, `tarih`, `durum`
- `teori`, `hipotez` (H-id, yanlışlanabilir iddia, **eşik değer**)
- `ölçüm metrikleri` (metrik adı + eşik), `deney tasarımı`
- `ham sonuçlar` (sayılar — olduğu gibi)
- `karar` (ONAYLANDI / REDDEDİLDİ + gerekçe), `sonraki adım`

## Onay kapısı mantığı (mekanik)

Ölçüm değeri vs hipotez eşiği karşılaştırması:

- `PASS`: ölçüm eşiği geçti → karar `ONAYLANDI`
- `FAIL`: ölçüm eşiği karşılamadı → karar `REDDEDİLDİ`, gerekçe kaydedilir
- Kapı komutu çıktısı `PASS` değilse skill, çıktıyı `ONAYLANDI` olarak İŞARETLEYEMEZ.
- **Sahtekarlık koruması:** kapı komutu hipotez eşiğini kullanır; hipotezi sonradan değiştirip
  "kabul edildi" demek geçersizdir (kayıttaki `hipotez` alanı değişmez — yeni hipotez → yeni deney).
- **Kayda bağlı kapı:** `--verify`, kayıttaki `Hipotez` claim'ini `Kapı kanıtı`'ndaki claim ile
  çapraz doğrular. Onay sonrası eşiği değiştirip jetonu koruyan kayıt, token jetonla eşleşse bile
  `FORGED` döner.
- **Örneklem/CI (kural 4, mekanik):** kapı `--run` çıktısındaki `(x/y)` paydasını örneklem `n`
  olarak ayrıştırır, %95 Wilson alt sınırını hesaplar; eşiğin altındaysa kayda `Belirsizlik`
  satırı yazar (`örneklem küçük`), yeterliyse `yok`, payda yoksa `n bilinmiyor`. Tavsiye amaçlıdır,
  red değil; jeton `n`'yi içermez (mevcut token'lar geçerli kalır). `--measured` için `--n` veya
  `Örneklem n` alanı.

## dürüstlük kuralları (bölüm 2'den alıntı)

- Reddedilen hipotez silinmez/gizlenmez; kaydedilir, raporlanır.
- Ham veri olduğu gibi saklanır.
- Belirsizlik itiraf edilir.
- "Denemedik, denemiş gibi gösterdik" yasaktır.
- Negatif sonuç da sonuçtur.

## Doğrulama (bmad-customize Step 6)

- `python3 {metodoloji-root}/hooks/engine/resolve_customization.py --skill {skill-root} --key workflow` — OpenHands terminal tool yalnızca command parametresi alır; description EKLEME
- Kapı betiği: `python3 scripts/run_experiment.py` kendi `__main__` doğrulamasıyla test edilir
  (PASS ve FAIL yolları, assert tabanlı).

## Kapanış koşulu

- Skill dosyaları yazıldı, resolver override'ı doğruladı, kapı betiği testi geçti.
- Kullanıcı özeti aldı.
