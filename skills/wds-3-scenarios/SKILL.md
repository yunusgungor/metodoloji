---
name: wds-3-scenarios
description: "Create UX scenario outlines from Trigger Map through structured micro-steps"
triggers: ["wds-3-scenarios", "/wds-3-scenarios"]
---

## Metodoloji

Bu yuzey arastirma metodolojisine baglidir: `docs/bmad/research-methodology.md` — Mod B (nitel) — senaryolar; R-id kaydi.
Belgesel karar kod yazma izni degildir; kod her durumda Mod A mekanik onayini ister
(run_experiment.py --verify + guard-code.sh). Uydurma kanit/olcum sahtekarliktir.


Follow the instructions in ./workflow.md.

## Customization

Load this skill's effective configuration before acting (three-layer merge:
skill `customize.toml` ← team `custom/<skill>.toml` ← personal
`custom/<skill>.user.toml`):

Run: `python3 {metodoloji-root}/hooks/engine/resolve_customization.py --skill {skill-root} --key workflow`
