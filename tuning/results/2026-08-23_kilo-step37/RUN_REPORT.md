# Tuning Çalıştırması Raporu — 2026-08-23

## Kurulum
- Model (optimizer + target): `stepfun/step-3.7-flash:free` (Kilo.ai gateway, openai_compatible backend)
- Konfigürasyon: `configs/metodoloji/default.yaml` — 3 epoch, batch_size 10, edit_budget 3, slow_update açık
- Süre: ~22 dakika, toplam ~662K token

## Sonuçlar
| Metrik | Baseline (initial.md) | En iyi (step_0001) | Δ |
|---|---|---|---|
| Seçim (val) hard | — | 0.9864 | — |
| Test soft | 0.849 | 0.9095 | +0.06 |
| Test hard | 0.8 | 0.8 | 0.0 |

- 3 adım: 1 kabul (step 1), 2 red (step 2-3 kapı reddetti).
- En iyi skill: [`best_skill.md`](best_skill.md) — harness `skills/initial.md` tohumuna promosyon uygulandı.

## Bu çalıştırma sırasında yakalanan SkillOpt hatası
`skillopt/config.py::_resolve_layer_format_duplicates` — yapısal `env.name` anahtarının düz `env` haritatingine çökmesi; silme guarded eklendi (daha önce env bölümü tamamen kayboluyordu). SkillOpt çalışma kopyasında düzeltildi; upstream'e önerilmeli.

## Pilot → tam eğitim yolu
1. Pilot: TRA-A01 hard=1, soft=1.0 (zorlu) — TRA-A01 senaryosu.
2. Tam: `scripts/train.py --config configs/metodoloji/default.yaml --out_root <out> --target_backend/optimizer_backend openai_compatible` (env var'larla Kilo endpoint + anahtar).
