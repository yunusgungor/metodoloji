---
description: Generate the machine-local ~/.bmad/gate-key used by the methodology's mechanical gates.
---

# /metodoloji:gate-setup — Generate the gate key (gate-key init)

The methodology's mechanical gates (Mode A approval, QR/PR hard mode) perform HMAC
verification with the machine-local key in `~/.bmad/gate-key`. This file must be
**outside the repo, with 0600 permissions**, and is never committed.

## Steps

1. If `~/.bmad/gate-key` exists: say "already installed" and finish (do not overwrite —
   old evidence would break).

2. If not, run this command:
   ```sh
   python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py --init-secret
   ```

3. Verify the result: does the file exist, is its permission 0600? **Never** print,
   copy, or move the key content — the guard blocks such traces.

4. If a `GATE-OK-...` token example appears in the output, setup is complete. Next step:
   create the first experiment record (`docs/experiments/E-001.md`) so the guard-code
   allows code writing.
