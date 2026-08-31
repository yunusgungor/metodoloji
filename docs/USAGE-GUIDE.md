# OpenHands Metodoloji Plugin — Comprehensive Usage Guide

> **Version:** 1.0.0 | **Author:** yunusgungor | **License:** MIT
>
> This document is the complete and detailed usage guide covering every aspect of the `metodoloji` OpenHands plugin.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Installation](#3-installation)
4. [Initial Configuration](#4-initial-configuration)
5. [Record Chain (E → IR → SP → S → QR → PR)](#5-record-chain)
6. [Hook Engine and Mechanical Gates](#6-hook-engine-and-mechanical-gates)
7. [Skill Bridge and TOML Customization](#7-skill-bridge-and-toml-customization)
8. [Commands](#8-commands)
9. [Templates](#9-templates)
10. [Free Zones and Restricted Areas](#10-free-zones-and-restricted-areas)
11. [Security (Gate Key and HMAC)](#11-security)
12. [Audit and Health Check](#12-audit-and-health-check)
13. [Troubleshooting](#13-troubleshooting)
14. [Frequently Asked Questions](#14-frequently-asked-questions)
15. [Glossary](#15-glossary)

---

## 1. Overview

### What Does the Plugin Do?

`metodoloji` is the OpenHands SDK plugin implementation of the **BMAD (Build Methodology for Agent-Driven development)** methodology. It ships with 123 skills + 119 bridge TOMLs (33 BRIDGE active) + mechanical gates + a record chain.

Core functions:

| Component | Function |
|-----------|----------|
| `skills/` | 123 BMAD skills (native body) |
| `custom/` | 119 bridge TOMLs (33 active with BRIDGE: `activation_steps_append`/`principles` → links native outputs to methodology records) + `config.toml` (soft/hard) |
| `hooks/` | PreToolUse / PostToolUse / Stop / SessionStart hooks; modular engine structure |
| `hooks/engine/` | Python engine: `main.py` (entry point), `modules/` (guard, audit, stop, utils, config) |
| `bmad/` | Module data (bmm, cis, gds, wds, tea, core, bmb) |
| `templates/` | IR/SP/QR/PR/S/E/README/tech-debt record templates |
| `commands/` | `/metodoloji:init`, `/metodoloji:gate-setup`, `/metodoloji:verify`, `/metodoloji:audit` |

### Core Principle

The plugin **mechanically blocks writing code without experiment approval**.
To write code you must first create an experiment (E-NNN) record, test the hypothesis,
and get APPROVED through the gate. This mechanically breaks the "write code without thinking" habit.

### Research Modes

| Mode | Type | Record Location | Usage |
|------|------|-----------------|-------|
| **Mode A** | Quantitative/Empirical | `docs/experiments/` | The only legitimate path to code production — mechanical gate |
| **Mode B** | Qualitative | `docs/research/` | Literature review, interviews, case analysis |
| **Mode C** | Design | `docs/design/` | UX/architecture designs |
| **Mode D** | Contextual | `docs/research/` | Market research, competitive analysis |

---

## 2. Architecture

### Directory Structure

```
metodoloji/
├── .plugin/
│   ├── plugin.json              # Plugin definition (name, version, repository)
│   └── marketplace.json         # Marketplace listing
├── hooks/
│   ├── hooks.json               # OpenHands hook definitions
│   ├── engine/                  # Python engine
│   │   ├── main.py              # Main entry point
│   │   ├── memlog.py            # Working memory logging utility
│   │   ├── resolve_customization.py  # TOML deep_merge bridge resolver
│   │   └── modules/
│   │       ├── __init__.py      # Module exports
│   │       ├── config.py        # Constant configuration (paths, thresholds)
│   │       ├── utils.py         # Helper functions (norm_path, is_free, is_code_target)
│   │       ├── archive.py       # Archive processing (tar/zip — bomb protection)
│   │       ├── bash_targets.py  # Bash command target detection
│   │       ├── guard.py         # PreToolUse logic (code writing block)
│   │       ├── audit.py         # PostToolUse audit trail
│   │       └── stop.py          # Stop logic (session close block)
│   └── scripts/
│       ├── bootstrap.sh         # SessionStart: gate-key + missing directories + context
│       └── hook-entry.sh        # Single dispatch point: mode-selection + routing to Python
├── skills/                      # 123 BMAD skill directories
├── custom/                      # 119 bridge TOMLs (33 BRIDGE active) + config.toml
├── bmad/                        # Module data (bmm, cis, gds, wds, tea, core, bmb)
├── templates/                   # Record templates
├── commands/                    # Command definitions + check-plugin.sh
├── scripts/                     # Helper scripts
└── docs/                        # Documentation
```

### Hook Flow Diagram

```
OpenHands Runtime
       │
       ├── SessionStart ──→ bootstrap.sh
       │    │                    │
       │    │              Create gate key (if missing)
       │    │              Create missing directories
       │    │              Inject context (record chain reminder)
       │    │
       ├── PreToolUse ────→ hook-entry.sh guard
       │    │                    │
       │    │              main.py guard() → read JSON stdin
       │    │                    │
       │    │              Detect target files (file_editor/terminal)
       │    │                    │
       │    │              For each target:
       │    │                ├── Free zone? → allow
       │    │                ├── Code target? → allow (if not)
       │    │                └── Approved experiment exists?
       │    │                      ├── Yes → allow
       │    │                      └── No → DENY
       │    │
       ├── PostToolUse ───→ hook-entry.sh audit (async)
       │    │                    │
       │    │              main.py audit() → write JSON audit trail
       │    │              Methodology compliance warnings (non-blocking)
       │    │              Append to .metodoloji/logs/hook-audit.log
       │    │
       └── Stop ──────────→ hook-entry.sh stop
                │                    │
                │              main.py stop()
                │                ├── Incomplete story exists? → DENY
                │                └── Unapproved code change exists? → DENY
```

### Root Resolution Rules

| Placeholder | Value |
|-------------|-------|
| `{project-root}` | Target project root (`$OPENHANDS_PROJECT_DIR`) |
| `{metodoloji-root}` | Plugin installation root (`~/.openhands/plugins/installed/metodoloji`) |
| `{skill-root}` | The skill's location within the plugin |

**Output rule:** Methodology outputs (story, experiment, planning, test artifacts, `bmad-output/`) are always created under `{project-root}` — never under `{metodoloji-root}`.

---

## 3. Installation

### 3.1. Installing from Python (SDK)

```python
from openhands.sdk.plugin import Plugin

# From GitHub
p = Plugin.load("github:yunusgungor/metodoloji", repo_path="openhands/metodoloji")

# From a local repository
p = Plugin.load("/path/to/openhands/metodoloji")
```

### 3.2. Manual Installation

```bash
# 1. Clone the repository
git clone https://github.com/yunusgungor/openhands-metodoloji.git
cd openhands-metodoloji

# 2. Verify the plugin directory structure
ls -la .plugin/plugin.json    # Plugin definition
ls -la hooks/hooks.json       # Hook definitions
ls -la hooks/engine/main.py   # Engine entry point

# 3. Python 3.11+ required (for tomllib)
python3 --version  # must be >= 3.11
```

### 3.3. Prerequisites

| Requirement | Minimum | Note |
|-------------|---------|------|
| Python | 3.11+ | For the `tomllib` stdlib module |
| OpenHands | Latest version | Plugin API support |
| Git | 2.x | Version control |

---

## 4. Initial Configuration

### 4.1. Step-by-Step Initial Setup

Proceed in the following order during your first session:

#### Step 1: Start the Plugin

The plugin loads automatically in your OpenHands session. The `SessionStart` hook
does the following:

1. Does not copy the plugin into the workspace — the single installation root is the install root
2. Creates `~/.bmad/gate-key` if it does not exist (permissions 0600)
3. Creates missing directories (`docs/experiments/`, `.metodoloji/logs/`)
4. Injects context: "METODOLOJI active — Record chain: E → IR → SP → S → QR → PR"

#### Step 2: Set Up the Record Skeleton

```
/metodoloji:init
```

This command does the following:

| Action | Detail |
|--------|--------|
| Create directories | `docs/experiments/`, `docs/development/stories/`, `docs/research/`, `docs/design/`, `docs/bmad/`, `scratch/` |
| Copy templates | E, IR, SP, S, QR, PR templates into the respective directories |
| Warning | Tells you to run `/metodoloji:gate-setup` if the gate key is not installed |

#### Step 3: Install the Gate Key

```
/metodoloji:gate-setup
```

This command creates the `~/.bmad/gate-key` file. This file:
- **Lives outside the repository** (is never committed)
- **Has 0600 permissions** (only the owner can read it)
- Is used for **HMAC validation**
- Is **machine-local** (each developer generates their own key)

```bash
# Manual installation (if /metodoloji:gate-setup does not work):
python3 skills/bmad-research-experiment/scripts/run_experiment.py --init-secret
```

#### Step 4: Run the Health Check

```
/metodoloji:audit
```

or directly:

```bash
sh commands/check-plugin.sh
```

This runs all checks from §0 through §6:
- §0: Is the gate key installed?
- §1: Is the hook engine working?
- §2: Is the manifesto wired to all surfaces?
- §2b: Are bridge instructions visible at runtime?
- §3: Approved experiment inventory
- §4: Documentary record completeness
- §5: Engine drift audit
- §5b: Hard gate enforcement mode
- §6: Development records format check

---

## 5. Record Chain (E → IR → SP → S → QR → PR)

The record chain is the backbone of the methodology. Each link depends on the next:

```
E (Experiment) → IR (Implementation Readiness) → SP (Sprint Planning) → S (Story) → QR (Quality Review) → PR (Production Readiness)
   Mode A              Gate 1                         Gate 2                Implementation      Gate 3                    Gate 4
```

### 5.1. E — Experiment Record (Mode A, Mechanical Gate)

The **only legitimate path** to code production. Writing code without an experiment is
mechanically blocked by `guard`.

**Record location:** `docs/experiments/E-NNN.md`

**Steps:**

1. **Create the experiment file:**
   ```
   templates/_template_E.md → docs/experiments/E-001.md
   ```

2. **Fill in the required fields:**

   ```markdown
   ## Experiment: E-001 — Database index optimization
   - **Date:** 20.08.2026
   - **Status:** planned
   - **Theory:** B+ tree indexes reduce search performance on large tables from O(n) to O(log n)
   - **Hypothesis:** H-001: "query time will drop from 200ms to 20ms"
   - **Measurement Metrics:** query_time_ms <= 20
   - **Code Scope:** src/db/**/*.py, lib/engine/*.py
   ```

3. **Run the gate:**

   ```bash
   python3 skills/bmad-research-experiment/scripts/run_experiment.py \
     --record docs/experiments/E-001.md \
     --run "python scripts/bench/bench_query.py"
   ```

4. **Result:**
   - `APPROVED` → Guard opens this scope; you can write code
   - `REJECTED` → Revise the hypothesis and re-measure

5. **Verify before writing code:**

   ```bash
   python3 skills/bmad-research-experiment/scripts/run_experiment.py \
     --verify --record docs/experiments/E-001.md
   ```

**Field Descriptions:**

| Field | Required | Description |
|-------|----------|-------------|
| `Date` | Yes | In DD.MM.YYYY format |
| `Status` | Yes | planned / APPROVED / REJECTED |
| `Theory` | Yes | Which theory/framework it came from |
| `Hypothesis` | Yes | In H-NNN: "metric >= threshold" format |
| `Measurement Metrics` | Yes | Metric name + threshold, numeric |
| `Code Scope` | Yes | Glob patterns, comma/space separated |
| `Raw results` | Written by gate | Measurement output |
| `Uncertainty` | Written by gate | small sample / none / n unknown |
| `Metric` | Written by gate | compliant / NON-COMPLIANT |
| `Decision` | Written by gate | APPROVED / REJECTED |
| `Gate Evidence` | Written by gate | GATE-OK-... token |
| `Next Step` | Written by gate | Move to Code / Return to Theory |

**Dry-run (preview without writing a Decision):**

```bash
python3 skills/bmad-research-experiment/scripts/run_experiment.py \
  --record docs/experiments/E-001.md \
  --run "python scripts/bench/bench_query.py" \
  --dry-run
```

### 5.2. IR — Implementation Readiness (Gate 1)

Checks whether research findings are ready for development.

**Record location:** `docs/development/IR-NNN.md`

**Status values:** `READY` | `INCOMPLETE`

**Checklist:**
- At least one approved research record exists (E/R/D/C-id)
- PRD or story defined
- UX spec ready (if required)
- Architecture plan ready (if required)
- Success criteria are clear and measurable
- Technical dependencies identified
- Risk assessment performed
- Plan for gaps exists (if any)

**Note:** If there are gaps, the sprint is not started; first return to the research wing.

### 5.3. SP — Sprint Planning (Gate 2)

Guarantees the sprint scope is clear, measurable, and realistic.

**Record location:** `docs/development/SP-NNN.md`

**Status values:** `planned` | `in-progress` | `completed` | `canceled`

**Fields:**
- Sprint goal (single sentence)
- Story list (S-id + priority + story points)
- Capacity (compared against team velocity)
- Technical debt assessment
- Blockers and resolution plans
- Dependencies

**Checklist:**
- Sprint goal is clear and expressible in a single sentence
- S-id record exists for each story
- Story points assigned and realistic
- Sprint capacity fits the team velocity
- Technical debt assessed and time-boxed
- Blockers identified and a resolution plan exists

### 5.4. S — Story Record

Created during sprint planning and tracked throughout implementation.

**Record location:** `docs/development/stories/S-NNN.md`

**Status values:** `backlog` | `sprint` | `in-progress` | `review` | `done` | `blocked`

**Required sections:**

1. **Frontmatter:**
   ```yaml
   ---
   experiment_refs:
     - id: E-001
       scope: "src/db/**"
       status: APPROVED
   ---
   ```

2. **Acceptance Criteria:** Required fields for each AC:
   - `[AC-NNN]` identifier
   - `Experiment:` field (E-NNN, or `—` together with the `[HYPOTHESIS]` tag)
   - `Type:` field (`agent-verifiable` | `user-evaluable` | `hybrid`)
   - `Measured:` field (`true` | `false`)
   - `Verify:` field (verification method)

3. **Technical Tasks:** Each task must have an AC reference (`AC: AC-NNN`)

4. **Definition of Done:** Each item must include a `DoD-NNN` identifier and a `Verify:` field

**Guard validations (when writing a story file):**
- `experiment_refs` → do the referenced experiment records exist?
- AC metadata → are all fields filled?
- Task↔AC mapping → is every task linked to an AC?
- DoD structure → are identifiers present?
- Methodology chain → does a QR/SP record exist for the story's status?

**Creating a story:**

```bash
# Create a methodology record from a native story file
python3 scripts/create-methodology-record.py --story docs/development/stories/S-001.md
```

### 5.5. QR — Quality Review (Gate 3)

Enforces quality standards before code is merged.

**Record location:** `docs/quality/QR-NNN.md`

**Status values:** `APPROVED` | `REJECTED` | `REVISE`

**Mechanical checks (automatic):**
- Test coverage >= 80%
- All tests passed (unit, integration, e2e)
- Linter and formatter clean
- Security scan clean
- No performance regression

**Documentary checks (manual):**
- Code review approval
- Documentation currency
- Breaking change migration plan
- Technical debt record

**Creating a QR:**

```bash
python3 scripts/create-qr-record.py --story docs/development/stories/S-001.md
```

### 5.6. PR — Production Readiness (Gate 4)

Guarantees operational readiness before production deployment.

**Record location:** `docs/development/PR-NNN.md`

**Status values:** `READY` | `PENDING`

**Main sections:**
- Staging test (deploy, smoke test, integration)
- Rollback plan (triggers, steps, database rollback)
- Monitoring and alerting (metrics, alerts, logging)
- Feature flags (kill switch, gradual rollout)
- Runbook (deploy steps, troubleshooting)
- Incident response (communication, severity, post-mortem)
- Deploy window (timing, freeze period)

**Checklist:**
- All mechanical checks PASS
- Rollback plan ready and tested
- Monitoring and alerting set up
- Deploy window determined
- Change approval obtained

---

## 6. Hook Engine and Mechanical Gates

### 6.1. hooks.json Definition

The plugin uses **6 hook points** in the OpenHands runtime:

```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command", "command": "sh .../bootstrap.sh" }] }],
    "PreToolUse": [
      { "matcher": "/file_editor|terminal/", "hooks": [{ "command": "sh .../hook-entry.sh guard" }] },
      { "matcher": "/terminal/", "hooks": [{ "command": "sh .../hook-entry.sh quality" }] },
      { "matcher": "/terminal/", "hooks": [{ "command": "sh .../hook-entry.sh deploy" }] }
    ],
    "PostToolUse": [{ "matcher": "/file_editor|terminal/", "hooks": [{ "command": "sh .../hook-entry.sh audit", "async": true }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": "sh .../hook-entry.sh stop" }] }]
  }
}
```

### 6.2. Guard (PreToolUse) — Fail-Closed

**Scope:** `file_editor`, `terminal`, `notebook_editor`

**Behavior:**
- Code target + outside free zone → looks for an approved experiment record
- No approved experiment → `DENY` (code writing is blocked)
- If it is a story file (`S-NNN.md` or `N-N-slug.md`) → additional validations:
  - `experiment_refs` → are the referenced experiment records APPROVED?
  - AC metadata → are all fields filled?
  - Task↔AC mapping → is every task linked to an AC?
  - DoD structure → are identifiers present?
  - Methodology chain → if an SP reference exists, does the SP record exist?
- If gate key access is detected → `DENY` (security violation)

**Code target classification:**

| Category | Examples | Protected? |
|----------|----------|-------------|
| Code files | `.py`, `.js`, `.ts`, `.go`, `.rs`, `.java` | ✅ Yes |
| Configuration | `Makefile`, `Dockerfile`, `package.json` | ✅ Yes |
| Documents | `.md`, `.txt`, `.rst` | ❌ No (free) |
| Data | `.csv`, `.json`, `.yaml`, `.lock` | ❌ No (free) |
| Visual | `.png`, `.jpg`, `.svg` | ❌ No (free) |

### 6.3. Audit (PostToolUse) — Fail-Open

**Scope:** All tool calls

**Behavior:**
- Writes every call to `.metodoloji/logs/hook-audit.log` in JSON format
- Produces methodology compliance warnings on story files (non-blocking)

**Audit record structure:**
```json
{
  "timestamp": 1692537600.0,
  "tool": "file_editor",
  "input": { "path": "src/main.py", "content": "..." },
  "output_summary": "...",
  "methodology_warnings": ["Story file ...: AC metadata missing"]
}
```

### 6.4. Quality (PreToolUse) — Fail-Closed

**Scope:** `terminal` (only `git commit` commands)

**Behavior:**
- Terminal command does not contain `git commit`? → `allow` (fast exit)
- If it is `git commit` → performs a chain check:
  1. Done stories exist but no IR record at all? → `DENY` (Gate 1 — readiness)
  2. Do stories with `Status: done` have a QR record? → If not, `DENY` (Gate 3 — quality)
  3. Do stories with `Status: done` contain an SP reference? If so, does the SP record exist? → If not, `DENY` (Gate 2 — sprint)
- If all checks pass → `allow`

**Check order:** IR (project-level) → QR (story-level) → SP (story-level)

**Example block (QR missing):**
```
DENY: git commit blocked: 1 story(s) marked 'done' lack Quality Record (QR).
Stories: 1-2-user-auth. Create QR with: python3 scripts/create-qr-record.py ...
```

**Example block (SP missing):**
```
DENY: git commit blocked: 1 story(s) reference SP but lack Sprint Planning record.
Stories: 1-2-user-auth. Run bmad-sprint-planning to create SP record.
```

### 6.5. Deploy (PreToolUse) — Fail-Closed

**Scope:** `terminal` (deploy commands: terraform, kubectl, docker, git push to prod)

**Behavior:**
- No deploy command detected → `allow`
- Deploy command present → performs a chain check:
  1. Done stories exist but no IR record at all? → `DENY` (Gate 1 — readiness)
  2. Story with missing QR exists? → `DENY` (Gate 3 — quality)
  3. Story with missing SP exists? → `DENY` (Gate 2 — sprint)
  4. Story with missing PR exists? → `DENY` (Gate 4 — production)
- If all checks pass → `allow`

**Check order:** IR → QR → SP → PR (all links of the chain)

**Recognized deploy commands:** `terraform apply`, `kubectl apply`, `docker compose up`, `git push origin main/master/production`, `ansible playbook` + `deploy` keyword

### 6.6. Stop (Stop) — Fail-Closed

**Behavior:**
1. Incomplete story exists? → `DENY`
2. Unapproved code change exists? → `DENY`
3. If both are clean → `allow`

**The Stop hook blocks closing the session when:**
- A story is `in-progress` in `sprint-status.yaml`
- Files at the project root such as `.py`, `.js`, `.ts`, etc. have changes outside the scope of an approved experiment

### 6.7. hook-entry.sh — Single Dispatch Point

```
hook-entry.sh guard    → guard mode (fail-closed)
hook-entry.sh quality → quality mode (fail-closed)
hook-entry.sh deploy  → deploy mode (fail-closed)
hook-entry.sh audit   → audit mode (fail-open)
hook-entry.sh stop    → stop mode (fail-closed)
```

- Python resolver: `python3` → `python` → `py` (searches in order)
- If the engine is missing or Python is unavailable:
  - guard/stop → `DENY` + exit 2 (fail-closed)
  - quality/deploy → pass silently (fail-open)
  - audit → pass silently (fail-open)

### 6.8. Bash Command Target Detection

Automatically detects which files will be modified by terminal commands:

| Command/Pattern | Detected Target |
|-----------------|-----------------|
| `> file` / `>> file` | Redirection target |
| `tee file` | Tee output |
| `sed -i '...' file` | Sed target |
| `cp source target` / `mv source target` | Last argument |
| `curl -o file` | -o target |
| `tar -xf archive` | Archive contents (bomb protected) |
| `unzip archive` | Archive contents |
| `git apply patch` | Patch targets |
| `python -c 'open("x","w")'` | open() target |

**Archive bomb protection:**
- Maximum file size: 512 MB
- Maximum compressed size: 64 MB
- Maximum member count: 200,000
- Maximum uncompressed size: 2 GB

---

## 7. Skill Bridge and TOML Customization

### 7.1. Three-Layer TOML Merge

Each skill is customized at three layers (highest priority to lowest):

```
1. custom/{skill}.user.toml    → Personal (gitignored)
2. custom/{skill}.toml         → Team/organization (committed)
3. skills/{skill}/customize.toml → Skill defaults
```

**Merge rules:**
- **Scalars** (string, int, bool, float): override wins
- **Tables**: deep merge (recursive)
- **Arrays**: if all elements carry the same `code` or `id` field → merge by key; otherwise → append

### 7.2. Bridge TOML Structure

Each bridge TOML contains a BRIDGE instruction in the `activation_steps_append` (workflow) or `principles` (agent) field. BRIDGE is active in 33 skills:

**Producer BRIDGE (creates records — 17 skills):**
```toml
# custom/bmad-dev-story.toml
[workflow]
activation_steps_append = [
  "BRIDGE: After implementation finishes, update the docs/development/stories/S-<seq>.md record...",
  "BRIDGE #3 (QR): Create QR record: docs/quality/QR-<seq>.md...",
  "VERIFY: After creating the record, verify the file exists with 'ls -la'."
]
```

**Feeder BRIDGE (updates an existing record — 16 skills):**
```toml
# custom/bmad-testarch-automate.toml
[workflow]
activation_steps_append = [
  "BRIDGE: Add the test results to the Mechanical checks section of the QR-<seq>.md record..."
]
```

**VERIFY:** Producer BRIDGEs include a `VERIFY` step. Every time the LLM creates a record, it verifies the file exists with `ls -la`. This is an automatic control layer that prevents the BRIDGE from being skipped.

### 7.3. Bridge Resolution (resolve_customization.py)

```bash
# Full customization output
python3 hooks/engine/resolve_customization.py -s skills/bmad-dev-story

# Specific field
python3 hooks/engine/resolve_customization.py -s skills/bmad-dev-story -k workflow.activation_steps_append

# Multiple fields
python3 hooks/engine/resolve_customization.py -s skills/bmad-dev-story \
  -k agent.name -k workflow.activation_steps_append
```

### 7.4. Manifesto Wiring

Every methodology surface (skill) must reference these documents:
- `research-methodology.md` — Research manifesto (all surfaces)
- `project-context.md` — Project context (all surfaces)
- `development-methodology.md` — Development manifesto (development wing)

Bridge document: `docs/bmad/dev-skill-to-methodology-bridge.md`

---

## 8. Commands

> **Note:** these command names were previously `/metodoloji:kapi-kur`, `/metodoloji:dogrula`, `/metodoloji:denetim` (Turkish).

### 8.1. `/metodoloji:init`

**Purpose:** Install the record skeleton into the target project

**Effects:**
- Creates 6 directories (does not touch existing ones)
- Copies 8 templates (does not overwrite)
- Installs manifesto copies
- Warns about the gate key if missing

**Usage:** Type `/metodoloji:init` in an OpenHands session or follow the steps in this guide.

### 8.2. `/metodoloji:gate-setup`

**Purpose:** Generate the gate key (gate-key init)

**Effects:**
- Creates `~/.bmad/gate-key` (if missing)
- Sets 0600 permissions
- Generates an HMAC key (secrets.token_hex(32))
- **Never** prints/copies the key contents

**Usage:**
```bash
python3 skills/bmad-research-experiment/scripts/run_experiment.py --init-secret
```

### 8.3. `/metodoloji:verify`

**Purpose:** Verify an experiment record

**Outputs:**
| Output | Meaning |
|--------|---------|
| `VERIFIED` | Record is APPROVED and the token is valid |
| `FORGED` | Token does not match the key — record is invalid |
| `REJECTED` | Did not pass the gate |

**Usage:**
```bash
python3 skills/bmad-research-experiment/scripts/run_experiment.py \
  --verify --record docs/experiments/E-001.md
```

### 8.4. `/metodoloji:audit`

**Purpose:** Methodology health check

**Scope:**
1. Plugin integrity (§0–§6 + §2b + §5b + drift)
2. Record chain status
3. Approved experiment inventory
4. Hook configuration
5. Result report (PASS/FAIL)

### 8.5. check-plugin.sh

```bash
# Full audit
sh commands/check-plugin.sh

# Negative test: break BRIDGE → catch → restore
sh commands/check-plugin.sh --negtest
```

**Exit codes:**
- `0` = all checks passed (HEALTHY)
- `1` = problem found

---

## 9. Templates

### 9.1. Template List

| Template | Target | Usage |
|----------|--------|-------|
| `_template_E.md` | `docs/experiments/E-NNN.md` | Experiment record |
| `_template_IR.md` | `docs/development/IR-NNN.md` | Implementation Readiness |
| `_template_SP.md` | `docs/development/SP-NNN.md` | Sprint planning |
| `_template_S.md` | `docs/development/stories/S-NNN.md` | Story record |
| `_template_QR.md` | `docs/quality/QR-NNN.md` | Quality Review |
| `_template_PR.md` | `docs/development/PR-NNN.md` | Production Readiness |
| `README.md` | `docs/development/README.md` | Development directory description |
| `tech-debt.md` | `docs/development/tech-debt.md` | Technical debt tracking |

### 9.2. Template Usage

Copy the templates manually or use the scripts:

```bash
# New record from the experiment template
cp templates/_template_E.md docs/experiments/E-001.md
# ↓ editing: fill in the E-001.md file

# Methodology record from a story (automatic)
python3 scripts/create-methodology-record.py --story path/to/story.md

# QR record from a story (automatic)
python3 scripts/create-qr-record.py --story path/to/story.md
```

---

## 10. Free Zones and Restricted Areas

### 10.1. Free Zones (No Approval Required)

The following paths are automatically released by the guard:

| Prefix/Directory | Description |
|------------------|-------------|
| `_bmad/` | Legacy BMAD module data |
| `scratch/` | Free zone for exploratory code |
| `graft/` | Graft code |
| `.git/` | Git directories |
| `tmp/`, `temp/` | Temporary files |
| `openhands/` | OpenHands directories |
| `.metodoloji/` | The plugin's own directory |
| `docs/*.md` | Document files |
| `docs/*/raw/` | Raw data files |
| `explore_*` | Exploration files |
| Infrastructure files | `scripts/check-methodology.sh` |

### 10.2. Protected Areas (Approval Required)

All source code files and executable configuration files:

- `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.java`, `.go`, `.rs`
- `Makefile`, `Dockerfile`, `package.json`, `.github/workflows/*.yml`
- `src/`, `lib/`, `tools/`, `bin/`, `core/`, `app/` directories

### 10.3. Protected Areas Outside Free Zones

Even in files under `scratch/`, `tmp/`, `temp/`, if hidden access patterns such as `.bmad` directories,
gate-key, or `bmad_gate_key` are detected, a **DENY** is issued.

---

## 11. Security

### 11.1. Gate Key

- **Location:** `~/.bmad/gate-key` (OUTSIDE the repository)
- **Permissions:** 0600 (owner only)
- **Content:** 64-character hex string (32 random bytes)
- **Purpose:** HMAC validation — guarantees experiment records are not forged
- **Lifetime:** Machine-local; each developer generates their own key

### 11.2. Secret Protection

The guard engine detects and blocks the following patterns:

| Pattern | Effect |
|---------|--------|
| Command containing `gate-key` | DENY |
| Command containing `bmad_gate_key` | DENY |
| Access to the `.bmad` directory | DENY |
| Content containing `.bmad`/`gate-key` under `scratch/`/`tmp/`/`temp/` | DENY |

### 11.3. HMAC Token Structure

Every experiment approval is signed with an HMAC token:
- In `GATE-OK-<hash>` format
- Generated and validated with the gate key
- If a forged token is detected, a `FORGED` result is returned

---

## 12. Audit and Health Check

### 12.1. Automatic Audit (check-plugin.sh)

```bash
sh commands/check-plugin.sh
```

**Check sections:**

| Section | Content | Error Code |
|---------|---------|------------|
| §0 | Is the gate key installed | `--init-secret` |
| §1 | Hook engine selfcheck | `--selfcheck` |
| §2 | Manifesto + bridge wiring | TOML parse + consume check |
| §2b | Is the bridge visible at runtime (33 skills) | `resolve_customization` deep_merge (30 workflow + 3 agent-principles) |
| §2c | Does the bridge VERIFY instruction exist (13 skills) | Search for VERIFY within BRIDGE |
| §3 | Approved experiment inventory | Each E record via `--verify` |
| §4 | Documentary record completeness | B/C/D records via `--validate` |
| §5 | Engine drift audit | Do all engine files exist? |
| §5b | Hard gate mode | `custom/config.toml [hooks]` |
| §6 | Development records format | Decision/Status/Date fields |

### 12.2. Negative Test

```bash
sh commands/check-plugin.sh --negtest
```

This test:
1. Temporarily removes the BRIDGE line from `custom/bmad-dev-story.toml`
2. Verifies that the §2b logic detects a MISS
3. Restores the custom TOML to its original

### 12.3. BRIDGE Distribution

**Producer BRIDGE (17 skills) — creates records:**
- `bmad-dev-story`, `bmad-quick-dev`, `bmad-dev-auto`, `bmad-agent-dev`
- `bmad-code-review`, `bmad-create-story`, `bmad-sprint-planning`, `bmad-check-implementation-readiness`
- `gds-dev-story`, `gds-quick-dev`, `gds-code-review`, `gds-create-story`
- `gds-sprint-planning`, `gds-check-implementation-readiness`
- `gds-agent-game-dev`, `gds-agent-game-solo-dev`, `wds-5-agentic-development`

**Feeder BRIDGE (16 skills) — feeds data into an existing QR:**
- `bmad-testarch-*` (atdd, automate, ci, framework, nfr, test-design, test-review, trace)
- `bmad-qa-generate-e2e-tests`
- `gds-test-*` (automate, design, framework, review)
- `gds-e2e-scaffold`, `gds-performance-test`, `gds-playtest-plan`

### 12.3. Manual Verification

```bash
# Verify a single experiment
python3 skills/bmad-research-experiment/scripts/run_experiment.py \
  --verify --record docs/experiments/E-001.md

# Full experiment inventory
for f in docs/experiments/E-*.md; do
  python3 skills/bmad-research-experiment/scripts/run_experiment.py \
    --verify --record "$f"
done
```

### 12.4. Reviewing the Audit Log

```bash
# All audit records
cat .metodoloji/logs/hook-audit.log

# Last 10 records
tail -10 .metodoloji/logs/hook-audit.log

# Filter for a specific tool
grep '"tool": "file_editor"' .metodoloji/logs/hook-audit.log

# Warnings
grep 'methodology_warnings' .metodoloji/logs/hook-audit.log
```

---

## 13. Troubleshooting

### 13.1. "No approved experiment record" Error

**Cause:** The file you are trying to write code to is outside the scope of an approved experiment record.

**Solution:**
```bash
# 1. Create a new experiment
cp templates/_template_E.md docs/experiments/E-001.md

# 2. Fill in the experiment (add the Code Scope field)
# docs/experiments/E-001.md → Code Scope: src/yourfile/**/*.py

# 3. Run the gate
python3 skills/bmad-research-experiment/scripts/run_experiment.py \
  --record docs/experiments/E-001.md \
  --run "python scripts/bench/benchmark.py"

# 4. Continue writing code
```

### 13.2. "Gate key not configured" Error

**Cause:** The `~/.bmad/gate-key` file does not exist.

**Solution:**
```bash
python3 skills/bmad-research-experiment/scripts/run_experiment.py --init-secret
```

### 13.3. "Hook engine could not run" Error

**Cause:** Python3 not found or engine files missing.

**Solution:**
```bash
# Python check
python3 --version  # must be 3.11+

# Engine files check
ls -la hooks/engine/main.py
ls -la hooks/engine/modules/

# Import test
python3 -c "import sys; sys.path.insert(0, 'hooks/engine'); import main; print('OK')"
```

### 13.4. "BRIDGE merge problem" Warning

**Cause:** The BRIDGE step in the custom TOML did not merge with deep_merge.

**Solution:**
```bash
# Test bridge visibility
python3 hooks/engine/resolve_customization.py \
  -s skills/bmad-dev-story \
  -k workflow.activation_steps_append

# The output should contain "BRIDGE"
```

### 13.5. "Story experiment validation failed" Error

**Cause:** The `experiment_refs` in the story file is invalid or the experiment record does not exist.

**Solution:**
1. Check that the `docs/experiments/E-XXX.md` file exists
2. Is the experiment status `APPROVED`?
3. Validate the token with `run_experiment.py --verify`

### 13.6. Stop Hook Is Not Closing the Session

**Cause:** There is an incomplete story or an unapproved code change.

**Solution:**
```bash
# Check the sprint status
cat bmad-output/implementation-artifacts/sprint-status.yaml

# Complete or change the status of in-progress stories
# Add experiment scope for unapproved files
```

---

## 14. Frequently Asked Questions

### Q: What do the `quality_gate` / `deploy_guard` soft/hard modes do?

**A:** In the OpenHands runtime, these values are **now enforced at the hook level**:
- `quality` hook: DENY on `git commit` if IR/QR/SP are missing (fail-closed)
- `deploy` hook: DENY on deploy commands if IR/QR/SP/PR are missing (fail-closed)
- `guard` hook: experiment approval + story metadata validation when writing code (fail-closed)
- `stop` hook: in-progress story check at session close (fail-closed)

The `quality_gate`/`deploy_guard` config values sit on top of this mechanical
enforcement at the hook level.

### Q: Can I write code in the `scratch/` directory without an experiment?

**A:** Yes. `scratch/` is a free zone; the guard does not audit it.
However, code here can never go to production — it is for exploration only.

### Q: Can I share my gate key with someone else?

**A:** No. The gate key is machine-local; each developer must
generate their own key. Sharing breaks HMAC security.

### Q: Can multiple experiments be active at the same time?

**A:** Yes. Each experiment defines its own scope (glob). The guard checks whether
the target file falls within the scope of any active experiment.

### Q: Is the old `bmad-hooks.py` file still used?

**A:** No. The single-file `bmad-hooks.py` has been removed. All references
point to the modular engine (`hooks/engine/main.py` + `modules/`).

### Q: How do I update the plugin?

```bash
cd /path/to/metodoloji
git pull
```

### Q: How do I remove an item from a custom TOML?

**A:** There is no deletion mechanism. To disable an item:
1. Fork the skill
2. Or override the item with that code/id using a noop description

---

## 15. Glossary

| Term | Definition |
|------|------------|
| **BMAD** | Build Methodology for Agent-Driven development |
| **Guard** | PreToolUse hook — the mechanical gate that blocks code writing (experiment + story metadata) |
| **Quality** | PreToolUse hook — the gate that enforces the IR/QR/SP chain on `git commit` |
| **Deploy** | PreToolUse hook — the gate that enforces the IR/QR/SP/PR chain on deploy commands |
| **Audit** | PostToolUse hook — the audit trail that logs every tool call + BRIDGE warning |
| **Stop** | Stop hook — the mechanical gate that blocks session close |
| **BRIDGE** | The TOML step that links a native skill output to a methodology record |
| **Gate Key** | Machine-local key used for HMAC validation |
| **Gate Token** | The GATE-OK-... signature produced by an experiment approval |
| **Fail-Closed** | Block by default (DENY) if the engine cannot run |
| **Fail-Open** | Allow by default if the engine cannot run |
| **Free Zone** | Directories/files outside guard audit (scratch/, docs/, .git/) |
| **Code Target** | Files protected by the guard (.py, .js, .ts, Makefile, etc.) |
| **Drift** | The difference between the plugin's installed copy and the repo canonical |
| **Deep Merge** | Recursively merging TOML tables |
| **Memlog** | Working memory logging utility (.memlog.md) |
| **Methodology Chain** | The E → IR → SP → S → QR → PR link structure — each link is mechanically enforced |
| **Mode A** | Quantitative/empirical experiment mode (the only path to code production) |
| **Mode B** | Qualitative research mode |
| **Mode C** | Design mode |
| **Mode D** | Contextual research mode |

---

## Appendix: Quick-Start Commands

```bash
# 1. Plugin installation
git clone https://github.com/yunusgungor/openhands-metodoloji.git

# 2. Initial setup (in the OpenHands session)
/metodoloji:init          # Install the record skeleton
/metodoloji:gate-setup      # Generate the gate key

# 3. Create an experiment and get approval
cp templates/_template_E.md docs/experiments/E-001.md
# → Fill in E-001.md (hypothesis, scope, metric)
python3 skills/bmad-research-experiment/scripts/run_experiment.py \
  --record docs/experiments/E-001.md \
  --run "python scripts/bench/bench.py"

# 4. Start writing code
# → Guard now allows the src/ scope

# 5. Health check
sh commands/check-plugin.sh
/metodoloji:audit

# 6. Create records
python3 scripts/create-methodology-record.py --story path/to/story.md
python3 scripts/create-qr-record.py --story path/to/story.md
```

---

> **Note:** This document applies to the `metodoloji` plugin v1.0.0. It should be
> updated as the plugin evolves. For the latest updates, see the repository:
> https://github.com/yunusgungor/openhands-metodoloji
