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

## Architecture

```
bmad_benchmarks/envs/
├── _base_/default.yaml          # Shared hyperparameters
├── bmad_code_review/
│   ├── adapter.py               # EnvAdapter implementation
│   ├── dataloader.py            # SplitDataLoader (JSON items)
│   ├── rollout.py               # Rollout + scoring functions
│   ├── skills/initial.md        # Seed skill (starting point)
│   └── data/{train,valid}/      # Training + held-out validation
├── bmad_create_story/           # Same structure
├── bmad_architecture/
├── bmad_prd/
└── bmad_test_design/

configs/
├── bmad-code-review/default.yaml
├── bmad-create-story/default.yaml
├── bmad-architecture/default.yaml
├── bmad-prd/default.yaml
└── bmad-test-design/default.yaml

scripts/
├── train_bmad.py                # Training entry point
├── eval_bmad.py                 # Evaluation entry point
└── register_benchmarks.py       # Adapter registration
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

## Adding More Training Data

Drop JSON files into `bmad_benchmarks/envs/<benchmark>/data/train/`.
Each file can contain a single object or an array of objects.
The dataloader globs `*.json` from the split directory.

## SkillOpt-Sleep (Nightly Self-Evolution)

For continuous improvement from real usage sessions:

```bash
skillopt-sleep schedule    # Install nightly cron
skillopt-sleep dry-run     # Test without staging
skillopt-sleep run         # Full cycle → proposal staged
skillopt-sleep status      # Check staged proposals
skillopt-sleep adopt --all-skills  # Apply approved changes
```

Config at `~/.skillopt-sleep/config.json`:
```json
{
  "gate_no_regression": true,
  "dream_rollouts": 3,
  "multi_skill_fanout": true
}
```
