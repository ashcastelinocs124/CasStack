# CasStack

A curated collection of **agents** and **skills** for AI coding assistants. Plug them into [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Codex](https://github.com/openai/codex), or any agent that supports the `.claude/` skill convention and instantly level up your development workflow.

---

## Table of Contents

- [Why Agentarium?](#why-agentarium)
- [What's Inside](#whats-inside)
  - [Agents](#agents)
  - [Skills](#skills)
- [Quick Start](#quick-start)
  - [One-Line Install](#one-line-install)
  - [Manual Install](#manual-install)
- [Agent Reference](#agent-reference)
  - [code-implementation](#code-implementation-agent)
  - [code-reviewer](#code-reviewer-agent)
  - [integration-test-validator](#integration-test-validator-agent)
  - [security-scanner](#security-scanner-agent)
- [Skill Reference](#skill-reference)
  - [code-implementation](#code-implementation-skill)
  - [gitpush](#gitpush)
  - [skill-creator](#skill-creator)
  - [skill-creator-v2](#skill-creator-v2)
  - [skill-graph](#skill-graph)
  - [skill-guard](#skill-guard)
  - [capture-learnings](#capture-learnings)
  - [find-skills](#find-skills)
  - [screen-recording](#screen-recording)
- [Architecture](#architecture)
  - [Agents vs Skills](#agents-vs-skills)
  - [Directory Layout](#directory-layout)
  - [Progressive Disclosure](#progressive-disclosure)
- [Configuration](#configuration)
- [Creating Your Own Skills](#creating-your-own-skills)
- [Contributing](#contributing)
- [License](#license)

---

## Why CasStack?

AI coding assistants are powerful out of the box, but they lack **procedural memory** -- the step-by-step knowledge of *how* to do specialized tasks reliably. Agentarium fills that gap with:

- **Battle-tested workflows** -- multi-phase implementation, review, and deployment pipelines that enforce quality gates
- **Security-first defaults** -- automated secret scanning and sensitive file protection on every push
- **Composable pipelines** -- chain skills together with `skill-graph` to orchestrate complex multi-step tasks
- **Self-improving skills** -- `capture-learnings` and `skill-creator-v2` create a feedback loop where your skills get better over time

---

## What's Inside

### Agents

Agents are autonomous sub-processes that handle complex, multi-step tasks. They run in isolated contexts and return structured results.

| Agent | Model | Description |
|-------|-------|-------------|
| [code-implementation](#code-implementation-agent) | Opus | Plans, proposes, and implements code with approval gates and sub-agent delegation |
| [code-reviewer](#code-reviewer-agent) | Inherit | Reviews completed work against plans, standards, and architectural patterns |
| [integration-test-validator](#integration-test-validator-agent) | Sonnet | Three-tier testing (unit, integration, system) with structured pass/fail reports |
| [security-scanner](#security-scanner-agent) | Inherit | Six-phase security audit covering secrets, OWASP, dependencies, and guardrails |

### Skills

Skills are modular instruction sets that guide the agent through specialized workflows. They load on-demand and stay lean.

| Skill | Description |
|-------|-------------|
| [code-implementation](#code-implementation-skill) | Full-stack feature implementation with TDD, planning, and code review |
| [gitpush](#gitpush) | Safe push workflow with repo/branch confirmation, secret scanning, and deploy options |
| [skill-creator](#skill-creator) | Step-by-step guide for building new skills with scripts, references, and assets |
| [skill-creator-v2](#skill-creator-v2) | Benchmark-driven skill creation with A/B testing via isolated sub-agents |
| [skill-graph](#skill-graph) | Chain multiple skills into a Mermaid-rendered pipeline with approval gates |
| [skill-guard](#skill-guard) | Intercept skill installs to detect overlap; audit existing skills for redundancy |
| [capture-learnings](#capture-learnings) | Extract bugs, gotchas, patterns, and decisions from sessions into `learnings.md` |
| [find-skills](#find-skills) | Discover and install skills from the open ecosystem via `npx skills` |
| [screen-recording](#screen-recording) | Automated browser or Mac app screen capture with post-processing via Remotion |

---

## Quick Start

### One-Line Install

```bash
git clone https://github.com/ashcastelinocs124/Agentarium.git && cd Agentarium && bash setup.sh
```

The setup script will:

1. **Detect your agent** (Claude Code or Codex)
2. **Ask where to install** -- global (`~/.claude/skills/`), project-local (`./.claude/skills/`), or custom path
3. **Collect your GitHub identity** for commit attribution in the `gitpush` skill
4. **Copy and personalize** all skills and agents to your chosen directory

### Manual Install

If you prefer to pick and choose:

```bash
# Clone the repo
git clone https://github.com/ashcastelinocs124/Agentarium.git
cd Agentarium

# Copy a single skill
cp -r skills/gitpush ~/.claude/skills/

# Copy a single agent
cp agents/code-reviewer.md ~/.claude/agents/

# Copy everything
cp -r skills/* ~/.claude/skills/
mkdir -p ~/.claude/agents && cp agents/*.md ~/.claude/agents/
```

---

## Agent Reference

### code-implementation (Agent)

**Model:** Opus | **Color:** Red

An elite implementation engineer that follows a strict 7-phase workflow:

1. **Analysis & Planning** -- break down requirements, identify components, consider edge cases
2. **Proposal & Suggestions** -- present approach with design decisions, alternatives, and trade-offs
3. **Approval & Refinement** -- wait for explicit user approval before coding
4. **Checklist Creation** -- specific, measurable tasks with acceptance criteria
5. **Implementation** -- work through checklist methodically; delegate heavy subtasks to sub-agents
6. **Quality Assurance** -- comprehensive self-review for requirements, quality, and edge cases
7. **Completion & Documentation** -- summary, usage examples, and next steps

**Principles:** SOLID, DRY, KISS, YAGNI, Separation of Concerns, Defensive Programming, Security First.

**When to use:** Feature development, refactoring, complex bug fixes, multi-file changes.

---

### code-reviewer (Agent)

**Model:** Inherit

A senior code reviewer that validates completed work across five dimensions:

1. **Plan Alignment** -- implementation vs. original plan; justified vs. problematic deviations
2. **Code Quality** -- error handling, type safety, conventions, maintainability
3. **Architecture & Design** -- SOLID principles, separation of concerns, scalability
4. **Documentation & Standards** -- comments, file headers, project-specific conventions
5. **Issue Classification** -- Critical (must fix), Important (should fix), Suggestions (nice to have)

**When to use:** After completing a major implementation step or feature milestone.

---

### integration-test-validator (Agent)

**Model:** Sonnet | **Color:** Blue

A test engineer that validates implementations through a three-tier testing methodology:

| Tier | Focus |
|------|-------|
| **Unit** | Individual functions with valid inputs, edge cases, error handling, boundary conditions |
| **Integration** | Component interactions, data flow, API contracts, database operations, auth integration |
| **System** | End-to-end workflows, regression, concurrency, load scenarios, observability |

**Output format:** Structured report with total tests, pass/fail counts, severity-rated issues, regression check, and deployment recommendation.

**When to use:** After code review approval, before deployment.

---

### security-scanner (Agent)

**Model:** Inherit

A comprehensive security auditor that executes six scan phases:

| Phase | What It Checks |
|-------|---------------|
| **1. Secrets Detection** | API keys, tokens, passwords, private keys, connection strings, `.env` files |
| **2. Git Hygiene** | `.gitignore` coverage, tracked sensitive files, exposed `.git/` |
| **3. OWASP Patterns** | Prompt injection, SQL/command injection, XSS, insecure deserialization, broken access control |
| **4. Config Security** | YAML/JSON configs, env var handling, file permissions, bot intent declarations |
| **5. Guardrails Alignment** | Input/output sanitization, RBAC, rate limiting, hardened system prompts |
| **6. Dependency Audit** | Known CVEs, typosquatted packages, unnecessary dependencies |

**Output format:** Tabular report with severity levels (Critical/High/Medium/Low), guardrails status matrix, and push recommendation.

**When to use:** Before any `git push`, after major implementations, periodic security audits.

---

## Skill Reference

### code-implementation (Skill)

**Trigger:** `/code-implementation "task description"`

A full-stack implementation workflow with seven phases:

```
Phase 0: Architecture Context (if available)
Phase 1: Understand & Bound (requirements, affected files, frontend surface audit)
Phase 2: Plan (checklist-driven, with test cases identified upfront)
Phase 2.5: Approval Gate (for complex changes)
Phase 3: Implement (test-first TDD: red -> green -> refactor)
Phase 4: Verify (run all tests, check coverage >80%, frontend builds clean)
Phase 5: Code Review (invoke code-reviewer agent)
Phase 6: Summarize
Phase 7: Explain (on request)
```

**Key principle:** Every backend feature needs a frontend. Unless explicitly told otherwise, the skill assumes full-stack delivery including API layer, store, components, pages, and routing.

---

### gitpush

**Trigger:** `/gitpush` or "push my changes"

A safe push workflow with 7 blocking gates:

| Step | Gate | What Happens |
|------|------|-------------|
| 0 | Repo confirmation | Detects remote or lets you pick from `gh repo list` |
| 1 | Identity verification | Validates `git config` matches your stored GitHub identity |
| 2 | Branch selection | Choose current, main, or create new branch |
| 2.5 | Screen recording | Optional: record a demo and embed in README |
| 2.6 | README check | Create or update README before pushing |
| 3 | Sensitive file scan | Blocks `.env`, credentials, `.claude/`, plan files; auto-unstages `.gitignore`, `memory.md`, `CLAUDE.md`, `learnings.md` |
| 3.5 | Security scan | Launches the `security-scanner` agent; walks through each finding individually |
| 4 | Final confirmation | Shows repo, branch, files, commit message, and author for explicit approval |
| 5 | Execute | Commit and push only after "Yes, push it" |
| 6 | Deploy | Optional deploy to Vercel, Railway, GitHub Pages, Netlify, or Chrome Web Store |

**Safety rules:** Never force-push unless explicitly requested. Never push secrets. Always confirm repo and branch. Every security finding is presented individually with explain-why-it-matters descriptions.

---

### skill-creator

**Trigger:** `/skill-creator` or "create a skill for X"

A six-step process for building new skills:

1. **Understand** -- gather concrete usage examples through interview questions
2. **Plan** -- identify reusable scripts, references, and assets
3. **Initialize** -- run `scripts/init_skill.py` to scaffold the skill directory
4. **Edit** -- implement resources and write `SKILL.md` with proper frontmatter
5. **Package** -- validate and bundle into a distributable `.skill` file via `scripts/package_skill.py`
6. **Iterate** -- refine based on real usage

**Included scripts:**
- `scripts/init_skill.py` -- scaffolds a new skill directory with template files
- `scripts/package_skill.py` -- validates and packages a skill for distribution
- `scripts/quick_validate.py` -- fast validation of skill structure and frontmatter

---

### skill-creator-v2

**Trigger:** `/skill-creator-v2` or "create a skill" (advanced)

An enhanced skill creation system with two modes, selected via a mandatory prehook gate:

**Simple Mode:**
```
Prehook (3 questions) -> Focused Interview (1-2 rounds) -> Quick Research -> Build + Validate -> Package
```

**Advanced Mode (with benchmarking):**
```
Prehook -> Deep Interview (2-3 rounds) -> Research -> Build + Generate Evals
-> A/B Benchmark (parallel sub-agents: with-skill vs without-skill)
-> Grade (4 dimensions: correctness, completeness, quality, adherence)
-> HTML Comparison Viewer -> Iterate until satisfied -> Package
```

**Included assets:**
- `assets/comparison-template.html` -- side-by-side benchmark comparison viewer
- `references/eval-format.md` -- test case format specification
- `references/skill-design-patterns.md` -- established patterns for effective skills
- `references/subagent-prompts.md` -- prompt templates for A/B benchmark agents
- `scripts/generate_comparison.py` -- generates the HTML comparison report
- `scripts/open_viewer.py` -- opens the comparison in the browser

---

### skill-graph

**Trigger:** `/skill-graph "task description"` or "chain skills for X"

Orchestrates multiple skills into an ordered pipeline:

**Phase 1: Scan** -- discover all installed skills, filter by relevance (two-pass: frontmatter first, deep read for matches)

**Phase 2: Classify & Connect** -- assign each skill to a workflow phase and infer edges:

| Phase | Role | Examples |
|-------|------|---------|
| 0 | Explore | brainstorming, explain |
| 1 | Design | system-arch, debate, validation |
| 2 | Research | doc-search |
| 3 | Build | code-implementation, frontend-design |
| 4 | Verify | code-reviewer, integration-test-validator |
| 5 | Ship | gitpush, document-changes, linkedin-post |

Detects parallel branches, feedback loops (max 3 iterations before escalation), and circular dependencies.

**Phase 3: Render & Approve** -- generates a Mermaid diagram, summary table, and exclusion list; requires explicit approval before execution.

**Phase 4: Execute** -- runs skills in phase order with context passing, progress updates, and error handling.

---

### skill-guard

**Trigger:** `/skill-guard` or "should I install X" or "audit my skills"

Two operational modes:

**Gate Mode** (before installing a skill):
1. Build fingerprint index of all installed skills (~2 lines each)
2. Compare candidate against index using trigger/description overlap signals
3. Categorize: No Match -> install, Close Match -> spawn sub-agent for deep diff, Obvious Duplicate -> block
4. Present overlap report with Merge / Install Both / Skip options per candidate
5. Execute user decisions (merge deltas into existing skill, install alongside, or skip)

**Audit Mode** (on-demand scan):
1. Build fingerprint index
2. Pairwise comparison of all installed skills
3. Deep diff close matches via parallel sub-agents
4. Read-only report with overlap findings and recommendations

---

### capture-learnings

**Trigger:** `/capture-learnings` or "save learnings" or at end of session

A two-phase process:

**Phase 1:** Extract learnings from the current session and append to `learnings.md`:
- Bugs and root causes
- API/library gotchas
- Architectural patterns and decisions
- Useful commands and configs
- Failed approaches (warnings)

**Phase 2:** Cross-reference learnings against existing skills and propose targeted improvements (e.g., adding a gotcha to a skill's caveats section).

---

### find-skills

**Trigger:** "how do I do X", "find a skill for X", "is there a skill that can..."

Discovers and installs skills from the open ecosystem using the Skills CLI:

```bash
npx skills find [query]     # Search for skills
npx skills add <package>    # Install a skill
npx skills check            # Check for updates
npx skills update           # Update all skills
```

Browse the ecosystem at [skills.sh](https://skills.sh/).

---

### screen-recording

**Trigger:** "record this flow", "make a screen recording of X", "demo this feature"

Automates polished screen recordings with two auto-detected modes:

| Mode | Trigger | Pipeline |
|------|---------|----------|
| **Browser** | URL in prompt | Steel Dev (headless browser) -> Remotion |
| **Mac App** | App name in prompt | ffmpeg + AppleScript + cliclick -> Remotion |

Both modes produce a `moments.json` (timestamped action log) that feeds into Remotion for post-processing: dead-time trimming, clip merging/splitting, smooth zoom keyframes, and gradient backgrounds.

**Prerequisites:** Remotion, Steel Dev (browser mode), ffmpeg + cliclick (Mac app mode).

---

## Architecture

### Agents vs Skills

| | Agents | Skills |
|---|--------|--------|
| **What** | Autonomous sub-processes | Instruction sets loaded into context |
| **How they run** | Launched via `Agent` tool in isolated contexts | Invoked via `Skill` tool or `/command` |
| **Format** | Single `.md` file with YAML frontmatter | `SKILL.md` + optional `scripts/`, `references/`, `assets/` |
| **Context cost** | None until launched (runs in sub-process) | Metadata always in context (~100 words); body loaded on trigger |
| **Best for** | Heavy, isolated tasks (review, testing, scanning) | Workflows that guide the main agent (implementation, pushing, creating) |

### Directory Layout

```
~/.claude/                    # Global installation (all projects)
  skills/
    gitpush/
      SKILL.md
      examples.md
    code-implementation/
      SKILL.md
    skill-creator/
      SKILL.md
      scripts/
        init_skill.py
        package_skill.py
        quick_validate.py
    ...
  agents/
    code-implementation.md
    code-reviewer.md
    integration-test-validator.md
    security-scanner.md
```

Or install project-local at `./.claude/skills/` and `./.claude/agents/` for project-specific setups.

### Progressive Disclosure

Skills use a three-level loading system to manage context efficiently:

1. **Metadata** (~100 words) -- `name` + `description` from frontmatter; always in context
2. **SKILL.md body** (<5k words) -- loaded only when the skill triggers
3. **Bundled resources** (unlimited) -- scripts, references, and assets loaded as-needed by the agent

This ensures the context window isn't bloated with instructions for skills that aren't being used.

---

## Configuration

The `setup.sh` script handles initial configuration. It personalizes the `gitpush` skill with your GitHub identity by replacing `YOUR_GITHUB_USERNAME` and `YOUR_EMAIL` placeholders in `SKILL.md`.

**Supported install targets:**

| Option | Path | Scope |
|--------|------|-------|
| Claude Code (global) | `~/.claude/skills/` + `~/.claude/agents/` | All projects |
| Claude Code (project) | `./.claude/skills/` + `./.claude/agents/` | Current project only |
| Codex | `~/.agents/skills/` + `~/.agents/agents/` | All Codex projects |
| Custom | Your choice | Your choice |

---

## Creating Your Own Skills

Use the built-in `skill-creator` or `skill-creator-v2` to build new skills:

```bash
# Quick creation
/skill-creator "my-new-skill"

# Benchmark-driven creation with A/B testing
/skill-creator-v2
```

Or scaffold manually:

```bash
# Initialize a skill directory
python3 ~/.claude/skills/skill-creator/scripts/init_skill.py my-skill --path ./.claude/skills/

# Validate
python3 ~/.claude/skills/skill-creator/scripts/quick_validate.py ./.claude/skills/my-skill/

# Package for distribution
python3 ~/.claude/skills/skill-creator/scripts/package_skill.py ./.claude/skills/my-skill/
```

Every skill needs at minimum a `SKILL.md` with YAML frontmatter (`name` and `description`) and markdown instructions. See `skills/skill-creator/SKILL.md` for the full creation guide.

---

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b my-skill`)
3. Add your skill under `skills/` or agent under `agents/`
4. Validate your skill: `python3 skills/skill-creator/scripts/quick_validate.py skills/your-skill/`
5. Open a pull request

**Guidelines:**
- Skills should be focused and modular -- one skill, one job
- Keep `SKILL.md` under 500 lines; split detailed content into `references/`
- Include at least one concrete example showing: user prompt -> skill behavior -> expected output
- Write comprehensive `description` fields in frontmatter (this is how agents decide when to use your skill)

---

## License

See individual skill files for license information.
