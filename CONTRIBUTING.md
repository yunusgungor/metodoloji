# Contributing to Metodoloji

Thank you for your interest in contributing to **Metodoloji**! We welcome contributions to our BMAD methodology skills, hook engine, test suites, and documentation.

## Development Setup

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

3. **Run the Test Suite:**
   ```bash
   pytest
   ```

4. **Verify Health Check:**
   ```bash
   sh scripts/check-plugin.sh --negtest
   ```

---

## Contribution Guidelines

### Adding or Updating Skills
- Skills live under `skills/<skill-name>/` with a valid `SKILL.md`.
- Customization and BRIDGE instructions live under `custom/<skill-name>.toml`.
- If a skill produces or feeds into methodology records (IR/SP/S/QR/PR), define the appropriate `BRIDGE` and `VERIFY` steps.

### Hook Engine Modifications
- The hook engine lives in `hooks/engine/` (`main.py` and `modules/`).
- Must support dual-runtime execution (**OpenHands** and **Claude Code**).
- Fail-closed behavior for `guard` and `stop`; fail-open for `audit` and dispatcher root discovery (`run-hook.sh`).
- Every engine change must include unit tests in `hooks/engine/tests/`.

### Pull Request Process
1. Fork the repository and create your branch from `master`.
2. Ensure all tests pass (`pytest`).
3. Commit with concise conventional commit messages (e.g. `feat(skill): ...`, `fix(hooks): ...`, `docs: ...`).
4. Open a pull request against `master`.
