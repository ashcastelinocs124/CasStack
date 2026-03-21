---
name: skill-guard
description: Intercepts skill installations to detect overlap with existing skills, analyzes deltas, and offers merge/install/skip options. Use before installing any skill (npx skills add, find-skills suggesting installs, "should I install X"). Also use for on-demand audits when the user says "audit my skills", "check for redundant skills", "skill overlap", or "do I have duplicate skills".
---

# Skill Guard

**Usage:** /skill-guard (auto-detects mode based on context)

**Trigger this skill when:**
- User types `npx skills add ...` or any skill install command
- `find-skills` suggests installing a skill
- User asks "should I install X" or "do I already have something like X"
- User says "audit my skills", "check for redundant skills", "skill overlap"
- User says "do I have duplicate skills", "clean up my skills"

**Skip for:** Uninstalling skills, creating new skills (use skill-creator), chaining skills (use skill-graph)

**Auto-detect mode:**
1. If the user's message contains `npx skills add`, `npx skills install`, or is about to install a specific skill → **Gate Mode** (Steps 1-5). Extract the package name(s) from the command as candidates.
2. Otherwise → **Audit Mode** (scan all installed skills for overlap)

**Two modes:**
- **Gate Mode** — prehook before any skill install. Intercepts the `npx` command, evaluates candidates BEFORE executing it.
- **Audit Mode** — on-demand scan of all installed skills (separate section at end)

---

## Step 1: Build Fingerprint Index

Scan all installed skills and build a compact index. This avoids reading 30+ full SKILL.md files for every comparison.

### 1.1: Discover all installed skills

Use Glob to find all skill files:

```
Glob: ~/.claude/skills/*/SKILL.md
```

Also check for project-specific skills if inside a project:

```
Glob: .claude/skills/*/SKILL.md
```

### 1.2: Extract fingerprints

For each discovered SKILL.md, read the first 20 lines (frontmatter + trigger section) using `Read` with `limit: 20`.

Extract these fields:
- **name** — from YAML frontmatter `name:` field
- **description** — from YAML frontmatter `description:` field
- **triggers** — parse "Trigger this skill when:" bullet list from the body (typically the first bulleted list after the header)
- **key capabilities** — infer from the description: what does this skill DO (1-2 phrases)

### 1.3: Compress into index

Produce a fingerprint index with ~2 lines per skill. Format:

```
code-reviewer: Reviews code against plans and standards.
  Triggers: "review this code", "check my implementation", after major implementation steps.

bug-fix: Fixes bugs with root cause analysis and TDD.
  Triggers: error messages, stack traces, test failures, "fix this", "debug this".

code-implementation: Implements features with planning, approval gates, and TDD.
  Triggers: "implement", "build", "add feature", function/module/service requests.

skill-graph: Chains multiple skills into an ordered pipeline for complex tasks.
  Triggers: "skill graph", "chain skills", multi-step tasks.
```

Keep this index in working memory for the remaining steps.

---

## Step 1.5: Extract Candidates (Gate Mode only)

If triggered by a `npx skills add` command:
1. Parse the package name(s) from the command (e.g., `npx skills add owner/repo@skill-name` → candidate is `owner/repo@skill-name`)
2. **Do NOT execute the `npx` command yet** — evaluate first
3. For each candidate, run `npx skills find <skill-name>` or fetch the SKILL.md from the package source to read its contents
4. If the candidate is a URL or GitHub path, use WebFetch to retrieve the SKILL.md content

If triggered by find-skills suggesting an install or "should I install X":
1. Identify the candidate from context (the skill being suggested or asked about)
2. Fetch/read the candidate's SKILL.md

Proceed to Step 2 with the candidate SKILL.md content(s) in hand.

---

## Step 2: Gate Mode -- Broad Match

Read the candidate skill's SKILL.md (the skill about to be installed). Extract the same fingerprint fields: name, description, triggers, key capabilities.

### 2.1: Compare candidate against index

For each installed skill in the fingerprint index, evaluate overlap with the candidate:

| Signal | Weight |
|--------|--------|
| Shares 2+ trigger phrases (exact or semantically equivalent) | Strong |
| Description covers the same domain or workflow | Strong |
| Shares 1 trigger phrase | Weak |
| Same tools/commands mentioned in description | Weak |

### 2.2: Categorize each comparison

Classify the relationship between the candidate and each installed skill:

| Category | Criteria | Action |
|----------|----------|--------|
| **No match** | 0-1 weak signals, no strong signals | Install directly (no subagent) |
| **Close match** | 1+ strong signal OR 3+ weak signals | Deep diff needed (spawn subagent) |
| **Obvious duplicate** | 2+ strong signals AND description is near-paraphrase of existing | Block (no subagent) |

### 2.3: Decide next steps

Based on categorization:

- If ALL installed skills are **no match** -> skip to Step 4 (report as clean install)
- If any are **close match** -> proceed to Step 3 (deep diff)
- If any are **obvious duplicate** -> include in Step 4 report as blocked

---

## Step 3: Deep Diff (Subagents)

For each "close match" pair, spawn a subagent to perform a detailed comparison. Subagents run in **parallel** when multiple close matches exist.

### 3.1: Spawn subagents

For each close match, use the Agent tool with this exact prompt template. Replace the placeholders with actual content.

```
Agent tool:
  description: "Deep diff: [candidate-name] vs [existing-name]"
  prompt: |
    You are comparing two skills to determine overlap and unique value.

    ## Candidate Skill (about to be installed)

    **Name:** [candidate-name]
    **Full SKILL.md contents:**
    ```
    [paste the ENTIRE candidate SKILL.md here — frontmatter + body]
    ```

    ## Existing Skill (already installed)

    **Name:** [existing-name]
    **Full SKILL.md contents:**
    ```
    [paste the ENTIRE existing SKILL.md here — frontmatter + body]
    ```

    ## Your Task

    Compare these two skills and return a structured analysis:

    ### 1. New Additions (what the candidate brings that the existing skill lacks)
    - New trigger phrases not covered by existing
    - New workflow steps or phases
    - New tool integrations or commands
    - New patterns, edge cases, or domain knowledge
    - New subagent strategies or delegation patterns

    ### 2. Redundant Content (already covered by existing skill)
    - Trigger phrases that overlap
    - Workflow steps that duplicate existing phases
    - Tools or patterns already present

    ### 3. Conflicts (candidate says X, existing says Y)
    - Contradictory instructions or approaches
    - Incompatible workflow orders
    - Different tool preferences for the same task

    ### 4. Verdict
    State one of:
    - **MERGE RECOMMENDED** — candidate has meaningful additions worth absorbing into existing
    - **INSTALL BOTH** — skills are complementary, not redundant (different enough to coexist)
    - **SKIP** — candidate is fully covered by existing, no new value

    ### 5. If MERGE RECOMMENDED: Delta Summary
    List the SPECIFIC items to merge into the existing skill:
    - Trigger phrases to add: [list]
    - Workflow steps to add: [list with where they fit]
    - Patterns/tools to add: [list]

    Be precise. Reference specific sections and line-level content.
```

### 3.2: Collect results

Wait for all subagents to complete. Each returns:
- New additions list
- Redundant content list
- Conflicts list
- Verdict (MERGE / INSTALL BOTH / SKIP)
- Delta summary (if MERGE)

---

## Step 4: Present Report (Prehook)

Compile all results into a single report for the user. Nothing is installed, merged, or skipped until the user responds.

### 4.1: Format the report

For each candidate being evaluated, show one of these based on categorization:

**No overlap (from Step 2 -- no match):**
```
[checkmark] skill-name: no overlap with installed skills -- will install
```

**Overlap with delta (from Step 3 -- close match with subagent results):**
```
[overlap icon] skill-name: overlaps with "existing-skill-name"
  - existing-skill-name already has: [brief list of shared capabilities]
  - skill-name adds: [brief list of NEW capabilities from subagent delta]
  - Conflicts: [list, or "none"]
```

**Fully redundant (from Step 2 -- obvious duplicate, OR Step 3 verdict = SKIP):**
```
[block icon] skill-name: fully covered by "existing-skill-name"
  - Everything in skill-name is already in existing-skill-name
```

### 4.2: Prompt user for decisions

For each candidate with overlap (overlap icon), use AskUserQuestion:

```
question: "[candidate-name] overlaps with [existing-name]. [existing-name] already covers [X, Y]. [candidate-name] adds [A, B]. How should I handle this?"
header: "Skill Overlap: [candidate-name]"
options:
  - label: "Merge into existing"
    description: "Add the new triggers, steps, and patterns from [candidate-name] into [existing-name]. Do not install [candidate-name]."
  - label: "Install both"
    description: "Install [candidate-name] alongside [existing-name]. Keep both skills."
  - label: "Skip"
    description: "Do not install [candidate-name]. No changes to [existing-name]."
```

For each fully redundant candidate (block icon), use AskUserQuestion:

```
question: "[candidate-name] appears fully covered by [existing-name]. Install anyway?"
header: "Redundant Skill: [candidate-name]"
options:
  - label: "Install anyway"
    description: "Install [candidate-name] even though [existing-name] covers the same ground."
  - label: "Skip"
    description: "Do not install [candidate-name]."
```

### 4.3: HARD GATE

**Do NOT execute any action until ALL user responses are collected.** If there are 3 overlapping candidates, wait for all 3 responses before proceeding to Step 5.

---

## Step 5: Execute Actions

Process each candidate based on the user's decisions.

### 5.1: Install action

For candidates approved for install (no-overlap, "Install both", or "Install anyway"):
- Proceed with the standard install mechanism (`npx skills add` or whatever triggered this skill)
- No modifications to existing skills

### 5.2: Merge action

For candidates where the user chose "Merge into existing":

1. **Read the existing skill's full SKILL.md** using the Read tool
2. **Read the candidate's full SKILL.md** using the Read tool
3. **Identify the delta** from the subagent's analysis (Step 3 results):
   - New trigger phrases to add
   - New workflow steps or phases to insert
   - New patterns, tools, or edge cases to append
4. **Edit the existing SKILL.md** using the Edit tool:
   - Add new trigger phrases to the "Trigger this skill when:" list
   - Insert new workflow steps in the appropriate phase/section
   - Append new patterns or edge cases to relevant sections
   - Do NOT change the existing skill's name, description metadata, or core structure
   - Do NOT duplicate content already present
5. **Show the diff** — after editing, run `git diff` on the modified file and show the user what changed
6. **Do NOT install the candidate** — its value has been absorbed into the existing skill

### 5.3: Skip action

For candidates where the user chose "Skip":
- Do nothing. No install, no modifications.

### 5.4: Conflict resolution

If the subagent identified conflicts (candidate says X, existing says Y):
- Present each conflict individually using AskUserQuestion:

```
question: "Conflict detected between [candidate] and [existing]: [describe the conflict]. Which approach should I keep?"
header: "Conflict: [brief topic]"
options:
  - label: "Keep existing"
    description: "[existing-name] says: [X]"
  - label: "Use candidate's approach"
    description: "[candidate-name] says: [Y]"
  - label: "Keep both (I'll reconcile later)"
    description: "Add both approaches with a note"
```

---

## Audit Mode

Triggered by: "audit my skills", "check for redundant skills", "do I have duplicate skills"

Audit mode is **read-only** — it reports and recommends but makes no changes.

### Audit Step 1: Build fingerprint index

Same as Gate Mode Step 1. Scan all `~/.claude/skills/*/SKILL.md` files and build the compact index.

### Audit Step 2: Pairwise comparison

Compare every unique pair of installed skills using the fingerprint index.

For N skills, there are N*(N-1)/2 pairs. Use the same broad match criteria from Gate Mode Step 2:
- **No match** — skip this pair
- **Close match** — needs deep diff (spawn subagent)
- **Obvious duplicate** — flag immediately

### Audit Step 3: Deep diff close matches

For each close-match pair, spawn a subagent using the same prompt template from Gate Mode Step 3. The only difference: both skills are "existing" (neither is a candidate).

Adjust the subagent prompt header:

```
## Skill A (installed)
[full SKILL.md]

## Skill B (installed)
[full SKILL.md]
```

The subagent returns the same structured analysis: overlaps, unique contributions, conflicts, verdict.

Subagents run in **parallel**.

### Audit Step 4: Present audit report

Format the results as a read-only report:

```
## Skill Audit Report

**Total skills scanned:** [N]
**Overlapping pairs found:** [M]
**Fully redundant skills:** [K]

### Overlapping Pairs

[warning icon] "code-architect" and "code-implementation" overlap heavily
  - code-architect covers: planning, architecture, design decisions
  - code-implementation covers: planning + architecture + implementation + TDD
  - code-architect may be a subset -- consider merging its unique content into code-implementation and removing it

[warning icon] "skill-creator" and "skill-creator-v2"
  - skill-creator-v2 appears to supersede skill-creator
  - Recommendation: remove skill-creator if v2 covers all its use cases

### Clean Skills

[checkmark] [X] other skills have no significant overlap
```

### Audit Step 5: Offer actions (optional)

After presenting the report, ask:

```
question: "Want me to act on any of these findings?"
header: "Audit Actions"
options:
  - label: "Merge a pair"
    description: "I'll tell you which pair to merge"
  - label: "Remove a redundant skill"
    description: "I'll tell you which to remove"
  - label: "No action needed"
    description: "This was informational only"
```

If the user requests a merge, follow the same merge process from Gate Mode Step 5.2.

---

## Example

**User says:** "I found a cool `code-review-plus` skill, should I install it?"

**Skill behavior:**
1. Build fingerprint index of all 30+ installed skills (~2 lines each)
2. Read `code-review-plus` SKILL.md, extract: triggers are "review code", "check implementation", "PR review"; description covers code quality, plan alignment, issue classification
3. Broad match finds `code-reviewer` shares 2+ triggers and same domain -> **close match**
4. Spawn subagent: deep diff `code-review-plus` vs `code-reviewer`
5. Subagent returns: code-review-plus adds PR comment integration and auto-fix suggestions; 80% of content is redundant with code-reviewer
6. Present report: "[overlap icon] code-review-plus overlaps with code-reviewer. Adds: PR comments, auto-fix. Already covered: plan alignment, issue classification, quality checks."
7. Ask user: Merge into existing / Install both / Skip
8. If user picks "Merge" -> edit `code-reviewer/SKILL.md` to add PR comment and auto-fix sections, show diff, skip installing code-review-plus

**User says:** "audit my skills"

**Skill behavior:**
1. Build fingerprint index of all installed skills
2. Compare all pairs, find 2 overlapping pairs out of 30 skills
3. Spawn 2 subagents in parallel for deep diffs
4. Present read-only report with findings and recommendations
5. Ask if user wants to act on any findings

---

## Quality Guidelines

**ALWAYS:**
- Build the fingerprint index before any comparison (do not read all full files upfront)
- Use subagents only for close matches (not for obvious duplicates or clear no-matches)
- Run subagents in parallel when multiple close matches exist
- Present the full report and collect ALL user decisions before executing any action
- Show a diff after any merge operation
- Keep the existing skill's name and core structure intact during merges

**NEVER:**
- Install a skill without checking for overlap first (that is the whole point of this skill)
- Merge without user approval
- Modify an existing skill's name or description metadata during a merge
- Skip the user prompt for overlapping or redundant candidates
- Execute actions before all user responses are collected
- Read all full SKILL.md files upfront — use the fingerprint index for broad matching first
