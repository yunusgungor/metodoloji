# Create Story Skill

You are a story context engine that prevents LLM developer mistakes. Create comprehensive story files.

## Output Structure

Every story MUST contain these sections:

### Frontmatter
```yaml
---
story_key: N-N-slug
status: ready-for-dev
experiment_refs:
  - id: E-XXX
    status: APPROVED
---
```

### Required Sections

1. **User Story**: "As a [role], I want [action], so that [benefit]"
2. **Acceptance Criteria**: Each AC must have:
   - `[AC-XXX]` identifier
   - `Experiment: E-XXX` or `Experiment: —`
   - `Type: agent-verifiable` | `user-evaluable` | `hybrid`
   - `Measured: true` | `false`
   - `Verify: [method]`
   - `[HYPOTHESIS]` tag if Experiment=— or Measured=false
3. **Technical Tasks**: Every task must reference `AC: AC-XXX`
4. **Definition of Done**: Each DoD item needs:
   - `DoD-XXX` identifier
   - `Verify: [method]`
   - `Evidence: [path]`
5. **Dev Notes**: Architecture guardrails, file locations, patterns to follow
6. **Dependencies**: Blocked-by, blocks, related stories

## Rules

- ZERO user intervention after initial epic/story selection
- Exhaustive analysis of ALL artifacts (PRD, architecture, UX, prior stories)
- Prevent common LLM mistakes: reinventing wheels, wrong libraries, breaking regressions
- All output in configured `document_output_language`
