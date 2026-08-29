# Test Design Skill

Create system-level or epic-level test plans using risk-based methodology.

## Output Structure

### Test Plan Sections

1. **Test Strategy**: Overall approach, entry/exit criteria
2. **Test Levels**: Unit, Integration, E2E with coverage targets
3. **Test Scenarios**: Organized by feature/risk:
   - Happy path scenarios
   - Edge cases and boundary conditions
   - Negative/error scenarios
   - Performance/security scenarios
4. **Risk Assessment**: Risk matrix (probability × impact)
5. **Traceability Matrix**: Story → Test → Evidence mapping
6. **Automation Plan**: What to automate, framework selection
7. **Environment Requirements**: Test data, services, tools

## Test Categories (must cover)

- **Unit**: Isolated component tests, fast feedback
- **Integration**: Service/API interaction tests
- **E2E**: Full user journey tests
- **Edge Case**: Boundary values, empty inputs, overflow
- **Negative**: Error handling, invalid inputs, security

## Rules

- Risk-based prioritization (p1/p2/p3)
- Every AC maps to at least one test
- ATDD red-phase scaffolds when applicable
- Test data strategy defined per scenario
- Evidence collection plan for each test level
