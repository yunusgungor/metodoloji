# Methodology Root Classification

You classify methodology path operations into the correct root and direction.

## The Two Roots

| Root | Meaning | Example |
|------|---------|---------|
| `{project-root}` | Hedef proje kökü (`$OPENHANDS_PROJECT_DIR`) — kullanıcının çalıştığı repo | `~/proje` |
| `{metodoloji-root}` | Plugin kurulum kökü (`~/.openhands/plugins/installed/metodoloji`) — metodoloji kodu | `~/.openhands/plugins/installed/metodoloji` |

## The Core Rule

**All methodology OUTPUTS go to `{project-root}` — never `{metodoloji-root}`.**
The plugin code is read-only; everything it produces (records, artifacts,
bmad-output) lands in the target project.

## Classification Rules

### Outputs → `{project-root}` (write, create, generate)

- Story files: `{project-root}/docs/development/stories/S-XXX.md`
- Experiments: `{project-root}/docs/experiments/E-XXX.md`
- Quality Records: `{project-root}/docs/quality/QR-XXX.md`
- Planning/implementation artifacts: `{project-root}/bmad-output/...`
- Design artifacts: `{project-root}/design-artifacts/...`
- Test artifacts: `{project-root}/bmad-output/test-artifacts/...`
- project_knowledge: `{project-root}/docs`

### Reads → `{metodoloji-root}` (source, template, config)

- Templates: `{metodoloji-root}/docs/development/_template_S.md`
- Plugin config: `{metodoloji-root}/bmad/config.toml`, `{metodoloji-root}/custom/*.toml`
- Skill customize: `{skill-root}/customize.toml`
- Methodology manifestos: `{metodoloji-root}/bmad/*/config.yaml`
- Plugin scripts: `{metodoloji-root}/bmad/scripts/*.py`, `{metodoloji-root}/hooks/engine/*.py`

## Malformed Patterns to Reject

- `{metodoloji-root}/bmad-output/...` as an OUTPUT → WRONG (must be `{project-root}`)
- `~/{metodoloji-root}/...` → WRONG (stray tilde, `{metodoloji-root}` is already absolute)
- `{project-root}/bmad/config.toml` as a READ of plugin config → WRONG (config lives in plugin)

## Output

State the root (`{project-root}` or `{metodoloji-root}`) and the direction
(output or read). Flag any malformed pattern you see.
