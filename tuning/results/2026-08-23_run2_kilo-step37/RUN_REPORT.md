# Tuning Çalıştırması Raporu — Run 2 (2026-08-23, akşam)

## Kurulum
- Model (optimizer + target): `stepfun/step-3.7-flash:free` (Kilo.ai gateway, openai_compatible backend)
- Tohum skill: run 1'in best skill'i (step_0001 routing düzeltmesi promosyonlanmış)
- Değişiklik: `rollout_system.md` — geliştirme isteğinde IR+SP'nin **tek yanıtta** üretilmesi artık zorunlu (run 1'deki `dev_chain` hatasının kök nedeni: model SP kaydını hiç üretmiyordu)
- Konfigürasyon: 3 epoch, batch_size 10, edit_budget 3
- Süre: ~20 dakika, ~857K token

## Sonuçlar
| Metrik | Run 1 final | Run 2 final | Run 2 baseline |
|---|---|---|---|
| Val (seçim) hard | — | **1.0** | — |
| Test hard | 0.8 | **1.0** (5/5) | **1.0** |
| Test soft | 0.9095 | 0.954 | 0.9095 |

- 3 step: 2 kabul, 1 red. En iyi: step_0002 (best_selection_hard 0.9888)
- `dev_chain` testte artık geçiyor: run 1'de hard=0 → run 2'de hard=1
- Run 2 baseline (tohum = run1 best): test_hard 1.0 — tohum zaten güçlü; run 2'deki 2 kabulü ile soft 0.9095 → 0.954

## Not: best-on-val paradoksu
Best-on-val (step 2) testte hard=0.6, final skill ise 1.0. n=5 test + ücretsiz tier model varyansı; `final_skill.md` (step 3 hali, yani step 2 + slow_update) de kayıtlı. İkisi de kıyas için korunuyor.

## SkillOpt hatası (devam)
`skillopt/config.py::_resolve_layer_format_duplicates` düzeltmesi çalışma kopyasında uygulanıyor; upstream'e gitmeyi bekliyor (`fix/env-name-collision-clean` dalı hazır).
