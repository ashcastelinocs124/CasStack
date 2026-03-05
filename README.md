# public-skills

Skills and agents I use for my Claude Code coding workflows. Feel free to use them in your own setup.

## Skills

| Skill | What it does |
|-------|-------------|
| `skills/code-implementation/` | Plan → approve → implement → review cycle for writing features |
| `skills/gitpush/` | Safe GitHub push with sensitive-file scanning and confirmation gate |
| `skills/capture-learnings/` | Extract and save session learnings to `learnings.md`, then improve skills |
| `skills/skill-creator/` | Guide + scripts for creating new Claude Code skills |

## Agents

Sub-agents automatically dispatched by the skills above:

| Agent | What it does |
|-------|-------------|
| `agents/code-implementation.md` | Heavy implementation work — plans, checklists, and execution |
| `agents/code-reviewer.md` | Validates completed implementation against plan and coding standards |
| `agents/integration-test-validator.md` | Runs full test suite after code review passes |

## Usage

Place skills under `.claude/skills/<skill-name>/SKILL.md` and agents under `.claude/agents/<name>.md` in your project (or `~/.claude/` for global use).

Invoke skills with the `Skill` tool in Claude Code, e.g. `/code-implementation` or `/gitpush`.
