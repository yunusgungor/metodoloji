# Deney Kaydı Şablonu (Mod A — Sayısal / Empirik, MEKANİK KAPI)

Yeni bir deney için bu dosyayı kopyala: `docs/experiments/E-NNN.md`

Bu şablon **Mod A (sayısal/empirik)** içindir — kod üretiminin tek meşru yolu. Belgesel
modlar için: Mod B (nitel) ve Mod D (bağlamsal) → `docs/research/_template.md`; Mod C
(tasarım) → `docs/design/_template.md`. Manifesto: `docs/bmad/research-methodology.md`.

Türkçe alan etiketleri **zorunludur** — kapı (`run_experiment.py`) bu etiketleri ayrıştırır.
`Karar`, `Kapı kanıtı`, `Sonraki adım`, `Durum` satırlarını **elle yazma**; kapı yazar.

```markdown
## Deney: E-NNN — <kısa başlık>
- **Tarih:** <GG.AA.YYYY>
- **Durum:** planlandı
- **Teori:** <hangi teoriden/çerçeveden geldiği — "merak ettim" yetmez>
- **Hipotez:** H-NNN: "metrik >= eşik"   <!-- ör. H-001: "accuracy >= 0.90" -->
- **Ölçüm metrikleri:** <metrik adı + eşik, birimsiz sayısal>  <!-- ör. accuracy >= 0.90 -->
- **Deney tasarımı:** <girdiler, prosedür, kontrol değişkenleri, tekrarlanabilirlik>
- **Örneklem n:** <örneklem büyüklüğü — kapı paydayı (x/y) ölçüm çıktısından ayrıştırır; bu alan bilgi amaçlıdır>
- **Kod kapsamı:** <bu onayın açtığı dosyaların glob'ları, virgül/boşluk ayrık; ör. src/** , lib/engine/*.py>
  <!-- "yok" = kod üretmeyen deney. Kapsam dışı dosyaya yazım guard tarafından engellenir. -->
- **Ham sonuçlar:** <ölçüm — kapı yazar>
- **Belirsizlik:** <kapı yazar: örneklem küçük | yok | n bilinmiyor>
- **Metrik:** <kapı yazar: uyumlu | UYUMSUZ — ölçülen metrik --run çıktısından gelir>
- **Karar:** <kapı yazar: ONAYLANDI | REDDEDİLDİ — gerekçe>
- **Kapı kanıtı:** <kapı yazar: GATE-OK-...>
- **Sonraki adım:** <kapı yazar: Kod'a geç | Teori'ye dön>
```

## Kapı anahtarını kur (makine başına bir kez)

```bash
python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py --init-secret
# Anahtar ~/.bmad/gate-key dosyasına yazılır (repo DIŞI). Kontrol:
python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py --check-secret
```

## Kapıyı çalıştır

```bash
# Kapı ölçümü kendisi çalıştırır: değer + metrik adı + payda (x/y) çıktıdan ayrıştırılır.
# Operatörün sayı beyan etmesi yoktur (--measured kaldırıldı — gerçeklik mekaniktir).
# Ölçüm betiği korumalı bölgede yaşamalıdır: scratch/ altındaki betik --run ile reddedilir
# (ör. scripts/bench/ kullanın).
python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py \
  --record docs/experiments/E-NNN.md --run "python scripts/bench/bench_xxx.py"
# Dry-run: kararı YAZMADAN önizle (format/kayıt kontrolü — "kontrol" için --run'ı asla
# yalnız kullanma, kaydı yanlışlıkla karara bağlar)
python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py \
  --record docs/experiments/E-NNN.md --run "python scripts/bench/bench_xxx.py" --dry-run
```

## Kod öncesi doğrula

```bash
python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py \
  --verify --record docs/experiments/E-NNN.md
```

Ham veri dosyalarını `docs/experiments/E-NNN/raw/` altında tut.
