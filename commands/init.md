# /metodoloji:init — Install the record skeleton into the target project

This command installs the directories and templates required for the methodology
record chain under **{project-root}**. {metodoloji-root} = this plugin's installation
root (OpenHands: `~/.openhands/plugins/installed/metodoloji`,
Claude Code: `${CLAUDE_PLUGIN_ROOT}` or the repo clone path).

## Steps

1. Create these directories (skip if they exist):
   - `docs/experiments/` — Mode A experiment records (E-NNN.md)
   - `docs/development/stories/` — story records (S-NNN.md)
   - `docs/research/` — Mode B/D documentary records
   - `docs/design/` — Mode C documentary records
   - `docs/bmad/` — manifestos and bridge copies
   - `scratch/` — free zone for exploration code

2. Copy templates (do not overwrite — preserve existing):
   - `{metodoloji-root}/templates/_template_E.md` → `docs/experiments/_template.md`
   - `{metodoloji-root}/templates/_template_IR.md` → `docs/development/_template_IR.md`
   - `{metodoloji-root}/templates/_template_SP.md` → `docs/development/_template_SP.md`
   - `{metodoloji-root}/templates/_template_QR.md` → `docs/development/_template_QR.md`
   - `{metodoloji-root}/templates/_template_PR.md` → `docs/development/_template_PR.md`
   - `{metodoloji-root}/templates/_template_S.md` → `docs/development/stories/_template_S.md`
   - `{metodoloji-root}/templates/README.md` → `docs/development/README.md`
   - `{metodoloji-root}/templates/tech-debt.md` → `docs/development/tech-debt.md`

3. Manifesto copies (source: repo texts instead of the plugin's reference copies):
   - Install the bridge and manifesto copies of this methodology package under `docs/bmad/` if present.

4. If no gate key exists, warn: run `/metodoloji:gate-setup`.

5. Print a summary: installed directories, skipped (existing) files, next step
   (`/metodoloji:audit` health check).
