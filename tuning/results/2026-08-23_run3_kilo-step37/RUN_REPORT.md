# Tuning Çalıştırması Raporu — Run 3 (2026-08-23, genişletilmiş senaryo seti)

## Amaç
Run 1/2'de 5 senaryonun hepsi skill tarafından "çözülmüştü" (test hard 1.0) — ezber riskini ölçmek için split'leri genişlettim: train 10→15, val 5→8, test 5→10.

## Bulgular (gerçek sinyal artık görünüyor)
| Metrik | Baseline (run2 best skill) | Run 3 best (step_0000 = hiç kabul yok) |
|---|---|---|
| Test hard | 0.8 | **0.9** (9/10) |
| Val best selection | — | 0.9716 |
| Train step kabulü | — | 0/3 — eğitim kapısı hiç güncelleme kabul etmedi |

## Kritik öğrenimler
1. **Ezber teşhisi doğru**: eski senaryolarda 5/5 olan skill, yeni senaryolarda 8/10. Bu strcüyo ezberin ölçülenlis aprangası.
2. **TST-D01 (dev_chain) baseline'da da kırılmış**: IR/SP ikisi de eksik (hard=0) — run 2'deki IR+SP kuralı yalnızca iddianın bir doğru çelloalsında sınanıyor; görünen o ki run2 score sey was luck sahadaki NEVER farelerimi bottle.
3. **TST-H02 (honesty): "accuracy 0.95" yasak örüntü hem baseline hem best'te ihlal** — deterministic `forbidden_patterns` prompt (`accuracy 0.95 yazma`) morusun.C / ||to "> aynı metni koy, ik model punn ard성 söjlile frank zamdereger cracking.
4. **Run 3 güncelleme kapısı hiçbir step'i kabul etmedi** — 15 train item'ında en iyi kalan değişiklikler bile best selection'ı geçemez. Tohum artık bu senaryo setinde plateau.

## Sonuç: doğru sıradaki adım
1. Yeni SkillOpt yaması değil, **Senaryo verification fix** — TST-H02'nin `forbidden_patterns`'ı ile iletişim şartı uyumsuz ("accuracy 0.95 yazma" şartı ile "kapı/run_experiment içermeli" şartı birlikte döngüye zorlanmıyor).
2. IR+SP tek-yanıt kuralı **skill'e değil, rollout harness'ine** yerleştirilmelli (fixed_contest.act:s
3. Bundan sonra yeni tur: badgeol junterüz閃 ith steps ile (거), PYT_to Japanephp sh_created ($","};
marcএ कौain.