---
name: metodoloji-manifesto
description: 'Metodolojinin beyni: kayıt zinciri (E→IR→SP→S→QR→PR), dört araştırma modu, beş geliştirme kapısı, guard/gate disiplini. Her oturumda geçerli temel sözleşme. Use when planning, implementing, reviewing or deploying anything under BMAD.'
triggers: ["metodoloji-manifesto", "/metodoloji-manifesto", "kayıt zinciri", "hard gate", "guard code", "metodoloji"]
---

# Metodoloji Manifestosu (çekirdek — her oturumda geçerli)

Bu skill, taşınan BMAD metodolojisinin **çekirdek sözleşmesidir**. Ayrıntılı manifestolar:
`docs/bmad/research-methodology.md` (araştırma kanadı) ve `docs/bmad/development-methodology.md`
(geliştirme kanadı) — hedef projede `/metodoloji:init` ile kurulur; köprü kuralları:
`docs/bmad/dev-skill-to-methodology-bridge.md`.

## Yol değişkenleri (plugin sözleşmesi)

| Değişken | Anlam |
|---|---|
| `{project-root}` | Üzerinde çalışılan hedef projenin kökü (kayıtlar `docs/` altında burada) |
| `{metodoloji-root}` | Bu plugin'in kökü (engine, skills, custom, bmad). Çalışma zamanında `~/.openhands/plugins/installed/metodoloji` veya workspace içi senkron `.metodoloji/plugin` |

Herhangi bir skill metninde bu değişkenleri gördüğünde yukarıdaki anlamlarla çöz.

## OpenHands araç çağrısı sözleşmesi (kritik)

Bu plugin OpenHands üzerinde çalışır — araç şemaları Claude Code'dan farklıdır:

- `terminal` aracı **yalnızca** `command` parametresi alır. `description` gibi ek
  parametre EKLEME — OpenHands `extra_forbidden` hatasıyla reddeder.
- `file_editor` aracı için `path`, `content` ve `action` alanları dışında parametre geçme.
- Script çağrılarında `uv run` yerine `python3` tercih et (uv her ortamda yok).
- Bir komutun ne yaptığını açıklamak istersen bunu **düz metinle** söyle, araç
  parametresi olarak değil.

## Kayıt zinciri (tek doğruluk zinciri)

```
E (deney kaydı)  →  IR (hazırlık)  →  SP (sprint planı)  →  S (story)  →  QR (kalite)  →  PR (üretim)
```

- **Her çıktı bir iddiadır**; iddia, moduna uygun kanıt kapısından geçmeden kodlaştırılamaz.
- Kayıtlar `{project-root}/docs/experiments/` (E) ve `{project-root}/docs/development/` (IR/SP/S/QR/PR) altında yaşar.
- `docs/bmad/dev-skill-to-methodology-bridge.md` §2.x kuralları: her geliştirme skill'inin çıktısı karşılık gelen metodoloji kaydını besler (S → QR vb.).

## Araştırma kanadı: dört mod, beş kapı

| Mod | Soru | Kanıt | Kapı |
|---|---|---|---|
| **A — Sayısal/empirik** | Ne ölçülebilir, hangi eşik? | sayı, (x/y) örneklem, ham log | **mekanik** — `run_experiment.py` ONAYLANDI + --verify VERIFIED |
| **B — Nitel/kavramsal** | Tema, örüntü, anlam? | kodlanmış tema, alıntı | belgesel (`R-id`) |
| **C — Tasarım/keşif** | Kullanıcı ihtiyacı, çözüm fikri? | senaryo, prototip | belgesel (`D-id`) |
| **D — Bağlamsal/alan** | Gerçek dünya kısıtları? | bağlam haritası | belgesel (`C-id`) |

## Geliştirme kanadı: beş aşama, dört kapı

1. Hazırlık → **Kapı 1 IR** (belgesel)  2. Sprint planı → **Kapı 2 SP** (belgesel)
3. İmplementasyon (Mod A onayı şart)  4. Kalite → **Kapı 3 QR** (hook'lu)
5. Üretim → **Kapı 4 PR** (hook'lu)

## Mekanik kapılar (hook'lar, `custom/config.toml [hooks]` soft/hard)

- **guard** (PreToolUse, `file_editor|terminal`): korunan bölgeye kod yazımı, kapsamı eşleşen
  VERIFIED deney kaydı yoksa **deny**. Serbest bölgeler: `scratch/`, `.metodoloji/`, plugin kökü.
- **stop** (PreToolUse/Stop): kapsamsız korunmuş kod varken bitişe izin vermez (exit 2).
- **quality** (PreToolUse, terminal): `git commit` IR/QR/SP'siz story varsa **deny** (fail-closed).
- **deploy** (PreToolUse, terminal): IR/QR/SP/PR eksik story ile deploy (terraform/kubectl/...) **deny** (fail-closed).
- **audit** (PostToolUse): `.metodoloji/logs/hook-audit.log` denetim izi.

## Kapı anahtarı

`~/.bmad/gate-key` (0600, makine-yerel; asla commit edilmez). Yoksa:
`python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py --init-secret`
Anahtarı okumak/kopyalamak yasaktır — guard her izi engeller.

## Dürüstlük kuralları

- Sonuç çarpıtılmaz: REDDEDİLDİ kaydı ONAYLANDI'ya çevrilmez; FORGED token kapıyı açmaz.
- Kayıt zinciri atlanmaz: IR'siz/QR'siz/SP'siz commit, IR'siz/QR'siz/SP'siz/PR'sız deploy, E'siz kod — kapı ihlali sayılır.
- Keşif kodu istiyorsan `scratch/` altında yaz; korunan bölgeye geçerken Mod A onayı gerekir.
