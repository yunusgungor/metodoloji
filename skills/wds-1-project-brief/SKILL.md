---
name: wds-1-project-brief
description: "Establish project context - foundation for all design work"
triggers: ["wds-1-project-brief", "/wds-1-project-brief"]
---

## Metodoloji

Bu yuzey arastirma metodolojisine baglidir: `docs/bmad/research-methodology.md` — Mod C (tasarim) — proje ozeti; D-id kaydi.
Belgesel karar kod yazma izni degildir; kod her durumda Mod A mekanik onayini ister
(run_experiment.py --verify + guard-code.sh). Uydurma kanit/olcum sahtekarliktir.


Follow the instructions in ./workflow.md.

## Customization

Load this skill's effective configuration before acting (three-layer merge:
skill `customize.toml` ← team `custom/<skill>.toml` ← personal
`custom/<skill>.user.toml`):

Run: `python3 {metodoloji-root}/hooks/engine/resolve_customization.py --skill {skill-root} --key workflow`
