# SkillOpt Output

Bu dizin SkillOpt eğitim ve değerlendirme çıktılarını tutar.

## Commit politikası

| Dosya/klasör | Commit | Neden |
|---|---|---|
| `baseline.json` | ✓ | Eğitim öncesi/sonrası karşılaştırma referansı (değişmez) |
| `<skill>/best_skill.md` | ✗ | Eğitim çıktısı, büyük, değişken |
| `<skill>/history.json` | ✗ | Eğitim logu, büyük |
| `<skill>/config.json` | ✓ | Eğitim parametreleri (küçük, audit trail) |
| `<skill>/training_summary.json` | ✗ | Eğitim sonuç özeti, her koşuda değişir |
| `*-eval/` | ✗ | Ara değerlendirme, geçici |

## Kullanım

```sh
# Baseline (eğitim öncesi)
python optimization/scripts/baseline.py
# → optimization/output/baseline.json

# Eğitim sonrası karşılaştırma
python optimization/scripts/compare.py
# → baseline.json vs benchmark_results.json diff
```
