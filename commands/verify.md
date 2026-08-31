# /metodoloji:verify — Verify an experiment record

Verifies whether the `{project-root}/docs/experiments/<experiment-id>.md` record is
APPROVED and whether the gate token is not forged.

## Usage

```sh
python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py \
  --verify --record {project-root}/docs/experiments/<experiment-id>.md
```

## Meaning of outputs

| Output | Meaning | What to do |
|---|---|---|
| `VERIFIED` | Record is APPROVED and token is valid | the guard allows code writes matching the globs in the record's `Code Scope` field |
| `FORGED` | Token does not match the key | record invalid — no code can be written; regenerate the record (`--record ... --run <command>`) |
| `REJECTED` / other | Did not pass the gate | revise the hypothesis, measure again |

The guard already performs this verification before code is written; this command is for manual checks.
