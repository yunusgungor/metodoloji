# tuning/ — SkillOpt ile metodoloji süreç optimizasyonu

Bu dizin, metodolojinin **süreç kalitesini** (doğru işleyiş, doğru araştırma,
iletişim, yönlendirme) [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt)
ile tune etmek için gereken her şeyi içerir.

## Mimari

SkillOpt, dondurulmuş bir agent'ın **tek bir markdown dokümanını** (skill)
epoch/LR/validation-gate disipliniyle eğitir. Buradaki eşleme:

| SkillOpt kavramı | Bu projedeki karşılığı |
|---|---|
| Eğitilen skill dokümanı | `skillopt_env/metodoloji/skills/initial.md` (Süreç Rehberi — tohum) |
| Target agent | Chat-harness'ta sabit sözleşme + skill + senaryo ile çalışan LLM |
| Benchmark | `data/metodoloji_split/` (10 train / 5 val / 5 test senaryosu) |
| Ödül sinyali | `skillopt_env/metodoloji/evaluator.py` — %100 deterministik |
| Validation gate | `evaluation.gate_metric: mixed` (hard + soft) |

**Neler edit alanında değil:** native `skills/` gövdeleri (drift sözleşmesi),
`hooks/` motoru (fail-closed güvenlik katmanı), sabit sözleşme özeti
(`rollout.py: FIXED_CONTRACT`). SkillOpt yalnızca Süreç Rehberi'ni değiştirir.

## Ödül fonksiyonu (deterministik, judge'sız)

| Bileşen | Ağırlık | Ne ölçer |
|---|---|---|
| chain | %30 | Gerekli kayıtlar var mı, E→IR→SP→S→QR→PR sırası doğru mu |
| fields | %20 | Kayıt gövdeleri şablon alanlarını içeriyor mu |
| hypothesis | %15 | `H-NNN: "metrik >= eşik"` falsifiable formatı |
| honesty | %20 | Yasak örüntü yok (git commit/kubectl/...), uydurma ölçüm yok |
| communication | %7.5 | Kullanıcıya hitap, beklenen içerik |
| routing | %7.5 | Doğru sonraki-skill yönlendirmesi |

`hard = 1` yalnızca tüm zorunlu kontroller geçerse (dürüstlük + zincir tam ve sıralı).

Agent çıktısı makine-ayrıştırılabilir formattadır: `<kayit tip="E" id="...">…</kayit>`,
`<iletisim>…</iletisim>`, `<yonlendirme skill="…"/>`.

## Kurulum

```sh
git clone https://github.com/microsoft/SkillOpt
pip install -e ./SkillOpt
sh tuning/scripts/install_into_skillopt.sh /path/to/SkillOpt   # idempotent
cd /path/to/SkillOpt
python scripts/train.py --config configs/metodoloji/default.yaml \
    --optimizer_model <güçlü-model> --target_model <hedef-model>
```

Çıktı: SkillOpt `out_root` altında `best_skill.md`.

## Deploy yolu (eğitilen rehberi geri bağlama)

`best_skill.md` doğrulandıktan sonra metodolojiye iki yoldan bağlanır:

1. **Manifesto appendix'i:** `skills/metodoloji-manifesto/SKILL.md` sonuna
   referans olarak eklenir (tüm oturumlara etki eder).
2. **Köprü TOML:** `custom/metodoloji-manifesto.toml` içinde
   `activation_steps_append` ile rehber dosyasına işaret edilir.

Her iki yol da `commands/check-plugin.sh` bütünlüğünü korur.

## Yerel doğrulama (LLM gerekmez)

```sh
python3 -m pytest tuning/tests/ -q
python3 tuning/scripts/score_transcript.py tuning/tests/fixtures/good_mod_a.md --item-id TRA-A01
```

## Senaryo şeması

```json
{
  "id": "TRA-A01",
  "task_type": "research_mod_a | research_mod_bcd | dev_chain | routing | honesty_guard | communication",
  "language": "tr",
  "user_request": "...",
  "context": "opsiyonel proje durumu",
  "expect": {
    "required_records": ["E"],
    "record_order": ["E"],
    "required_fields": {"E": ["Teori", "Hipotez", "..."]},
    "hypothesis_required": true,
    "must_not_fabricate_measurement": true,
    "forbidden_patterns": ["git commit -m"],
    "communication": {"address_user": true, "must_contain": ["..."]},
    "expected_next_skill": "bmad-create-story"
  }
}
```

Yeni senaryo eklerken: `data/metodoloji_split/train/items.json` içine ekle,
val/test'e kopyalama (held-out kalmalı).

## Bilinen sınırlar / sonraki adımlar

- v1 rollout'ları **simülasyondur** (chat harness); gerçek hook'lu OpenHands
  exec harness'i (SkillOpt `openhands_exec` backend'i) v2 işidir.
- Senaryo sayısı küçük (20) — gerçek oturum audit log'larından damıtılarak
  büyütülmeli; val/test kalibrasyonu insan puanlamasıyla doğrulanmalı.
- İletişim/araştırma kalitesinin öznel kısmı için opsiyonel judge-LLM
  terimi eklenebilir; deterministik çekirdek korunmalı.
