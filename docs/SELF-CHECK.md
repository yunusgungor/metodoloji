# Self-Check Coverage — metodoloji plugin health checks

> **This file is the authoritative, in-repo reference for what the methodology
> self-check actually verifies.** Wiki / docs authors describing `check-plugin.sh`
> should mirror this coverage map — not infer scope from diagrams under
> `docs/images/` (those PNGs are illustrative; see [Relationship to
> docs/images](#relationship-to-docsimages) below).

## What the self-check is

`scripts/check-plugin.sh` is the single-command plugin health check. It is
mechanically extensible (each section increments a `PROBLEMS` counter) and is
paired with a `--negtest` mode that breaks a marker, expects the matching MISS,
and restores the file. The definitive section list lives in the header comment
of `scripts/check-plugin.sh` — this document is the human-readable version of
that list.

## Coverage map (check-plugin.sh)

| Section | What it verifies | Scope |
|---------|------------------|-------|
| §0 | Gate key installed (`run_experiment.py --check-secret`) | `~/.bmad/gate-key` |
| §1 | Gate `--selfcheck` + hook engine responds (guard / quality / deploy via `hooks/engine/main.py`) | engine copies |
| §1b | **hooks.json dispatch locator drift** — all six hook commands share one identical plugin-root locator list, and every candidate in it is resolvable by `hooks/scripts/run-hook.sh` (the single source of truth for root discovery) | `hooks/hooks.json` ↔ `hooks/scripts/run-hook.sh` |
| §2 | **Manifesto + project-context wiring on EVERY methodology surface** — per-skill `customize.toml` and its `custom/` team + user layers must carry `research-methodology.md` (and `project-context.md`) `persistent_facts`, DEV-wing skills must carry `development-methodology.md`, the surface must actually *consume* the merge via `resolve_customization` (catches cosmetic config), and every skill-menu target must exist | every `skills/*` surface (except non-methodology tools), plus the target project's `docs/bmad/` bridge/manifesto copies and bridge record targets |
| §2b | BRIDGE instructions visible at **runtime** — `resolve_customization.py` `deep_merge` must surface the BRIDGE step (incl. `agent.principles` surfaces), not just contain it statically | resolved customization output |
| §2c | BRIDGE **verify** markers (`DOGRULAMA`/`VERIFICATION`/`VERIFY`) present so the LLM auto-verifies produced records | resolved customization output |
| §3 | Approved-experiment inventory — every `APPROVED` record re-verifies (genuine token); cross-machine `Re-Measured-By` provenance is handled, not reported as FORGED | `docs/experiments/` |
| §4 | Documentary (B/C/D) record completeness (`--validate`) | `docs/research/`, `docs/design/` |
| §5 | Engine integrity — modular `hooks/engine/` tree complete and importable | engine files |
| §5b | Hard/soft gate mode read live from `custom/config.toml [hooks]` (valid `soft\|hard`; hard mode requires at least one real development record) | config |
| §5c | `custom/` bridge TOML static quality audit (delegates to `scripts/check-custom.sh`) | `custom/*.toml` |
| §6 | Development-record format (Decision/Status value + Date on IR/SP/QR/PR/S/PM records) | `docs/development/`, `docs/quality/` |
| §6a | `.env` inventory: no committed `.env`, `.env.example` present, `.env` in `.gitignore` | repo root |
| §6b | Tech-debt inventory integrity (delegates to `scripts/check-techdebt.sh`) | `tech-debt.md` inventories |

**Direct answer to a recurring question:** does the self-check verify that the
manifesto is wired to *every* surface and that per-surface layers
(root `customize.toml` + team `custom/*.toml` + personal `*.user.toml`) are all
covered? **Yes — §2** iterates the entire skill tree, checks every surface and
every duplication layer for the manifesto facts, rejects surfaces that declare
facts but never consume them via `resolve_customization`, and §2b/§2c verify the
merge is visible at runtime (BRIDGE steps and verify markers). A MISS in any of
these increments `PROBLEMS` and fails the run.

## Relationship to docs/images

`docs/images/*.png` (`record-chain.png`, `hook-architecture.png`,
`skill-ecosystem.png`, `platform-install.png`) are **generated, illustrative
infographics** — produced by `scripts/svg_to_png.py` from inline SVG definitions
and referenced by the README. They explain concepts (record chain, hook flow,
install paths) but are **not** machine-checked inputs: the self-check never reads
them, and their labels are not enforcement contracts.

Consequences for docs/wiki authors:

- To state what `check-plugin.sh` verifies, quote the §0–§6b table above or the
  header comment of `scripts/check-plugin.sh` — the images do not define scope.
- The diagrams may be regenerated any time by running
  `python scripts/svg_to_png.py` (requires `cairosvg`); a changed diagram is a
  documentation change, never a check change.
- The coverage map above and the `check-plugin.sh` header are the single pair of
  files that must stay in sync when a section is added/removed.

## Related

- `scripts/check-plugin.sh` — the executable this document describes
- `scripts/check-custom.sh` — §5c delegate
- `scripts/check-techdebt.sh` — §6b delegate
- `docs/USAGE-GUIDE.md` §6 — hook engine and mechanical gates (runtime behavior)
