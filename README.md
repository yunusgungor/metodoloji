# metodoloji (OpenHands plugin)

BMAD metodolojisinin OpenHands SDK plugin karşılığı: 125 skill + 74 köprü TOML +
mekanik kapılar (guard/stop/quality/deploy) + kayıt zinciri (E → IR → SP → S → QR → PR).

## Ne yapar

| Parça | İşlev |
|---|---|
| `skills/` | 124 BMAD skill'i (native gövde) + `metodoloji-manifesto` (çekirdek sözleşme) |
| `custom/` | 74 köprü TOML (`activation_steps_append` → native çıktıları metodoloji kaydına bağlar) + `config.toml` (soft/hard) |
| `hooks/` | PreToolUse/PostToolUse/Stop/SessionStart hook'ları; modüler motor yapısı |
| `hooks/engine/` | Python motoru: `main.py` (giriş), `modules/` (guard, audit, stop, utils, config) |
| `bmad/` | eski `_bmad/` modül verisi (bmm, cis, gds, wds, tea, core, bmb) |
| `templates/` | IR/SP/QR/PR/S/E/README/tech-debt kayıt şablonları |
| `commands/` | `/metodoloji:init`, `/metodoloji:kapi-kur`, `/metodoloji:dogrula`, `/metodoloji:denetim` |

## Kurulum

```python
from openhands.sdk.plugin import Plugin
p = Plugin.load("github:yunusgungor/metodoloji", repo_path="openhands/metodoloji")
```

veya yerel: `Plugin.load("<repo>/openhands/metodoloji")`.

İlk oturumda: `/metodoloji:init` (şablonları kurar) ve `/metodoloji:kapi-kur`
(`~/.bmad/gate-key` üretir — makine-yerel, commit edilmez).

## Yol değişkenleri

- `{project-root}` — hedef proje kökü (kayıtlar burada)
- `{metodoloji-root}` — bu plugin'in kökü (kuruluysa `~/.openhands/plugins/installed/metodoloji`,
  bootstrap ile `.metodoloji/plugin` senkronu)

## Modüler Motor Yapısı

```
hooks/engine/
├── main.py              # Ana giriş noktası
├── modules/
│   ├── __init__.py      # Modül ihracatları
│   ├── config.py        # Sabit yapılandırma
│   ├── utils.py         # Yardımcı fonksiyonlar
│   ├── archive.py       # Arşiv işleme (tar/zip)
│   ├── bash_targets.py  # Bash komut hedef tespiti
│   ├── guard.py         # PreToolUse mantığı
│   ├── audit.py         # PostToolUse denetim izi
│   └── stop.py          # Stop mantığı
└── resolve_customization.py  # Skill TOML deep_merge köprü çözücüsü
```

## Sağlık kontrolü

```sh
sh commands/check-plugin.sh            # tam denetim (§0–§6 + §2b + §5b + §5c + drift)
sh commands/check-plugin.sh --negtest  # negatif test: KÖPRÜ boz → yakala → geri yükle
sh commands/check-custom.sh            # sadece custom/ statik kalite denetimi (§0–§6)
```

## Doğruluk kaynağı ve drift

Hook motorunun canonical kopyası bu repo'nun `hooks/engine/` ağacıdır (modüler motor:
`main.py` + `modules/`). Kurulu plugin kopyası repo ile aynı olmalı — `check-plugin.sh`
§5 bütünlüğü denetler. Değişiklik her zaman repoda yapılır, kurulu plugin `git pull`
ile güncellenir (eski tek-dosya `bmad-hooks.py` kaldırılmıştır; referans vermeyin).

## Hard gate

OpenHands runtime'da denetim zinciri **beş** hook noktasından çalışır (hooks.json):

| Hook | Mod | Matcher | Eşik | Davranış |
|------|-----|---------|------|----------|
| **guard** | PreToolUse | file_editor, terminal | — | Deney onaysız kod yazımı → DENY (fail-closed) |
| **quality** | PreToolUse | terminal | — | `git commit` IR/QR/SP'siz story varsa → DENY (fail-closed) |
| **deploy** | PreToolUse | terminal | — | Deploy komutu + IR/QR/SP/PR eksikse → DENY (fail-closed) |
| **stop** | Stop | — | — | Tamamlanmamış story/onaysız kod → DENY (fail-closed) |
| **audit** | PostToolUse | file_editor, terminal | — | Her çağrıyı log'a yazar (fail-open) |

`custom/config.toml [hooks]` altındaki `quality_gate`/`deploy_guard` (`"soft"` varsayılan |
`"hard"`) değerleri artık hook seviyesinde zorlanır: guard/stop kalitesiz commit/deploy'i
mekanik olarak engeller.

## Durum

Kurulum/yol katmanı birleşti; canlı akış (ilk E→IR→SP→S→QR üretimi gerçek LLM
oturumunda) kanıtlanmadan "tam birleşti" denmez. Kapanış kapısı: Faz 8.
