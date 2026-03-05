---
name: code-implementation
description: Use when implementing features, writing new code, adding functionality, refactoring, or fixing bugs where root cause is known. Also use when the user says "implement", "build", "add feature", or requests a function/module/service. Includes planning, approval gate, test-driven development, and code review.
---

# Code Implementation Skill
**Usage:** /code-implementation "task description"

**Trigger this skill when:**
- User asks to implement/build/add code or a feature
- User requests a function/module/service to be written
- Complex coding tasks requiring design decisions
- Multi-file changes that benefit from upfront planning
- Bug fixes that require non-trivial coding (after root cause is known)

**Skip for:** Pure analysis, docs-only tasks, minor tweaks that don't need a plan

## Full-Stack by Default

**Every backend feature needs a frontend.** Unless the user explicitly says "backend only", assume the feature requires:
1. Backend implementation (API endpoints, services, models)
2. Frontend integration (API client, types, store, components, pages, routing)

If you implement a backend endpoint without surfacing it in the UI, the feature is **incomplete**.

## Execution Workflow

### Phase 0: Architecture Context (if applicable)

**When invoked from /system-arch or when architecture context exists:**
- Review the approved architecture decision
- Extract specific implementation requirements:
  * Components to create/modify
  * Interface contracts and APIs
  * Data flow requirements
  * Success metrics from architecture plan
- Ensure test strategy aligns with architectural requirements
- Note any architectural constraints that affect implementation

### Phase 1: Understand & Bound
- Capture requirements and constraints (inputs/outputs, interfaces, performance, edge cases)
- Identify affected components/files — **both backend AND frontend**
- Fire `explore` agent to find related code patterns if needed
- Note non-functional needs (tests, types, logging, telemetry)
- **Frontend surface audit:** Which pages/components consume this data? What new UI is needed?

### Phase 2: Plan (checklist-driven)
Produce a concise plan before coding:
- Scope & assumptions
- Key design decisions (with rationale and alternatives considered)
- Files to touch (including test files)
- Steps to implement (ordered)
- **Test cases required** (unit, integration, edge cases)
- Tests/verification commands
- Rollback notes

Use this template:
```markdown
## Implementation Plan
- Scope/assumptions: ...
- Key Design Decisions:
  | Decision | Rationale | Alternatives |
  |----------|-----------|--------------|
  | [Choice] | [Why] | [Other options] |

### Backend
- Files: [...]
- Test Files: [...] (MANDATORY: list all test files to create/modify)

### Frontend
- API layer: [types, endpoints, client changes]
- Store: [new/modified Zustand store]
- Components: [new/modified components]
- Pages: [new/modified pages]
- Routing: [App.tsx route changes, if any]
- **Design skill needed?** [Yes → invoke /frontend-design for non-trivial UI | No → standard components]

### Test Cases Required
  * Unit tests: [...]
  * Integration tests: [...]
  * Edge cases: [...]
- Steps:
  1) ...
  2) Write tests for [component] (BEFORE implementation)
  3) Implement backend [component]
  4) Add frontend types + API client
  5) Build store/hooks
  6) Build components/pages
  7) Wire routing
  8) ...
- Tests/verify: `...`
- Rollback: ...
```
Only start coding after the plan is written. Keep the plan updated if scope changes.

**CRITICAL: Test-Driven Approach**
- Write test cases BEFORE implementing each component when possible
- Every new function/module MUST have corresponding tests
- Aim for >80% code coverage on new code

### Phase 2.5: Approval Gate (for complex changes)

**For multi-file changes, architectural decisions, or ambiguous requirements:**
1. Present the plan to the user
2. Highlight any assumptions or open questions
3. Wait for explicit approval or feedback
4. If changes requested, update plan and re-present

**Skip this gate for:** Small, well-defined tasks where the path is clear.

### Phase 3: Implement
- Follow the plan steps in order; keep changes minimal and focused
- Prefer existing patterns; match project style
- **Test-first workflow:**
  1. Write test case for a component/function
  2. Run test (expect it to fail - "red")
  3. Implement the component/function
  4. Run test again (expect it to pass - "green")
  5. Refactor if needed while keeping tests green
- Run `lsp_diagnostics` on changed files after each logical unit
- Ensure test files are created/updated for ALL new code

**Delegation Rules** — delegate to subagents when:
- Subtask is self-contained and complex
- Subtask requires deep specialized knowledge
- Parallel execution would improve efficiency

Delegation prompt template:
```
TASK: [Specific atomic goal]
CONTEXT: [Relevant code snippets, constraints, patterns to follow]
EXPECTED OUTCOME: [Specific deliverable]
MUST DO: [Requirements]
MUST NOT DO: [Forbidden actions]
```

**Frontend Integration Steps** (after backend is working):

1. **Types** — Add/update TypeScript interfaces in `api/types.ts` matching backend Pydantic schemas
2. **API client** — Add endpoint functions in `api/endpoints.ts` calling the new backend routes
3. **Store** — Create or extend a Zustand store in `stores/` for state management
4. **Hooks** — Add custom hooks in `hooks/` if needed (WebSocket, polling, derived state)
5. **Components** — Build reusable UI components in `components/`
6. **Pages** — Create or update pages in `pages/` that compose the components
7. **Routing** — Add routes in `App.tsx` if new pages were created
8. **Design quality** — For non-trivial UI, invoke `/frontend-design` skill for aesthetic direction

**Contract alignment:** Frontend types MUST mirror backend response schemas exactly. Read the backend Pydantic models or API response shapes before writing TypeScript interfaces.

**Test Coverage Requirements:**
- [ ] Unit tests for all new functions/methods
- [ ] Integration tests for cross-component interactions
- [ ] Edge case tests (null, empty, boundary values)
- [ ] Error handling tests (exceptions, failures)

### Phase 4: Verify (COMPREHENSIVE)
- Run ALL planned tests/commands
- Check test coverage metrics (if available)
- Verify tests cover:
  * Happy path scenarios
  * Error conditions
  * Edge cases
  * Integration points
- **Frontend verification:**
  * TypeScript compiles cleanly (`npm run build` or `npx tsc --noEmit`)
  * New components render without console errors
  * API client functions match backend response shapes
  * Routes are reachable and render correct pages
- If ANY failures occur, fix and re-run until ALL tests green
- Document test results in summary

### Phase 5: Code Review (MANDATORY)
- Invoke the **code-reviewer** agent (see AGENTS.md) after implementation & self-verification
- Address review findings; rerun verification if code changes

### Phase 6: Summarize
- Summarize changes, tests run, and status vs plan
- Call out any deviations or TODOs

### Phase 7: Explain (only if user asks)
- If the user requests an explanation of the new code, use the **Explain** skill (/explain) or the **tutor** agent to provide a concise walkthrough (what it does, how it works, key flows)

## Quality Guidelines

**ALWAYS:**
- Plan before you code; keep it short but specific
- Update the plan if the scope shifts
- Keep diffs tight; avoid drive-by refactors
- Add/maintain tests; keep `lsp_diagnostics` clean
- Use existing patterns and conventions (SOLID, DRY, KISS, YAGNI)
- Run code-reviewer agent before considering the task done

**NEVER:**
- Start coding without a plan
- Skip writing tests for new code
- Write implementation before tests (when TDD is feasible)
- Mark tests as TODO or skip tests
- Ignore failing tests or diagnostics
- Ship code with <80% test coverage
- Write tests after the fact without running them
- Introduce type suppressions (`# type: ignore`, `as any`, `@ts-ignore`)
- Mix unrelated refactors with the requested change

## Escalation Triggers

**Ask User if:**
- Requirements are ambiguous
- Multiple valid approaches exist with trade-offs
- Scope creep detected
- Business logic unclear (intended behavior?)

## Verification Checklist (tick before closing)

**Backend:**
- [ ] Plan created with test cases identified
- [ ] Plan followed/updated throughout implementation
- [ ] Test files created/modified for ALL new code
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing
- [ ] Edge case tests written and passing
- [ ] Error handling tests written and passing
- [ ] Test coverage >80% on new code (if measurable)
- [ ] All tests/commands executed and passing
- [ ] lsp_diagnostics clean on changed files

**Frontend:**
- [ ] TypeScript types match backend Pydantic schemas
- [ ] API endpoint functions added for new backend routes
- [ ] Store created/updated with proper state management
- [ ] Components/pages built and wired to store
- [ ] Routes added in App.tsx (if new pages)
- [ ] Frontend builds cleanly (no TS errors)
- [ ] `/frontend-design` invoked for non-trivial UI work

**Final:**
- [ ] code-reviewer agent run and feedback addressed
- [ ] Summary delivered to user with test results
