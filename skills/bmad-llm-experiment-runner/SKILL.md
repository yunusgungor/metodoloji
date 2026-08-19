---
name: bmad-llm-experiment-runner
description: 'Run the full graph-engineering experiment loop end to end — Teori → Hipotez → Deney → Ölçüm → Kapı → Kod → Benchmark → Commit → Memory/Rapor. Use when the user wants to add a new graph-engineering capability, run the next experiment, continue the LLM-integration series, or says "sıradaki doğru adımla devam edelim".'
triggers: ["bmad-llm-experiment-runner", "/bmad-llm-experiment-runner", "llm-experiment-runner", "sıradaki doğru adımla devam edelim"]
---

## Metodoloji

Bu yuzey arastirma metodolojisine baglidir: `docs/bmad/research-methodology.md` — Mod A (sayisal) — deney dongusu; E-id kaydi.
Belgesel karar kod yazma izni degildir; kod her durumda Mod A mekanik onayini ister
(run_experiment.py --verify + guard-code.sh). Uydurma kanit/olcum sahtekarliktir.


# LLM Experiment Runner

**Goal:** Execute the project's experiment pattern **in full, every time** — from theory to committed code with a verified gate token, memory + report updated. This skill wraps the mechanical gate of `bmad-research-experiment` and adds the delivery loop this project has been running (E-094..E-150): one falsifiable experiment per commit, production code + bench script, `--verify` before code, commit per experiment, and memory/R-002/sprint-status/cli.py kept current.

**Your Role:** You are the research-and-delivery engineer. You keep the pattern intact: never write code without a measured, verified experiment; never commit a half-finished cycle; never let the docs drift from the code.

## Why this skill exists (the pattern to preserve)

This project runs a **per-experiment delivery loop**. Each capability is born as a
falsifiable experiment, measured against a production surface, gated by a
mechanical token, and shipped as one commit. Preserve this — it is the whole point.

```
Teori → Hipotez → Deney tasarımı   (docs/experiments/E-NNN.md, durum: planlandı)
  → Ölçüm (production surface + scratch/bench_*.py)
  → Kapı (run_experiment.py --record)        → GATE-OK-... token
  → --verify                                → VERIFIED, code may proceed
  → Kod (production module in lib/graph/)    → implementation
  → Benchmark yeniden doğrula                 → measured=1.00
  → Commit (one experiment per commit)
  → Memory + R-002 + sprint-status + cli.py token listesi güncelle
```

## Conventions

- `{project-root}` = the repo root (the directory containing `.git/` and `bmad/`).
- `{gate-script}` = `{metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py`.
- Experiment records live at `docs/experiments/E-NNN.md`, Turkish field labels.
- Benches live at `scratch/bench_*.py`, production code under `lib/graph/`.
- Records/research/memory are written in Turkish; code docstrings in English.

## The mandatory loop (execute in order)

### 1. Pick the next experiment

- The next number is the highest existing `E-NNN` + 1. Check `docs/experiments/`.
- A capability is a good next experiment when it (a) maps to a PDF claim or an
  existing surface's gap, (b) is falsifiable (a broken implementation scores
  below the threshold), (c) is one coherent commit.
- For the LLM-integration series: the next experiment chains the existing
  `llm_*` functions onto another production surface.

### 2. Write the record (durum: planlandı)

Create `docs/experiments/E-NNN.md` with Turkish fields, exactly as the gate
parses them:

```
## Deney: E-NNN — <kısa başlık> (<alt deneyler / PDF bölümü>)
- **Tarih:** <GG.AA.YYYY>
- **Durum:** planlandı
- **Teori:** <hangi PDF iddiası / hangi mevcut yüzeyin boşluğu — "merak ettim" yetmez>
- **Hipotez:** H-NNN: "metrik >= 0.90"
- **Ölçüm metrikleri:** metrik = doğru kontrol / toplam kontrol. Bir kontrol doğru: ...
  Eşik: >= 0.90. Yanlışlanabilir: <bozuk uygulama ne yapar ve neden düşük puanlar>
- **Deney tasarımı:** <üretim yüzeyi + kontrol listesi + ölçüm betiği yolu>
- **Örneklem n:** <opsiyonel — örneklem büyüklüğü; yoksa kapı "n bilinmiyor" uyarısı yazar>
- **Ham sonuçlar:** <ölçüm — kapı yazar>
- **Belirsizlik:** <kapı yazar: örneklem küçük | yok | n bilinmiyor>
- **Metrik:** <kapı yazar: uyumlu | UYUMSUZ | n/a>
- **Karar:** <kapı yazar: ONAYLANDI | REDDEDİLDİ — gerekçe>
- **Kapı kanıtı:** <kapı yazar: GATE-OK-...>
- **Sonraki adım:** <kapı yazar: Kod'a geç | Teori'ye dön>
```

Leave `Karar`/`Kapı kanıtı`/`Sonraki adım`/`Durum`/`Ham sonuçlar`/`Belirsizlik`/`Metrik` to the gate — it writes them.

### 3. Implement the production surface + bench

- Add the function/class to the production module (`lib/graph/pipeline.py` or
  the appropriate module) with a docstring naming the experiment:
  `Deney E-NNN: docs/experiments/E-NNN.md (H-NNN: ... >= 0.90) -> GATE-OK-E-NNN-`
  (leave the hash empty until the gate runs; fill it in after).
- Write `scratch/bench_<name>.py` that exercises the PRODUCTION surface,
  prints `metric_accuracy=0.93 (14/15)`-style output (value + `(x/y)` count),
  and asserts `>= 0.90`. Falsifiability: the bench must fail on a broken
  implementation.
- For live-LLM experiments: use the local gateway env
  (`OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL=http://localhost:20128/v1`,
  `OPENROUTER_MODEL=cmc/deepseek/deepseek-v4-flash`), add `(x/y)` counts, and
  be resilient to the LLM's non-determinism (see lessons below).

### 4. Measure, gate, verify

```bash
# measure (must print metric_accuracy=0.93 (14/15))
PYTHONIOENCODING=utf-8 python scratch/bench_<name>.py

# gate — the gate runs the bench itself and parses value + metric + (x/y) from output
python {gate-script} --record docs/experiments/E-NNN.md --run "<command>" --raw "..."
# preview WITHOUT deciding (format/draft checks — NEVER "check" with --run
# alone: it writes a real decision into the record, E-189 lesson)
python {gate-script} --record docs/experiments/E-NNN.md --run "<command>" --dry-run

# verify BEFORE code
python {gate-script} --verify --record docs/experiments/E-NNN.md
```

`VERIFIED` unlocks code. `FORGED`/`REDDEDİLDİ` → no code; revise the theory and
open a new record. A decided record refuses a re-run.

### 5. Finalize the production code + docs

- Fill the `GATE-OK-E-NNN-<hash>` into the production docstring.
- Append the experiment to `cli.py`'s Verified Tokens banner (both the
  `E-XXX (hash)` list and the `| E-XXX` list).
- Append a one-line entry to `_bmad-output/implementation-artifacts/sprint-status.yaml`
  (same style as the existing `E-NNN ...` entries).
- If it closes a PDF gap / research direction, add a row to the R-002 table
  and update the closing paragraph + experiment count.

### 6. Commit (one experiment per commit)

```
git add -A && git commit -m "Add <feature> (E-NNN) — <PDF claim / one-line>

<2-4 lines: what was added, measured value + token, what a broken impl would do>.

Measured: <metric>=1.00 (4/4), GATE-OK-E-NNN-<hash> (verified).
A <broken integration> would <fail how> -> falsifiable.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
"
```

### 7. Update memory

After committing, update `ge-dre-project-state.md` (the project memory file
under `progress/`, the WDS memory backend): add the new `llm_*`/capability to the
direction list, bump the experiment count + latest commit hash, and record any
new live-LLM lesson.

## Live-LLM lessons (learned the hard way — E-125..E-150)

These recur; handle them up front so the bench is stable:

1. **Temporal schema (valid_at) makes the LLM return EMPTY output.** Ask the LLM
   for S-P-O only; parse dates deterministically from the text (`_parse_valid_at`).
2. **Non-deterministic predicates**: "was CEO of" vs "became CEO of" are the same
   attribute — normalize to `(company, role, person)` and dedupe `norm_claims`.
3. **Non-deterministic JSON**: retry `llm_extract_graph` 4x (long chains multiply
   the flake probability). Benchmarks that query the LLM's output must use the
   LLM's ACTUAL output, not a hardcoded predicate.
4. **Code/tool prompts drift to tool-call XML** instead of JSON — add
   "Do NOT call any tools and do NOT use XML" to the prompt.
5. **Rate/bundle limits**: live calls consume real quota — gate with RateLimiter
   (E-148) and bundle_allowed (E-149).
6. **Consistency**: the pipeline's DECISIONS (fact/superseded) must not flip
   across runs even when the LLM is non-deterministic (E-135). If a bench is
   flaky, retry, don't weaken the assert.
7. **`kg.claims` is subject-keyed** — the subject is the dict KEY, not a field.
   Access via `claims.items()`.
8. **`SwarmReducer.reduce` needs hashable tuples**, not relation dicts.

## Integrity rules (inherited — non-negotiable)

1. No measurement, no gate; no gate approval, no code.
2. Never fabricate a measurement; never hide a negative result; report honestly.
3. A broken implementation must score below the threshold (falsifiability).
4. One measurement, one decision per record; a decided record refuses a re-run.
5. If data contradicts the theory, revise the THEORY (new record), never the data.
6. Every experiment ships as one commit with its docs; no half-finished cycles.