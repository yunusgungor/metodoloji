---
name: wds-8-product-evolution
description: "Brownfield improvements — the full WDS pipeline in miniature for existing products"
triggers: ["wds-8-product-evolution", "/wds-8-product-evolution"]
---

## Metodoloji

Bu yuzey arastirma metodolojisine baglidir: `docs/bmad/research-methodology.md` — Mod B+C (nitel/tasarim) — brownfield urun evrimi, tam WDS boru hatti minyaturu; R-id/D-id kaydi.
Belgesel karar kod yazma izni degildir; kod her durumda Mod A mekanik onayini ister
(run_experiment.py --verify + guard-code.sh). Uydurma kanit/olcum sahtekarliktir.


Follow the instructions in ./workflow.md.

## Customization

Load this skill's effective configuration before acting (three-layer merge:
skill `customize.toml` ← team `custom/<skill>.toml` ← personal
`custom/<skill>.user.toml`):

Run: `python3 {metodoloji-root}/hooks/engine/resolve_customization.py --skill {skill-root} --key workflow`
