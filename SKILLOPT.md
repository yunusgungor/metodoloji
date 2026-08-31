# SkillOpt Integration — BMAD Skill Tuning

## Overview

This directory contains SkillOpt benchmark definitions for tuning BMAD skills
using reinforcement learning on text-based skill documents — **without
modifying model weights**.

## Benchmarks

| Benchmark | What it tunes | Scoring |
|-----------|---------------|---------|
| `bmad-code-review` | Adversarial code review quality | Finding coverage (categories + severity) |
| `bmad-create-story` | Story file completeness | Section presence + metadata fields |
| `bmad-architecture` | Architecture spine quality | Invariant category coverage |
| `bmad-prd` | PRD completeness | Section coverage |
| `bmad-test-design` | Test plan comprehensiveness | Test category coverage |
| `bmad-custom-ir` | Incident record methodology | Record field completeness |
| `bmad-custom-sp` | Sprint planning methodology | Planning field completeness |
| `bmad-custom-story` | Story methodology | Story field completeness |
| `bmad-custom-qr` | Quality record methodology | Record field completeness |
| `bmad-custom-pr` | Production readiness record | Record field completeness |
| `bmad-meta-mod` | Mod classification (A/B/C/D) | Category + direction accuracy |
| `bmad-meta-chain` | Chain operation sequencing | Sequence correctness |
| `bmad-meta-guard` | Guard rule validation | Rule match accuracy |
| `bmad-meta-root` | Root classification (project vs plugin) | Root + direction accuracy |
| `bmad-meta-path` | Path resolution correctness | Path classification accuracy |
| `bmad-research-experiment` | Experiment methodology | Record completeness |
| `bmad-code-docs` | Code documentation quality | Doc coverage |

## Architecture

```
bmad_benchmarks/envs/
├── _base_/default.yaml              # Shared hyperparameters
├── bmad_code_review/                # adapter.py, dataloader.py, rollout.py, skills/, data/
├── bmad_create_story/
├── bmad_architecture/
├── bmad_prd/
├── bmad_test_design/
├── bmad_custom_ir/                  # Custom TOML methodology benchmarks
├── bmad_custom_sp/
├── bmad_custom_story/
├── bmad_custom_qr/
├── bmad_custom_pr/
├── bmad_meta_mod/                   # docs/bmad meta benchmarks
├── bmad_meta_chain/
├── bmad_meta_guard/
├── bmad_meta_root/
├── bmad_meta_path/
├── bmad_code_docs/
└── bmad_research_experiment/

configs/
├── bmad-code-review/default.yaml    # All configs use structured env: section
├── bmad-create-story/default.yaml   # (see Config Format below)
├── ...                              # One config per benchmark
└── bmad-research-experiment/default.yaml

scripts/
├── train_bmad.py                    # Training entry point
└── eval_bmad.py                     # Evaluation entry point
```

## Quick Start

### 1. Install SkillOpt

```bash
pip install skillopt
# or from source:
git clone https://github.com/microsoft/SkillOpt.git
cd SkillOpt && pip install -e ".[searchqa]"
```

### 2. Set credentials

```bash
cp .env.example .env
# Edit .env with your API keys
set -a; source .env; set +a
```

### 3. Train a single benchmark

```bash
python scripts/train_bmad.py --benchmark bmad-code-review
```

### 4. Train all benchmarks

```bash
python scripts/train_bmad.py --benchmark all
```

### 5. Evaluate trained skills

```bash
python scripts/eval_bmad.py --benchmark bmad-code-review
python scripts/eval_bmad.py --benchmark all
```

### 6. Use trained skill

The best skill is saved at `outputs/<benchmark>/best_skill.md`.
Replace the corresponding `SKILL.md` in `skills/` with the optimized version.

## Config Format

Each benchmark config uses a **structured `env` section**. This keeps
environment-specific settings grouped and allows `apply_overrides` to
correctly patch nested keys via `--cfg-options env.key=value`:

```yaml
_base_: ../../bmad_benchmarks/envs/_base_/default.yaml

model:
  target: cmc/deepseek/deepseek-v4-flash
  optimizer: cmc/deepseek/deepseek-v4-flash

env:
  name: bmad-meta-root                      # adapter registry key
  skill_init: bmad_benchmarks/envs/bmad_meta_root/skills/initial.md
  split_mode: split_dir
  split_dir: bmad_benchmarks/envs/bmad_meta_root/data
  workers: 2
  max_completion_tokens: 4096
  limit: 0
  out_root: outputs/bmad-meta-root

train:
  batch_size: 3
  num_epochs: 3
```

> **Why structured?** A flat `env: bmad-meta-root` string breaks
> `apply_overrides` (it tries `cfg["env"]["name"] = ...` on a string).
> The structured format lets CLI overrides like `--cfg-options
> env.name=new-name` work correctly.

## How It Works

1. **Seed**: Each benchmark starts with a compact `initial.md` extracted from
   the original `SKILL.md` (300-2000 tokens)

2. **Rollout**: The target model executes tasks using the current skill,
   producing outputs (code reviews, stories, architecture spines, etc.)

3. **Scoring**: Each output is scored against expected outcomes:
   - `hard`: 0/1 binary (all expected elements present?)
   - `soft`: [0,1] fraction of expected elements found

4. **Reflection**: The optimizer analyzes trajectories to identify
   what in the skill helped or hurt performance

5. **Update**: Bounded edits (add/delete/replace) are proposed for
   the skill document, gated by a held-out validation score

6. **Gate**: Only edits that improve validation score are accepted

## Training Data Format

Each benchmark uses JSON items with this structure:

```json
{
  "id": "unique-item-id",
  "task_type": "benchmark-type",
  "input fields...": "scenario-specific content",
  "expected_findings": [
    {"category": "...", "severity": "...", "title_keyword": "..."}
  ]
}
```

## Scoring Strategy

| Benchmark | hard criteria | soft criteria |
|-----------|--------------|---------------|
| code-review | All expected finding categories found | Fraction of expected findings present |
| create-story | ≥90% sections + metadata present | Fraction of sections + metadata found |
| architecture | ≥80% invariant categories covered | Fraction of invariant categories found |
| prd | ≥80% sections present | Fraction of sections found |
| test-design | ≥80% test categories covered | Fraction of test categories found |
| custom-ir | All record fields present | Fraction of fields found |
| custom-sp | All sprint planning fields present | Fraction of fields found |
| custom-story | All story fields present | Fraction of fields found |
| custom-qr | All quality record fields present | Fraction of fields found |
| custom-pr | All production readiness fields present | Fraction of fields found |
| meta-mod | Correct mod + direction classification | Per-component accuracy |
| meta-chain | Correct sequence ordering | Per-step accuracy |
| meta-guard | Correct rule match | Per-rule accuracy |
| meta-root | Correct root + direction classification | Per-component accuracy |
| meta-path | Correct path classification | Per-component accuracy |
| research-experiment | Record completeness + gate validity | Field coverage |
| code-docs | Documentation coverage | Per-section coverage |

## Adding More Training Data

Drop JSON files into `bmad_benchmarks/envs/<benchmark>/data/train/`.
Each file can contain a single object or an array of objects.
The dataloader globs `*.json` from the split directory.

## SkillOpt-Sleep (Nightly Self-Evolution)

For continuous improvement from real usage sessions. The repo ships a launcher
that bridges real usage (experiments, learnings, audit events) into the training
data first, then runs the cycle:

```bash
sh scripts/skillopt-sleep.sh dry-run     # bridge real usage + report only
sh scripts/skillopt-sleep.sh run         # bridge + full cycle → proposal staged
sh scripts/skillopt-sleep.sh status      # Check staged proposals
sh scripts/skillopt-sleep.sh adopt       # Apply approved changes
sh scripts/skillopt-sleep.sh schedule    # Install nightly cron/schtasks
sh scripts/skillopt-sleep.sh unschedule  # Remove it
```

> **Prerequisite:** a skill must be trained first (`python scripts/train_bmad.py
> --benchmark <name>`), producing `outputs/<benchmark>/best_skill.md` as the
> live baseline. `skillopt-sleep` refuses to stage a proposal without a baseline
> pin — that is by design (gate_no_regression).

Config at `~/.skillopt-sleep/config.json` (installed by this repo):
```json
{
  "transcript_source": "claude",
  "backend": "mock",
  "skill_roots": ["C:/Users/ASUS/orca/openhands-metodoloji/skills"],
  "target_skill_path": "C:/Users/ASUS/orca/openhands-metodoloji/skills",
  "gate_no_regression": true,
  "dream_rollouts": 3,
  "multi_skill_fanout": true
}
```
