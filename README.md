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
└── bmad-hooks.py        # Eski tek-dosya motor (geriye dönük uyumluluk)
```

## Sağlık kontrolü

```sh
sh commands/check-plugin.sh            # tam denetim (§0–§6 + §2b + §5b + drift)
sh commands/check-plugin.sh --negtest  # negatif test: KÖPRÜ boz → yakala → geri yükle
```

## Doğruluk kaynağı ve drift

Hook motorunun canonical kopyası metodoloji reposunda `.claude/helpers/bmad-hooks.py`'dir.
Plugin'deki `hooks/engine/bmad-hooks.py` bu dosyayla birebir aynı olmalı — `check-plugin.sh`
§5 drift'i denetler. Değişiklik her zaman canonical'da yapılır, sonra kopyalanır:

```sh
python3 .claude/helpers/bmad-hooks.py --selfcheck && \
cp .claude/helpers/bmad-hooks.py openhands/metodoloji/hooks/engine/bmad-hooks.py
```

## Hard gate

`custom/config.toml [hooks]` altında `quality_gate`/`deploy_guard` = `"soft"` (varsayılan) |
`"hard"`. Hard moda ancak ilk gerçek IR/SP/QR/PR kayıtları üretildikten sonra geçin —
yoksa her commit/push/deploy mekanik bloklanır.

## Durum

Kurulum/yol katmanı birleşti; canlı akış (ilk E→IR→SP→S→QR üretimi gerçek LLM
oturumunda) kanıtlanmadan "tam birleşti" denmez. Kapanış kapısı: Faz 8.
