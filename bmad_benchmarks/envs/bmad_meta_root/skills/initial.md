# Methodology Root Classification

You classify methodology path operations into the correct root and direction.

## The Two Roots

| Root | Meaning | Example |
|------|---------|---------|
| `{project-root}` | Target project root (`$OPENHANDS_PROJECT_DIR`) — the repo the user works in | `~/project` |
| `{metodoloji-root}` | Plugin installation root (`~/.openhands/plugins/installed/metodoloji`) — methodology code | `~/.openhands/plugins/installed/metodoloji` |

## The Core Rule

**All methodology OUTPUTS go to `{project-root}` — never `{metodoloji-root}`.**
The plugin code is read-only; everything it produces (records, artifacts,
bmad-output) lands in the target project.

## Classification Rules — the four combinations

The classification is two independent axes: **root** and **direction**. Every
operation falls into exactly one of these four combinations:

| Combination | Valid? | Meaning |
|---|---|---|
| `{project-root}` + output | ✅ | A record/artifact is CREATED in the target project |
| `{project-root}` + read | ✅ | A project-copied source is READ from the target project |
| `{metodoloji-root}` + output | ❌ **INVALID** | Never write into the plugin — the plugin is read-only |
| `{metodoloji-root}` + read | ✅ | A plugin source (config/template/script) is READ |

### `{project-root}` + output — WRITE into the target project (most common)

- Story files: `{project-root}/docs/development/stories/S-XXX.md`
- Experiments: `{project-root}/docs/experiments/E-XXX.md`
- Quality Records: `{project-root}/docs/quality/QR-XXX.md`
- Planning/implementation artifacts: `{project-root}/bmad-output/...`
- Design artifacts: `{project-root}/design-artifacts/...`
- Test artifacts: `{project-root}/bmad-output/test-artifacts/...`
- project_knowledge: `{project-root}/docs`

### `{project-root}` + read — READ a project-copied source

- Methodology manifestos: `{project-root}/docs/bmad/research-methodology.md`, `{project-root}/docs/bmad/development-methodology.md` — installed into the project by `bmad-customize`, read from the project root.
- Other manifesto/bridge copies under `{project-root}/docs/bmad/`.

### `{metodoloji-root}` + output — INVALID, must be rejected

- Writing a story/record/artifact to `{metodoloji-root}/...` is ALWAYS wrong. The plugin is read-only.
- Correct answer for any "write to plugin" operation: the root is `{project-root}` (the write goes to the project), or the operation itself is malformed and must be flagged.

### `{metodoloji-root}` + read — READ a plugin source

- Templates: `{metodoloji-root}/templates/_template_S.md`
- Plugin config: `{metodoloji-root}/bmad/config.toml`, `{metodoloji-root}/custom/*.toml`
- Skill customize: `{skill-root}/customize.toml`
- Plugin scripts: `{metodoloji-root}/bmad/scripts/*.py`, `{metodoloji-root}/hooks/engine/*.py`

## Malformed Patterns to Reject

- `{metodoloji-root}/bmad-output/...` as an OUTPUT → WRONG (must be `{project-root}`)
- `~/{metodoloji-root}/...` → WRONG (stray tilde, `{metodoloji-root}` is already absolute)
- `{project-root}/bmad/config.toml` as a READ of plugin config → WRONG (config lives in plugin)
- Any write into `{metodoloji-root}/` → WRONG (plugin is read-only; writes go to `{project-root}`)

## Output

State the root anchor (`{project-root}` or `{metodoloji-root}`) and the direction
(writes or reads). If the operation is malformed or invalid, say so. Flag any
malformed pattern you see.
