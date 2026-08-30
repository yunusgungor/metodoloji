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

- **Metodoloji manifestosu yoksa kısıtla.** `{project-root}/docs/bmad/research-methodology.md` yoksa:
  `bmad-customize` ile oluşturulması gerekir; onsuz skill yalnızca manifestoyu oluşturmayı teklif edebilir.
- **Kapı betiği şart.** `{skill-root}/scripts/run_experiment.py` çalışmazsa onay kapısı çalışamaz — dur ve betiği düzeltmeden devam etme.
- **Kayıt dosyası her zaman mevcut.** Kapı (`run_experiment.py`) bir dosya yolu alır; kayıtsız deney yoktur. Deney kaydı `{project-root}/docs/experiments/<deney-id>.md` olarak oluşturulmadan ölçüm yapılamaz.
- **Kayıtlar Türkçe alan adları kullanır.** Kapı, `Teori`, `Hipotez`, `Ölçüm metrikleri`, `Deney tasarımı` etiketlerini ayrıştırır (manifesto formatı; `document_output_language = "Türkçe"`). Farklı dilde etiketli bir kayıt, tamamlanmamış taslak olarak reddedilir — dil değiştirmek kapıyı atlamaz.

## On Activation

### Step 1: Resolve the Workflow Block

Run: `python3 {metodoloji-root}/hooks/engine/resolve_customization.py --skill {skill-root} --key workflow` — OpenHands terminal tool yalnızca command parametresi alır; description EKLEME

**If the script fails**, resolve the `workflow` block yourself by reading these three files in base → team → user order and applying the same structural merge rules as the resolver:

1. `{skill-root}/customize.toml` — defaults
2. `{metodoloji-root}/custom/{skill-name}.toml` — team overrides
3. `{metodoloji-root}/custom/{skill-name}.user.toml` — personal overrides

Any missing file is skipped. Scalars override, tables deep-merge, arrays of tables keyed by `code`/`id` replace matching entries and append new entries, all other arrays append.

### Step 2: Execute Prepend Steps

Execute each entry in `{workflow.activation_steps_prepend}` in order.

### Step 3: Load Persistent Facts

Treat every entry in `{workflow.persistent_facts}` as foundational context. Entries prefixed `file:` are paths/globs under `{project-root}` — load the referenced contents as facts. The methodology manifesto (`docs/bmad/research-methodology.md`) is the most important fact of this skill: **read it fully before proceeding.**

### Step 4: Load Config

Load config from `{metodoloji-root}/bmad/config.toml` and `{metodoloji-root}/bmad/config.user.toml`. Use `{user_name}`, `{communication_language}`, `{document_output_language}`, and `{project-root}`.

### Step 5: Greet the User

Greet `{user_name}` in `{communication_language}`.

### Step 6: Execute Append Steps

Execute each entry in `{workflow.activation_steps_append}` in order.

Activation is complete. If prepend/append steps were non-empty, confirm every entry was executed in order before starting the experiment. **Do not begin the experiment until the manifesto is loaded.**

## THE EXPERIMENT FLOW (6 stages, gated)

You move through these stages in order. A stage's gate must close before the next opens. Any missing prerequisite is a stop, not a skip.

### Stage 1 — Teori (Theory)

Clarify with the researcher the **theory/framework** behind this question:

- Why is this question being asked? What model, framework, or prior evidence motivates it?
- A vague "I'm curious" is not a theory — write down the reasoning that predicts an outcome.
- A good next experiment: (a) maps to a PDF claim or an existing surface's gap, (b) is falsifiable (a broken implementation scores below the threshold), (c) fits in one coherent commit.
- Output: a short theory statement recorded in the experiment log.

### Stage 2 — Hipotez (Hypothesis)

Turn the theory into a **falsifiable hypothesis**:

- Write it as a claim that the experiment can disprove. Include an **eşik değer (threshold)** — the numeric value the measurement must reach for the hypothesis to be supported.
- Assign an id: `H-xxx`.
- **Gate:** If the hypothesis cannot be tested — no measurable output, no threshold — you must reformulate it before proceeding. Do not run an experiment that cannot falsify anything.
- Output: `hipotez` + `ölçüm metrikleri` (metric name + threshold) recorded.

### Stage 3 — Deney (Experiment)

Design the experiment that produces the measurement:

- Inputs, procedure, controlled variables, and how the result is repeatable.
- **Gate:** The design must guarantee a measurable output that the threshold can be checked against. If not, revise the design.
- Output: `deney tasarımı` recorded, then **execute** the experiment. Use the real project code, real scripts, real data — never a simulation you present as real.

### Stage 4 — Ölçüm (Measurement)

Collect the **raw** result:

- Capture the numbers/outputs/logs exactly as produced. Store raw artifacts under `docs/experiments/<deney-id>/raw/`.
- **Gate:** No measurement, no gate. If the experiment produced nothing measurable, the hypothesis is not supported — that is a FAIL, not a do-over.
- Output: the raw measured value is handed to the gate (Stage 5), which writes `Ham sonuçlar` into the record. The record is the single home of both the measurement and the decision.

### Stage 5 — Onay (Approval) — THE RECORD-BOUND MECHANICAL GATE

The gate reads the hypothesis threshold **from the experiment record** — it is
never taken from the command line, so it cannot be silently changed. The gate
is the **only** writer of the decision. Run it against the record file.

**The gate runs the measurement itself — there is no other path.** Give the gate
the command that produces the measurement; it executes it and parses the measured
value from the run's own output. The number written into the record is therefore
the number the run actually produced — "denemiş gibi gösterme" (rule 5) becomes a
mechanical guarantee, not a trust claim. **`--measured` was removed**: the gate
does not trust an operator-supplied value, so a measurement it did not run cannot
produce an approval:

```
python3 {skill-root}/scripts/run_experiment.py --record {project-root}/docs/experiments/<deney-id>.md --run "<ölçüm komutu>"
```

For format/draft checks without writing a decision, use `--dry-run` (see below). For adding supplementary metadata to the record, use `--raw "key=value"` pairs.

The measurement command must print a `metric_accuracy=0.93 (14/15)`-style line
(`_accuracy`/`_validity`/`_precision`/`_score`/`_rate`/`_quality`); the gate
parses the value, the metric stem, **and the `(x/y)` sample-size denominator**
from it. The `(x/y)` denominator is **required**: a bench that prints
only a value (no count) is rejected with exit 2 and leaves the record untouched —
otherwise a small real sample could hide behind `n bilinmiyor` and bypass the
`ADVISORY-BLOCK` rule-4 enforcement. If the
command exits non-zero, times out, or prints no parseable value, the gate
refuses with exit code 2 and **leaves the record untouched**.

**Dry-run preview — never decide a record by accident.** Passing `--dry-run`
computes the full decision — parsed claim/threshold, measured
value, PASS/FAIL, Wilson bound, the `Belirsizlik`/`Metrik`/`Karar`/`Kapı kanıtı`
lines, and the would-be `GATE-OK-...` token — and prints it **without writing
anything** to the record (exit 0). Use `--dry-run` for every format/draft check:
a `--run` "format check" without it WRITES a real decision into the record
(E-189 lesson — a fabricated approval token was once written this way and had
to be reverted).

**Sample size is mechanically confessed (rule 4).** The gate computes the 95%
Wilson score lower bound for the observed `x/n` and writes a `Belirsizlik`
(uncertainty) line into the record — `örneklem küçük` when the sample is too
small for the threshold, `yok` when it clears, or `n bilinmiyor` when no
denominator was printed. This is **advisory, not a rejection**: a small sample
does not change the verdict, but the record now honestly confesses it. Because
the `(x/y)` denominator is mandatory, `n bilinmiyor` cannot be produced by a
new approval (rule-4 gap closed).

**Metric identity is cross-checked.** The gate compares the metric name the run
actually measured (`metric_accuracy=` stem) against the metric named in the
hypothesis claim. A mismatch writes a `Metrik: UYUMSUZ` line into the record —
a different thing was measured than claimed (metric redefinition, E-015 class).
This check runs mechanically on every approval (there is no unverified path).

**But advisory becomes enforceable at verify time.** A record whose
`Belirsizlik` confesses `örneklem küçük` or whose `Metrik` is `UYUMSUZ` returns
`ADVISORY-BLOCK` from `--verify` (exit 2) instead of `VERIFIED` — the approval
is genuine (token valid) but does **not** unlock code. `n bilinmiyor` does not
block (the gate just could not parse a denominator). Fix the experiment before code.

The script reads the threshold from the record's `Hipotez` line (e.g. `H-001: "accuracy >= 0.90"`), compares, and writes the decision into the record:

- `PASS` → record gets `Karar: ONAYLANDI` + `Kapı kanıtı` token (`GATE-OK-...`), `Durum: tamamlandı`, `Sonraki adım: Kod'a geç`. Then Stage 6.
- `FAIL` → record gets `Karar: REDDEDİLDİ` + `Sonraki adım: Teori'ye dön`, `Durum: REDDEDİLDİ`. **Do not pass Go. Do not "adjust" the threshold. Do not re-interpret the raw data to make it pass.** The researcher may revise the theory and open a *new* experiment record — that is the only path forward.
- A decided record refuses a re-run. One measurement, one decision per record. Forcing a new measurement into an approved record is fraud.

**Code may only proceed after a genuine approval.** Before implementing, the dev agent runs:

```
python3 {skill-root}/scripts/run_experiment.py --verify --record {project-root}/docs/experiments/<deney-id>.md
```

`VERIFIED` means the approval is backed by a valid gate token — proceed. `FORGED` (an `ONAYLANDI` record with no valid token) or `REDDEDİLDİ` means **no code**.

**The gate also cross-checks the recorded hypothesis.** `--verify` compares the claim recorded in the record's `Hipotez` field against the claim the gate actually evaluated (stored in `Kapı kanıtı`). Editing the threshold *after* approval and keeping the token is a forged outcome — it fails verify even though the token still matches the (edited) `Kapı kanıtı`. Only the original hypothesis as recorded at Stage 2 verifies.

### Stage 6 — Sonuç (Record & Delivery)

- Write/update `docs/experiments/<deney-id>.md` per `experiment-log.md` (the manifesto's mandatory format).
- Record: theory, hypothesis + threshold, measurement metrics, design, raw results, decision + rationale, next step.
- **Next step is derived from the decision:** ONAYLANDI → proceed to delivery (below); REDDEDİLDİ → "Teori'ye dön; yeni hipotez için yeni deney aç."
- Summarize honestly to the user: what was measured, what the gate decided, and what happens next.

**Delivery loop (ONAYLANDI only):**

1. **Production surface:** Add the function/class to the production module (`{production-root}/pipeline.py` or appropriate module) with a docstring naming the experiment: `Deney E-NNN: docs/experiments/E-NNN.md (H-NNN: ... >= 0.90) -> GATE-OK-E-NNN-` (leave the hash empty until the gate runs; fill it in after).
2. **Benchmark re-verify:** Run the bench again against the production surface to confirm `measured=1.00`. A broken integration must score below the threshold (falsifiability).
3. **Append to cli.py:** Add the experiment to the Verified Tokens banner (both the `E-XXX (hash)` list and the `| E-XXX` list).
4. **Update sprint-status.yaml:** Append a one-line entry to `_bmad-output/implementation-artifacts/sprint-status.yaml` (same style as existing `E-NNN ...` entries).
5. **Update R-002:** If the experiment closes a PDF gap / research direction, add a row to the R-002 table and update the closing paragraph + experiment count.
6. **Commit (one experiment per commit):**

```
git add -A && git commit -m "Add <feature> (E-NNN) — <PDF claim / one-line>

<2-4 lines: what was added, measured value + token, what a broken impl would do>.

Measured: <metric>=1.00 (4/4), GATE-OK-E-NNN-<hash> (verified).
A <broken integration> would <fail how> -> falsifiable.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
"
```

7. **Update memory:** After committing, update the project memory file (e.g. `ge-dre-project-state.md` under `progress/`): add the new capability to the direction list, bump the experiment count + latest commit hash, and record any new lesson learned.

## Integrity Rules (from the manifesto — non-negotiable)

1. A rejected hypothesis stays rejected and is reported; it is never deleted, hidden, or relabeled.
2. Raw data is stored as-is; never clean or filter it to change the verdict.
3. Uncertainty is confessed: small samples, noisy signals, arbitrary thresholds — written down, not hidden.
4. Running an experiment you never ran, or reporting a measurement you never took, is fraud and is forbidden.
5. A negative result is a result.
6. If observed data contradicts the theory, the **theory** is revised — never the data.
7. A broken implementation must score below the threshold (falsifiability). If it doesn't, the test is broken — fix the test, not the threshold.
8. One measurement, one decision per record; a decided record refuses a re-run.
9. No half-finished cycles: every experiment ships as one commit with its docs.
10. No measurement, no gate; no gate approval, no code.

## Live-LLM Lessons (E-125..E-150 — learned the hard way)

These recur when running experiments that call LLMs; handle them up front so the bench is stable:

1. **Temporal schema (valid_at) makes the LLM return EMPTY output.** Ask the LLM for S-P-O only; parse dates deterministically from the text (`_parse_valid_at`).
2. **Non-deterministic predicates**: "was CEO of" vs "became CEO of" are the same attribute — normalize to `(company, role, person)` and dedupe `norm_claims`.
3. **Non-deterministic JSON**: retry `llm_extract_graph` 4x (long chains multiply the flake probability). Benchmarks that query the LLM's output must use the LLM's ACTUAL output, not a hardcoded predicate.
4. **Code/tool prompts drift to tool-call XML** instead of JSON — add "Do NOT call any tools and do NOT use XML" to the prompt.
5. **Rate/bundle limits**: live calls consume real quota — gate with RateLimiter (E-148) and bundle_allowed (E-149).
6. **Consistency**: the pipeline's DECISIONS (fact/superseded) must not flip across runs even when the LLM is non-deterministic (E-135). If a bench is flaky, retry, don't weaken the assert.
7. **`kg.claims` is subject-keyed** — the subject is the dict KEY, not a field. Access via `claims.items()`.
8. **`SwarmReducer.reduce` needs hashable tuples**, not relation dicts.
