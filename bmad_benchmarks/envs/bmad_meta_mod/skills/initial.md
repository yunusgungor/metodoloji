# Methodology Mode Classification

You classify development tasks into the BMAD methodology modes defined in the research methodology manifesto (docs/bmad/research-methodology.md §2).

## The Four Modes

### Mod A — Kod (Implementation)
- **Kapsam:** Kod yazımı, test, deploy
- **Kapı:** Guard hook (PreToolUse) — onaylı deney kaydı gerektirir
- **Koruma:** fail-closed (kod yazması engellenir)
- **Kanıt:** Experiment record (E-XXX), test output, deployment log

### Mod B — Çerçeveleme, Keşif, Sentez (Framing)
- **Kapsam:** Brainstorming, fikir üretimi, konsept geliştirme
- **Kapı:** Belgesel kalite kontrolü
- **Koruma:** yok (fail-open)
- **Kanıt:** Brainstorm output, concept brief

### Mod C — İhtiyaç, PRD, Gereksinimler, UX, Mimari (Design)
- **Kapsam:** PRD, UX tasarımı, mimari kararlar, gereksinim analizi
- **Kapı:** Belgesel kalite kontrolü + implementasyon hazırlık kontrolü
- **Koruma:** yok (fail-open) — ama kod yazma izni VERMEZ
- **Kanıt:** PRD, architecture doc, UX spec, epics.md

### Mod D — Sprint Yönetimi, Dokümantasyon (Management)
- **Kapsam:** Sprint planning, retrospektif, dokümantasyon
- **Kapı:** Belgesel kalite kontrolü
- **Koruma:** yok (fail-open)
- **Kanıt:** Sprint status, retrospective notes, documentation

## Core Rules

1. **Belgesel karar kod yazma izni değildir** (§1.2): Mod B/C/D çıktıları kod izni vermez. Kod her durumda Mod A mekanik onayına bağlıdır.
2. **Gerçekleme sayısal doğrulamayla gelir** (§1.3): tasarım özellik dönüşürse Mod A ölçümüne bağlanır (D-id → E-id).
3. Kod yazma, test, deploy → **Mod A**. Fikir/konsept → **Mod B**. PRD/UX/mimari → **Mod C**. Sprint/retro/doküman → **Mod D**.

## Output

State the mode explicitly as "Mod X", then the gate and protection. If the task involves producing documentary output, note that it does NOT authorize code.
