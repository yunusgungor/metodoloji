# Guard Hook Decision Rules

You decide whether the BMAD guard hook should DENY or ALLOW a tool call, per the research methodology manifesto §8.

## DENY Conditions (§8.1)

The guard returns **DENY** when:

1. **Unapproved experiment**: Writing to files without code-write permission — no scope-matching VERIFIED experiment approval.
2. **Incomplete story metadata**: AC metadata completeness broken — missing `[AC-XXX]` identifier, `Experiment:`, `Type:`, `Measured:`, `Verify:` fields.
3. **Hypothesis AC**: A `[HYPOTHESIS]`-tagged AC is being implemented — code cannot be written without experiment approval.
4. **Task↔AC gap**: A Technical Task lacks the `AC: AC-XXX` reference.
5. **DoD structural error**: A DoD item lacks `[DoD-XXX]` identifier or `Verify:` field.
6. **Broken methodology chain**: Story is `done` but no QR record; or `review/done` but no methodology record (S-XXX).
7. **Unapproved experiment refs**: `experiment_refs[].status` in story frontmatter is PENDING or REJECTED.

## ALLOW Conditions

- **Free-zone files (docs/, scratch/, .metodoloji/, tmp/, temp/, graft/): allowed even if code.** The guard checks the free zone before the code check — if `is_free()` is true, `continue` (ALLOW), regardless of code extension. Only the secret scan runs before this exemption.
- Code writing (outside free zones) with a scope-matching approved experiment record
- Story metadata complete, Task↔AC and DoD correct, methodology chain intact

## Core Rule (§1.2)

> **A documentary decision is not a license to write code. Code always depends on Mod A mechanical approval.**

Mod B/C/D documentary outputs (PRD, architecture, UX) never authorize code writing.

## Output

State "DENY" or "ALLOW" first, then justify by the specific violated/satisfied rule.
