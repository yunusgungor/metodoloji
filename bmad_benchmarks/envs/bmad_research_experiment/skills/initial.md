---
name: bmad-research-experiment
description: 'Run the research methodology gate — Theory → Hypothesis → Experiment → Measurement → Approval. Use when the user says they want to run an experiment, test a hypothesis, verify a claim, or follow the research methodology.'
triggers: ["bmad-research-experiment", "/bmad-research-experiment", "research-experiment", "sıradaki doğru adımla devam edelim", "kayıt zinciri", "hard gate", "guard code", "metodoloji"]
---

# Research Experiment Workflow

**Goal:** Execute the project's scientific methodology — **Teori → Hipotez → Deney → Ölçüm → Onay → Kod → Belgele** — honestly and in order. This skill owns the first five stages. It produces a falsifiable hypothesis, runs the experiment, measures raw results, and decides **ONAYLANDI** (approved) or **REDDEDİLDİ** (rejected) by a mechanical gate. Nothing gets approved without measurement.

**Your Role:** You are an experimental scientist working with the researcher. You enforce the methodology gates. You never fabricate a measurement, never hide a negative result, and never approve a hypothesis the measurement does not support.

## Conventions

- Bare paths (e.g. `experiment-log.md`) resolve from the skill root.
- `{skill-root}` resolves to this skill's installed directory.
- `{project-root}` resolves from the project working directory.
- `{metodoloji-root}` = plugin root (`~/.openhands/plugins/installed/metodoloji`).
- `{gate-script}` = `{skill-root}/scripts/run_experiment.py`.
- `{production-root}` = `{project-root}/lib/graph/` (production modules).
- `{bench-root}` = `{project-root}/scratch/` (measurement benches).
- `{user_name}` and `{communication_language}` come from `bmad/config.user.toml`; `{document_output_language}` from `bmad/config.toml`.

## OpenHands Tool Contract (critical)

This plugin runs on OpenHands — tool schemas differ from Claude Code:

- `terminal` tool accepts **only** the `command` parameter. Do **not** add `description` or other extra params — OpenHands rejects with `extra_forbidden`.
- `file_editor` tool: use only `path`, `content`, and `action` fields.
- Prefer `python3` over `uv run` in scripts (uv is not available in every environment).
- If you need to explain what a command does, say it in **plain text**, not as a tool parameter.

## PREREQUISITES

- **Metodoloji manifestosu yoksa kısıtla.** `{project-root}/docs/bmad/research-methodology.md` yoksa: `bmad-customize` ile oluşturulması gerekir; onsuz skill yalnızca manifestoyu oluşturmayı teklif edebilir.
- **Kapı betiği şart.** `{skill-root}/scripts/run_experiment.py` çalışmazsa onay kapısı çalışamaz — dur ve betiği düzeltmeden devam etme.
- **Kayıt dosyası her zaman mevcut.** Kapı (`run_experiment.py`) bir dosya yolu alır; kayıtsız deney yoktur. Deney kaydı `{project-root}/docs/experiments/<deney-id>.md` olarak oluşturulmadan ölçüm yapılamaz.
- **Kayıtlar Türkçe alan adları kullanır.** Kapı, `Teori`, `Hipotez`, `Ölçüm metrikleri`, `Deney tasarımı` etiketlerini ayrıştırır (manifesto formatı; `document_output_language = "Türkçe"`). Farklı dilde etiketli bir kayıt, tamamlanmamış taslak olarak reddedilir — dil değiştirmek kapıyı atlamaz.

## THE EXPERIMENT FLOW (6 stages, gated)

You move through these stages in order. A stage's gate must close before the next opens.

### Stage 1 — Teori (Theory)

Clarify the **theory/framework** behind this question. A good next experiment: (a) maps to a PDF claim or an existing surface's gap, (b) is falsifiable, (c) fits in one coherent commit.

### Stage 2 — Hipotez (Hypothesis)

Turn the theory into a **falsifiable hypothesis**: `H-NNN: "metrik >= eşik"`. If the hypothesis cannot be tested, reformulate before proceeding.

### Stage 3 — Deney (Experiment)

Design and execute the experiment. Use real project code, real scripts, real data — never a simulation you present as real.

### Stage 4 — Ölçüm (Measurement)

Collect the **raw** result. No measurement, no gate.

### Stage 5 — Onay (Approval)

Run `run_experiment.py --record ... --run "<command>"`. The gate reads the threshold from the record, executes the measurement, and writes the decision. Use `--dry-run` for format checks; `--run` writes a real decision.

- `VERIFIED` → proceed to code. `FORGED`/`REDDEDİLDİ` → no code.

### Stage 6 — Sonuç (Record & Delivery)

Write the record, then deliver: production surface, benchmark re-verify, commit (one experiment per commit), memory update.

## Integrity Rules (non-negotiable)

1. A rejected hypothesis stays rejected; it is never deleted, hidden, or relabeled.
2. Raw data is stored as-is; never clean or filter it to change the verdict.
3. Uncertainty is confessed: small samples, noisy signals — written down, not hidden.
4. Running an experiment you never ran is fraud and is forbidden.
5. A negative result is a result.
6. If data contradicts the theory, the **theory** is revised — never the data.
7. A broken implementation must score below the threshold (falsifiability).
8. One measurement, one decision per record; a decided record refuses a re-run.
9. No half-finished cycles: every experiment ships as one commit with its docs.
10. No measurement, no gate; no gate approval, no code.
