# Contributing to Metodoloji

Thank you for your interest in contributing to **Metodoloji**! We welcome contributions across our 123 BMAD skills, SkillOpt training pipelines, hook engine, and documentation.

---

## 🎯 Special Focus: Skill Training & Optimization (SkillOpt)

Metodoloji uses [SkillOpt](https://github.com/microsoft/SkillOpt) (Reinforcement Learning on text-based skills without model weight changes) to continually tune and elevate skill instructions (`SKILL.md`). **Skill contributions backed by SkillOpt training and benchmark evaluation are highly valued.**

### 1. Training Environment & Benchmarks
Our 17 benchmark environments are located under `bmad_benchmarks/envs/`:
- **Core Engineering:** `bmad-code-review`, `bmad-create-story`, `bmad-architecture`, `bmad-prd`, `bmad-test-design`
- **Methodology Record Gates:** `bmad-custom-ir`, `bmad-custom-sp`, `bmad-custom-story`, `bmad-custom-qr`, `bmad-custom-pr`
- **Meta & Architecture:** `bmad-meta-guard`, `bmad-meta-chain`, `bmad-meta-mod`, `bmad-meta-root`, `bmad-meta-path`, `bmad-research-experiment`, `bmad-code-docs`

Each benchmark contains:
- `adapter.py`: Runtime/agent harness
- `dataloader.py`: Curated test prompts & gold standards
- `rollout.py`: Scoring rubrics and execution validation
- `skills/`: Seed/baseline skill text

### 2. How to Train a Skill with SkillOpt

1. **Install SkillOpt and Training Dependencies:**
   ```bash
   pip install skillopt pyyaml httpx openai
   ```

2. **Configure Credentials:**
   ```bash
   cp .env.example .env
   # Set OPENAI_API_KEY / ANTHROPIC_API_KEY
   source .env
   ```

3. **Run Training on a Benchmark:**
   ```bash
   # Train a specific skill benchmark (e.g. code-review)
   python scripts/train_bmad.py --benchmark bmad-code-review

   # Or evaluate current baseline
   python scripts/eval_bmad.py --benchmark bmad-code-review
   ```

4. **Adopt the Optimized Skill:**
   After training completes:
   - Check the resulting score in `outputs/<benchmark>/`
   - Compare `outputs/<benchmark>/best_skill.md` with `skills/<skill-name>/SKILL.md`
   - If the new score beats the baseline without regression, update `skills/<skill-name>/SKILL.md`

### 3. Nightly Self-Evolution Cycle (`skillopt-sleep.sh`)
Metodoloji supports feeding real-world session data (audit logs, learnings, approved experiments) back into training:
```bash
# Dry run to preview training queue
sh scripts/skillopt-sleep.sh dry-run

# Run full optimization cycle
sh scripts/skillopt-sleep.sh run

# Inspect training history and adopt improvements
sh scripts/skillopt-sleep.sh status
sh scripts/skillopt-sleep.sh adopt
```

---

## 🛠️ Development Setup & Quality Checks

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/yunusgungor/metodoloji.git
   cd metodoloji
   ```

2. **Python Environment:**
   Python 3.11+ is required (uses standard library `tomllib`).
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install pytest pyyaml httpx
   ```

3. **Run the Full Test Suite:**
   All 580+ unit and integration tests must pass:
   ```bash
   pytest
   ```

4. **Run Plugin Health Checks & Negative Tests:**
   ```bash
   # Verify gate key, engine drift, bridge runtime visibility, and tech debt:
   sh scripts/check-plugin.sh

   # Run automated negative tests (ensures detection catches missing markers):
   sh scripts/check-plugin.sh --negtest
   ```

---

## 📐 Contribution Guidelines

### Adding or Updating Skills
- Skills live under `skills/<skill-name>/` with a valid `SKILL.md`.
- Customization and BRIDGE instructions live under `custom/<skill-name>.toml`.
- If a skill produces or feeds into methodology records (IR/SP/S/QR/PR), define the appropriate `BRIDGE` and `VERIFY` steps.
- **Provide training evidence:** When improving a skill prompt, include before/after benchmark scores in your PR description.

### Hook Engine Modifications
- The hook engine lives in `hooks/engine/` (`main.py` and `modules/`).
- Must support dual-runtime execution (**OpenHands** and **Claude Code**).
- Fail-closed behavior for `guard` and `stop`; fail-open for `audit` and dispatcher root discovery (`run-hook.sh`).
- Every engine change must include unit tests in `hooks/engine/tests/`.

---

## 🚀 Pull Request Process

1. Fork the repository and create your branch from `master`.
2. Ensure all tests pass (`pytest` and `check-plugin.sh --negtest`).
3. Commit with conventional commit messages (e.g. `feat(skill): tune bmad-code-review prompt with SkillOpt (+4.2% score)`, `fix(hooks): ...`).
4. Include training logs or benchmark results if modifying skill behavior.
5. Open a pull request against `master`.

