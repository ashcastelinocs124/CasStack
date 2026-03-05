---
name: capture-learnings
description: Review the current coding session and extract important learnings — bugs fixed, gotchas, architectural decisions, patterns adopted, useful commands, and config discoveries — then append them to the project's learnings.md under a dated section. Also cross-references captured learnings against existing skills to propose targeted improvements. Use when the user says "capture learnings", "save learnings", "log what we learned", "add to learnings.md", or at the end of a coding session to preserve knowledge and grow skills.
---

# Capture Learnings

Two-phase process: (1) save learnings from this session, (2) use them to improve existing skills.

## What to Capture

Extract only information that would save time if rediscovered:

- **Bug** — root cause of a bug and how it was fixed (not just "it was broken")
- **Gotcha** — non-obvious behaviors, API quirks, version-specific issues
- **Pattern** — architectural or coding patterns adopted with brief reasoning
- **Command** — exact commands, flags, or scripts that were useful
- **Config** — env var names, file paths, settings that were non-obvious to find
- **Decision** — architectural trade-off made and why
- **Warning** — approaches that failed and should not be re-tried

Skip: session-specific context (e.g. "we were building X"), obvious things, incomplete work.

## Output Format

```markdown
### YYYY-MM-DD — [topic, e.g. "AutoCart / Frontend"]

- **[Category]**: [Concise learning with enough specificity to be actionable]
```

Example entries:
```markdown
### 2026-03-04 — AutoCart / web3.py

- **Gotcha**: `web3.py` SignedTransaction uses `rawTransaction` (camelCase), not `raw_transaction`
- **Config**: Gas limit for `approve`/`dispute` on AgentMarketplace must be 300000, not 100000
- **Bug**: `get_logs()` takes `fromBlock` (camelCase), not `from_block`
```

---

## Phase 1: Capture Learnings

Write to the **project's `learnings.md`** only:

- Look for `learnings.md` in the current working directory (project root)
- If it exists, read it and avoid duplicating entries already there
- Append the new dated section
- If it doesn't exist, create it with a `# Learnings` header and brief description:
  ```markdown
  # Learnings

  Project-specific concepts, technical gotchas, and bug fixes worth remembering.
  ```

After writing, tell the user what was captured (brief list).

---

## Phase 2: Improve Existing Skills

After capturing learnings, cross-reference them against existing skills to find improvement opportunities.

### Where to find skills

Read SKILL.md files from:
- `~/.claude/skills/` — global skills (available across all projects)
- `.claude/skills/` in the current project — project-specific skills

### What constitutes a good improvement

A learning warrants a skill update if it would make the skill more effective for future use:

- A **Gotcha/Bug/Warning** that belongs in the skill's caveats or known-issues
- A **Command/Config** the skill should mention but currently doesn't
- A **Pattern/Decision** that refines or corrects a skill's workflow guidance
- A missing example that would make a skill's instructions clearer

Do NOT propose improvements that are:
- Already covered in the skill
- Too project-specific to be generally useful
- Minor wording tweaks with no practical impact

### Proposal format

Present a structured proposal before making any edits:

```
## Proposed Skill Improvements

### 1. [skill-name] — [one-line reason]
File: ~/.claude/skills/skill-name/SKILL.md
Change: Add to [section name]:
  - **Gotcha**: [exact text to add]

### 2. [skill-name] — [one-line reason]
...
```

Ask: "Apply these improvements? (yes / skip N / no)"

### Applying approved improvements

Edit only the approved SKILL.md files. Place additions in the most semantically relevant existing section — prefer "Gotchas", "Caveats", "Known Issues", or "Tips" sections. If none exist, add a `## Gotchas` section near the end of the file.
