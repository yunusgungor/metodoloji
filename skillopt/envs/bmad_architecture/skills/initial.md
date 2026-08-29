# Architecture Spine Skill

You produce an architecture spine: a consistency contract fixing only invariants.

## Core Principle

> If two units one level down built this independently, could they choose incompatibly? Fix it here only when the answer is yes, AND the call is non-obvious, AND it's a real trade-off.

## Output: ARCHITECTURE-SPINE.md

### Required Invariants (AD-n format)

Each decision as `AD-n` with:
- **Binds**: What this constrains
- **Prevents**: What divergence this blocks
- **Rule**: The invariant statement

### Invariant Categories (must cover)

1. **Paradigm**: Named design paradigm (MVC, ECS, event-driven, etc.)
2. **Boundaries**: Module/service boundaries and communication patterns
3. **Dependencies**: Dependency direction rules, allowed external deps
4. **State**: How state is mutated, who owns shared data
5. **Ownership**: Data ownership and consistency guarantees

### Deferred Section

List decisions intentionally NOT made here, with revisit conditions.

## Process

1. **Elicit** (Coaching path default): Open-ended questions to pull decisions from user
2. **Draft**: Build spine from decisions, minimal seed
3. **Review**: Lint check + rubric walker + parallel reviewer subagents
4. **Finalize**: Distill from memlog, set status: final

## Rules

- Record decisions, not rationale (rationale lives in memlog)
- Carry shape in diagrams (mermaid), not prose
- Verify named technology's current version on web before binding
- Inherit parent spine invariants as read-only constraints
- No placeholders — mark real gaps as Deferred
