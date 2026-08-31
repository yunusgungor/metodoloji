# /metodoloji:audit — Methodology health check (plugin variant)

Mechanically audits the plugin's own integrity and the record discipline in the target project.

## Steps

1. Plugin integrity: run this script and summarize the result:
   ```sh
   sh {metodoloji-root}/commands/check-plugin.sh
   ```
   (0 issues = HEALTHY; §5c custom/ static quality check runs inside this script
   as §5c — no need to run it separately)

2. Custom/ bridge TOMLs (only if an audit is requested): run `commands/check-custom.sh`
   to see §0–§7 in detail. `check-plugin.sh` §5c already runs the same sections; this
   step is only used when a custom/-focused report is wanted.

3. Record chain status: list the records under `{project-root}/docs/experiments/` and
   `{project-root}/docs/development/`; note chain link gaps (e.g. S exists but no QR).

4. Approved experiment inventory: run `--verify` on each E record and report the
   VERIFIED/FORGED distribution (`/metodoloji:verify` logic).

5. Hook configuration: read the `quality_gate`/`deploy_guard` values in
   `custom/config.toml [hooks]` (soft/hard; not bound hooks in OpenHands —
   guard/stop run fail-closed).

6. Result report: PASS/FAIL list + fix suggestions. If you find an issue requiring a
   negative test (e.g. bridge cannot resolve), show the script's
   break→catch→restore output; prove the custom/ drift check is live with
   `check-custom.sh --negtest`.
