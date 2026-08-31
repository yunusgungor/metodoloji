# Methodology Record Paths

You state the exact path where each methodology record must be created.

## Record → Path Mapping (§11.2)

| Record | Path (under `{project-root}`) | Allowed Status |
|--------|-------------------------------|----------------|
| **E** (Experiment) | `docs/experiments/E-XXX.md` | planned → APPROVED \| REJECTED |
| **IR** | `docs/development/IR-XXX.md` | READY \| INCOMPLETE |
| **SP** | `docs/development/SP-XXX.md` | planned \| in-progress \| completed \| cancelled |
| **S** (Story) | `docs/development/stories/S-XXX.md` | backlog \| sprint \| in-progress \| review \| done \| blocked |
| **QR** | `docs/quality/QR-XXX.md` | pass \| fail \| partial |
| **PR** | `docs/development/PR-XXX.md` | READY \| WAITING |

## Root Rules

- **All record outputs** → `{project-root}` (target project). Never the plugin.
- **Templates/config** → read from `{metodoloji-root}` (plugin).

## Key Distinctions

- QR lives in `docs/quality/` — NOT `docs/development/`
- Story records live in `docs/development/stories/` (subfolder)
- Experiments live in `docs/experiments/` (not under development/)

## Output

State the full path with the correct root prefix and the allowed status values.
