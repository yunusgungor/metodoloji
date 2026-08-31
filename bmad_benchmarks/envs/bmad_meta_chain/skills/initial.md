# Methodology Record Chain

You identify the correct methodology record for a stage in the BMAD record chain, its exact path, and its allowed status values.

## The Record Chain (§1.1)

```
Experiment (E) → Implementation Readiness (IR) → Sprint Planning (SP) → Story (S) → Quality Record (QR) → Production Readiness (PR)
```

Each stage depends on the previous one. Every link requires approval.

## Records, Paths, and Status Values (§11.2)

| Record | Path | Allowed Status Values |
|--------|------|-----------------------|
| **E** (Experiment) | `docs/experiments/E-XXX.md` | planned → APPROVED \| REJECTED |
| **IR** | `docs/development/IR-XXX.md` | READY \| INCOMPLETE |
| **SP** | `docs/development/SP-XXX.md` | planned \| in-progress \| completed \| cancelled |
| **S** (Story) | `docs/development/stories/S-XXX.md` | backlog \| sprint \| in-progress \| review \| done \| blocked |
| **QR** | `docs/quality/QR-XXX.md` | pass \| fail \| partial |
| **PR** | `docs/development/PR-XXX.md` | READY \| WAITING |

## Chain Prerequisites

- **Sprint Planning** cannot start without **IR** (Gate 1)
- A story cannot be accepted as `done` without **QR** (Gate 3)
- Deploy cannot happen without **PR** (Gate 4)
- Every approved transition is recorded permanently with a git commit
- The Experiment Approval field is mandatory in Story, QR, and PR outputs

## Output

State the record type, its exact path (e.g. `docs/quality/QR-XXX.md`), and its allowed status values.
