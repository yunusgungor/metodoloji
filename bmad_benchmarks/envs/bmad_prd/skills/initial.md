# PRD Skill

Create, update, or validate a Product Requirements Document.

## Output Structure

### Frontmatter
```yaml
---
status: final
updated: YYYY-MM-DD
---
```

### Required Sections

1. **Overview**: Product vision, target users, problem statement
2. **Goals**: Measurable success criteria with numeric targets
3. **User Stories**: Role-action-benefit format with priority
4. **Requirements**:
   - Functional requirements (grouped by feature)
   - Non-functional requirements (performance, security, scalability)
   - Constraints and assumptions
5. **Success Metrics**: KPIs, measurement methods, baselines
6. **Risks**: Identified risks with mitigation strategies
7. **Timeline**: Milestones and dependencies
8. **Open Questions**: Unresolved items requiring decisions

## Process

1. **Elicit**: Gather product intent, constraints, audience. Seed the memlog with the session intent: `python3 {metodoloji-root}/hooks/engine/memlog.py init --workspace {doc_workspace} --field purpose="<PRD/product name>"` — `purpose` is read by the hook engine (intent bridge).
2. **Draft**: Generate comprehensive PRD with all sections
3. **Review**: Validate completeness, consistency, testability
4. **Finalize**: Apply reviewer gate, triage open items, set status: final

## Rules

- Jobs-to-be-Done over template filling
- User value first, technical feasibility is a constraint
- Every requirement must be testable/measurable
- No ambiguous language ("should", "might", "fast")
- Constraints section must list real blockers, not wishes
