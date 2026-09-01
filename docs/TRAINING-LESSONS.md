# BMAD SkillOpt Training — Lessons & Bottlenecks

Learned training `bmad-meta-root` end-to-end with SkillOpt (ReflACT). These are
the bottlenecks we hit and the approaches that got past them. Apply to any BMAD
benchmark before running a training.

## 1. `sel_env_num`/`test_env_num` truncation silently kills learning

**Symptom:** `accept=0` forever, `best_score == baseline`, every step
`skip_no_patches` or `reject`.

**Cause:** The base config defaulted to `sel_env_num: 4`. The gate only
evaluated the **first 4 alphabetically-sorted val items** — usually the easy
ones. Harder items (traps, edge cases) were never seen by the gate, so
ReflACT had no failure signal to optimize. Test eval had the same truncation.

**Fix (applied to `_base_/default.yaml`):**
```yaml
evaluation:
  sel_env_num: 0   # 0 = whole split; build_eval_batch treats env_num=0 as "no truncation"
  test_env_num: 0
```
Always let the gate/test see the **entire** split. If you add hard items,
they must be visible to the gate or the optimizer will never target them.

## 2. A model that already scores ~100% leaves nothing to learn

**Symptom:** baseline 1.0 → `accept=0`, training is a waste of tokens.

**Cause:** If the target model already classifies the task perfectly
(e.g. `deepseek-v4-flash` on a simple 2-axis classification), no skill patch
can beat the baseline and the gate rejects everything.

**Fix:** pick a **weaker** model so the skill optimizes something real.
`bmad-meta-root` only started learning when we switched to `laguna` (weaker),
which dropped the baseline to 0.7778 and let ReflACT push it to 0.8889.
Verify the model has room before training: measure a skill-less baseline
on a sample — you want it in the 0.6–0.8 range, not ≥0.9.

## 3. Gateway errors (503/429) returned *as the response body* bypass the SDK retry

**Symptom:** some rollouts are `hard:0` with the *exact text*
`[CommandCode error: {"statusCode":503,...}]` in the conversation, while the
backend's own `retries=5` never fires.

**Cause:** The proxy returns the 503 inside a 200 OK response body — the SDK
sees a normal reply, so its retry loop never triggers.

**Fix (applied to `_base_/rollout.py`):**
1. **Detect** gateway-error text in the returned `output_text` and **retry at
   the rollout layer** (exponential backoff).
2. **Drop** rollouts that still fail from the reflect-facing results list —
   otherwise reflect reads an infrastructure error as a *model* failure and
   patches the skill for the wrong reason (e.g. it added "do not touch files"
   to a classification skill). An exception path must also carry the raw error
   text so the same filter catches it.

`laguna` had a ~55% 503 rate; `kc/poolside/laguna-s-2.1:free` was stable.

## 4. Free/weak models are rate-limited mid-training

**Symptom:** mid-training `429 rate limit (reset after Nm)` — later steps all
skip or fail.

**Cause:** `-free` models have low per-minute quotas; a training loop burns
them fast.

**Fix:** if the model rate-limits, stop rather than let steps burn tokens
against 429s. A weaker-but-stable model beats a strong-but-throttled one.

## 5. Reverse traps must not name the wrong root in the path text

**Symptom:** a "config-in-project" trap — `read the bridge configuration from
`{project-root}`/bmad/config.toml` — model answered `{project-root}` because
the path *said* `{project-root}`, ignoring the skill rule "config = plugin".

**Cause:** the model anchors on the explicit path text, not on the file kind.
A path that names the *wrong* root overrides the skill's "decide by what the
file is" rule.

**Fix (applied to `bmad_meta_root/data/`):** phrase reverse traps **without a
path** — `read the bridge configuration file`. The model must then rely on the
skill rule (`config/TOML → plugin`) instead of the path. Path-less traps scored
3/3 consistent, vs 0/3 for path-named ones.

## 6. Score the model's explicit declaration, not regex over the reasoning

**Symptom:** correct answers scored `0.5`:
- `"resolves to {metodoloji-root} ... rather than a write to {project-root}"`
  → scorer took the *rejected* `{project-root}` as the real root.
- `"... but it's invalid; the correct destination would be under
  {project-root}"` → scorer took the *invalid target* root.

**Cause:** regex over the whole free-form reasoning lets a rejected/named-but-
excluded anchor win.

**Fix (applied to `bmad_meta_root/rollout.py`):** trust the model's **explicit
declaration first**, in priority order:
1. `correct/right/valid ... destination ... {root}` — the *correct* root wins
   over a named-but-invalid target.
2. `Root anchor: {root}` / `Anchor: {root}` / `resolves against/to {root}`.
3. Fallback: regex over verbs/anchors, honoring `rather than` / `instead of` /
   `not the` rejection markers.
Also support the formats the model actually emits: `**Root anchor:**`,
`**Anchor:**`, backticks around `{root}`, and `Direction: reads/writes`.

## 7. Initial skill over-specification leaves nothing to learn

**Symptom:** baseline 1.0 with the *initial* skill; the skill itself already
stated every answer (manifesto → project, config → plugin, trap list).

**Cause:** if `initial.md` is a complete answer key, ReflACT has nothing to add.

**Fix:** keep `initial.md` to **principles** (the read-only rule, source vs
product), and let the training data force the specifics. But balance this with
lesson #5: the specific file-kind mapping *can* go in the skill (a weak model
won't infer it) — the learning signal comes from data the skill doesn't
spell out verbatim.

## 8. Promote a real accepted gain into `initial.md`

When training accepts a `best_skill.md` (0.7778 → 0.8889), copy it back to
`bmad_benchmarks/envs/<bench>/skills/initial.md` so future runs start from the
improved baseline instead of re-learning it. Commit it.

## 9. Verify the gain against the *actual* methodology

Trained rules can contradict reality. When applying a gain:
- **Scan real skills** for violations of the trained rule (config read from
  `{project-root}` vs `{metodoloji-root}`, manifestos read from the plugin,
  plugin writes beyond the customization layer).
- `bmad-customize` was reading `bmad/config.toml` from `{project-root}` while
  every other skill read it from `{metodoloji-root}` — fixed.
- Document the rule in `docs/USAGE-GUIDE.md` Root Resolution Rules and note the
  one **deliberate exception**: `bmad-customize` writes user overrides under
  `{metodoloji-root}/custom/` (the plugin is read-only for *output*, not for
  the customization layer).

## Checklist before any training run

1. `sel_env_num: 0`, `test_env_num: 0` (whole split on gate + test).
2. Measure a **skill-less baseline** on a sample: want 0.6–0.8, not ≥0.9.
3. Model is stable (no 503/429 storms); retry+drop filter is in `_base_`.
4. Reverse traps are **path-less** (don't name the wrong root).
5. Scorer trusts explicit declarations (`Root anchor:`, `correct destination`,
   `resolves against`) and handles model-emitted formats.
6. Data coverage verified (`verify_combinations` passes).
