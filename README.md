<div align="center">

# metodoloji

**BMAD methodology as a dual-runtime plugin** — 123 skills, 120 bridge TOMLs and
mechanical gates (guard / quality / deploy / stop) that make the
record chain **E → IR → SP → S → QR → PR** actually enforceable in
[OpenHands](https://github.com/All-Hands-AI/OpenHands) and [Claude Code](https://code.claude.com).

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-0.1.0-8A2BE2.svg)
![Platform: OpenHands + Claude Code](https://img.shields.io/badge/platform-OpenHands%20%2B%20Claude%20Code-4B32C3.svg)

</div>

---

## Built on BMAD 🧡

**metodoloji is inspired by — and would not exist without — the
[BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) project**
(*Breakthrough Method for Agile AI-Driven Development*) and the wider
[BMAD ecosystem](https://bmadcode.com). We are deeply grateful to the BMad Code team
for creating and open-sourcing a methodology that puts thinking back into
agent-driven development. This plugin adapts their ideas into a ready-to-install
plugin with mechanical enforcement. **Thank you! 🙏**

## What it does

Agentic coding tools are great at writing code — and too eager to write it before
anyone has *thought*. `metodoloji` fixes that **mechanically**: hooks watch every
edit, commit and deploy, and refuse to proceed unless the methodology says so.

- **Guard (fail-closed)** — writing code requires an **approved experiment (E)**. No approval, no edit.
- **Quality / Deploy (soft or hard)** — `git commit` and deploy commands require the full record chain (IR → SP → QR → PR).
- **Stop (fail-closed)** — the session cannot close with unfinished stories or unapproved changes.
- **123 skills** (native BMAD body) bridged to methodology records via **120 bridge TOMLs**.
- **HMAC-secured records** — experiment approvals are signed with a machine-local gate key; forged records are detected.

## Quick start

### OpenHands (SDK)

```python
from openhands.sdk.plugin import Plugin

# Load from GitHub
Plugin.load(Plugin.fetch("github:yunusgungor/metodoloji"))

# Or persist it and auto-load in later sessions
from openhands.sdk.plugin import install_plugin
install_plugin("github:yunusgungor/metodoloji")  # → ~/.openhands/plugins/installed/metodoloji/
```

### Claude Code (marketplace)

```
/plugin marketplace add https://github.com/yunusgungor/metodoloji
/plugin install metodoloji@metodoloji
claude plugin enable metodoloji
```

> The plugin is **opt-in** (`defaultEnabled: false`) — enable it explicitly, as above.

### First session

```
/metodoloji:init          # install the record skeleton + templates into your project
/metodoloji:gate-setup    # generate ~/.bmad/gate-key (machine-local, HMAC signing)
```

Then run an experiment, get it **APPROVED** through the gate, and the guard opens
your code scope (`{metodoloji-root}` = this plugin's installation root —
`~/.openhands/plugins/installed/metodoloji/` on OpenHands,
`~/.claude/plugins/cache/yunusgungor/metodoloji/` on Claude Code):

```bash
python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py \
  --record docs/experiments/E-001.md \
  --run "python scripts/bench/bench.py"
```

## How it works

```
E (Experiment) → IR (Implementation Readiness) → SP (Sprint Planning)
→ S (Story) → QR (Quality Review) → PR (Production Readiness)
```

A single unified `hooks/hooks.json` is auto-discovered by **both** runtimes —
OpenHands and Claude Code share the same hook engine, and hook commands resolve
their own installation path at runtime. Methodology outputs are always written
under your **project root**, never inside the plugin.

## Documentation


| Document                               | Contents                                                   |
| -------------------------------------- | ---------------------------------------------------------- |
| [**Usage Guide**](docs/USAGE-GUIDE.md) | Everything: records, gates, security, troubleshooting, FAQ |
| [Claude Code guide](docs/CLAUDE.md)    | Claude-specific setup and behavior                         |


## License

MIT. Based on [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD)
