# Experiment Record Template (Mode A — Quantitative / Empirical, MECHANICAL GATE)

Copy this file for a new experiment: `docs/experiments/E-NNN.md`

This template is for **Mode A (quantitative/empirical)** — the only legitimate path
to code production. For documentary modes: Mode B (qualitative) and Mode D (contextual)
→ `docs/research/_template.md`; Mode C (design) → `docs/design/_template.md`.
Manifesto: `docs/bmad/research-methodology.md`.

English field labels are **mandatory** — the gate (`run_experiment.py`) parses these
labels. Do **not** hand-write the `Decision`, `Gate Evidence`, `Next Step`, `Status`
lines; the gate writes them.

```markdown
## Experiment: E-NNN — <short title>
- **Date:** <DD.MM.YYYY>
- **Status:** planned
- **Theory:** <which theory/framework this comes from — "I was curious" is not enough>
- **Hypothesis:** H-NNN: "metric >= threshold"   <!-- e.g. H-001: "accuracy >= 0.90" -->
- **Measurement Metrics:** <metric name + threshold, unitless numeric>  <!-- e.g. accuracy >= 0.90 -->
- **Experiment Design:** <inputs, procedure, control variables, reproducibility>
- **Sample Size n:** <sample size — the gate parses the denominator (x/y) from the measurement output; this field is informational>
- **Code Scope:** <glob patterns of files this approval opens, comma/space separated; e.g. src/** , lib/engine/*.py>
  <!-- "none" = experiment that produces no code. Writes to files outside scope are blocked by the guard. -->
- **Raw Results:** <measurement — the gate writes this>
- **Uncertainty:** <gate writes: small sample | none | n unknown>
- **Metric:** <gate writes: consistent | MISMATCH — from the measured metric of the --run output>
- **Decision:** <gate writes: APPROVED | REJECTED — reason>
- **Gate Evidence:** <gate writes: GATE-OK-...>
- **Next Step:** <gate writes: Proceed to Code | Return to Theory>
```

## Set up the gate key (once per machine)

```bash
python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py --init-secret
# Key is written to ~/.bmad/gate-key (OUTSIDE the repo). Check:
python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py --check-secret
```

## Run the gate

```bash
# The gate runs the measurement itself: value + metric name + denominator (x/y)
# are parsed from the output. No operator-declared numbers (--measured removed —
# reality is mechanical).
# The measurement script must live in a protected area: scripts under scratch/
# are rejected with --run (e.g. use scripts/bench/).
python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py \
  --record docs/experiments/E-NNN.md --run "python scripts/bench/bench_xxx.py"
# Dry-run: preview the decision WITHOUT writing (format/record check — never use
# --run alone for "checking", it would decide the record by mistake)
python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py \
  --record docs/experiments/E-NNN.md --run "python scripts/bench/bench_xxx.py" --dry-run
```

## Verify before code

```bash
python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py \
  --verify --record docs/experiments/E-NNN.md
```

Keep raw data files under `docs/experiments/E-NNN/raw/`.
