<div align="center">

# metodoloji

**BMAD methodology as a dual-runtime plugin for [OpenHands](https://github.com/All-Hands-AI/OpenHands) and [Claude Code](https://code.claude.com)**

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)
![Version](https://img.shields.io/badge/version-1.0.0-8A2BE2.svg?style=flat-square)
![Platform](https://img.shields.io/badge/platform-OpenHands%20%2B%20Claude%20Code-4B32C3.svg?style=flat-square)

<br/>

<img src="docs/images/record-chain.png" alt="Record chain: E → IR → SP → S → QR → PR" width="820" />

</div>

---

## The problem

AI coding agents are fast — and dangerously eager to write code before anyone has *thought*. There's no built-in gate between "I have an idea" and "I'm already touching files."

**metodoloji** fixes this mechanically. It enforces a six-stage record chain:

```
E → IR → SP → S → QR → PR
```

Every stage must be completed and HMAC-signed before the next one unlocks. Hooks watch every file edit, commit, and deploy — and block if the methodology isn't satisfied.

---

## How it works

The same `hooks/hooks.json` manifest is auto-discovered by both runtimes. OpenHands and Claude Code share one hook engine; each command resolves its installation path at runtime. Methodology records are always written to your **project root**, never inside the plugin.

**Guard (fail-closed)** — writing any code requires an approved Experiment record. No approval → no edit.

**Quality / Deploy** — `git commit` and deploy commands require the full chain: IR → SP → QR → PR.

**Stop (fail-closed)** — the session cannot close with unfinished stories or unapproved changes.

**PostToolUse audit** — every write, edit, and bash call is logged to `.metodoloji/logs/hook-audit.log` asynchronously.

### Record chain stages


| Stage | Full name                | Purpose                                        |
| ----- | ------------------------ | ---------------------------------------------- |
| E     | Experiment               | Define hypothesis, scope, and success criteria |
| IR    | Implementation Readiness | Verify design and prerequisites before coding  |
| SP    | Sprint Plan              | Break work into traceable stories              |
| S     | Story                    | Atomic unit of implementable work              |
| QR    | Quality Review           | Gate before merge — tests, coverage, review    |
| PR    | Production Readiness     | Final checklist before deploy                  |


---

## Installation

> The plugin is **opt-in** — you must enable it explicitly.

### OpenHands

```python
from openhands.sdk.plugin import install_plugin
install_plugin("github:yunusgungor/metodoloji")
# installs to → ~/.openhands/plugins/installed/metodoloji/
```

### Claude Code

```bash
/plugin marketplace add https://github.com/yunusgungor/metodoloji
/plugin install metodoloji@metodoloji
claude plugin enable metodoloji
```

### First session

```bash
/metodoloji:init        # creates record skeleton + templates in your project
/metodoloji:gate-setup  # generates ~/.bmad/gate-key (machine-local HMAC secret)
```

Once set up, run an experiment and get it **APPROVED** to open your code scope:

```bash
# {metodoloji-root} resolves at runtime to the plugin's installation directory
python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py \
  --record docs/experiments/E-001.md \
  --run "python scripts/bench/bench.py"
```

---

## Documentation


| Document                                     | Contents                                             |
| -------------------------------------------- | ---------------------------------------------------- |
| [**Usage Guide**](docs/USAGE-GUIDE.md)       | Records, gates, security model, troubleshooting, FAQ |
| [Claude Code guide](docs/CLAUDE.md)          | Claude-specific setup and behaviour                  |
| [Training lessons](docs/TRAINING-LESSONS.md) | Lessons learned from running the methodology         |


---

<div align="center">

MIT License · Built on [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) — thank you to the BMad Method team 🙏

</div>

