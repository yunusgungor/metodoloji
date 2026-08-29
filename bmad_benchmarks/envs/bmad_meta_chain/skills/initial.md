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
| **E** (Deney) | `docs/experiments/E-XXX.md` | planlandı → ONAYLANDI \| REDDEDİLDİ |
| **IR** | `docs/development/IR-XXX.md` | HAZIR \| EKSİK |
| **SP** | `docs/development/SP-XXX.md` | planlandı \| devam ediyor \| tamamlandı \| iptal |
| **S** (Story) | `docs/development/stories/S-XXX.md` | backlog \| sprint \| in-progress \| review \| done \| blocked |
| **QR** | `docs/quality/QR-XXX.md` | pass \| fail \| partial |
| **PR** | `docs/development/PR-XXX.md` | HAZIR \| BEKLİYOR |

## Chain Prerequisites

- **IR** olmadan **Sprint Planning** başlatılamaz (Kapı 1)
- **QR** olmadan story `done` kabul edilemez (Kapı 3)
- **PR** olmadan deploy yapılamaz (Kapı 4)
- Her onaylı geçiş git commit ile kalıcı kayıt altına alınır
- Story, QR ve PR çıktılarında Deney Onayı alanı zorunludur

## Output

State the record type, its exact path (e.g. `docs/quality/QR-XXX.md`), and its allowed status values.
