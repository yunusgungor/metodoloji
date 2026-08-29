# Methodology Record Paths

You state the exact path where each methodology record must be created.

## Record → Path Mapping (§11.2)

| Record | Path (under `{project-root}`) | Allowed Status |
|--------|-------------------------------|----------------|
| **E** (Deney) | `docs/experiments/E-XXX.md` | planlandı → ONAYLANDI \| REDDEDİLDİ |
| **IR** | `docs/development/IR-XXX.md` | HAZIR \| EKSİK |
| **SP** | `docs/development/SP-XXX.md` | planlandı \| devam ediyor \| tamamlandı \| iptal |
| **S** (Story) | `docs/development/stories/S-XXX.md` | backlog \| sprint \| in-progress \| review \| done \| blocked |
| **QR** | `docs/quality/QR-XXX.md` | pass \| fail \| partial |
| **PR** | `docs/development/PR-XXX.md` | HAZIR \| BEKLİYOR |

## Root Rules

- **All record outputs** → `{project-root}` (hedef proje). Plugin'e asla.
- **Templates/config** → read from `{metodoloji-root}` (plugin).

## Key Distinctions

- QR lives in `docs/quality/` — NOT `docs/development/`
- Story records live in `docs/development/stories/` (subfolder)
- Experiments live in `docs/experiments/` (not under development/)

## Output

State the full path with the correct root prefix and the allowed status values.
