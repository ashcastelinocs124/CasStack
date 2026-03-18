# gitpush — Examples

---

## Example 1 — Pushing skill files to a separate empty repo

**Scenario:** User asks to push specific files from the current project into a different GitHub repo (`your-username/public-skills`) that has never been pushed to before.

### Step 1 — Gather info

```bash
gh repo view your-username/public-skills
# → repo exists

gh api repos/your-username/public-skills/git/refs
# → {"message":"Git Repository is empty.","status":"409"}
# → Repo exists but has no commits — needs initialization
```

**Decision:** Target is a different repo from the working directory. Clone it to `/tmp`, copy files in, push from there.

```bash
cd /tmp && git clone https://github.com/your-username/public-skills.git
# → "warning: You appear to have cloned an empty repository." — expected
```

### Step 2 — Branch selection (AskUserQuestion)

Repo is empty — only option is `main`. Selected automatically, user confirmed.

### Step 2.5 — README check (AskUserQuestion)

No README exists (empty repo). Options shown:
- "No README exists — create one" ← selected

Generated `README.md` with a table of all skills and agents being pushed. Shown to user for approval before continuing.

### Step 3 — Scan for sensitive files

```bash
grep -r "sk-\|OPENAI\|PRIVATE_KEY\|SECRET\|PASSWORD\|TOKEN" skills/ agents/
```

**Result:** Two matches flagged — both false positives:
```
skills/skill-creator/scripts/init_skill.py:**2. Task-Based**
skills/skill-creator/scripts/init_skill.py:...task-based patterns...
```

The word "task-based" partially matched `TOKEN`. **Verified by reading context** — not secrets. Proceeded.

> **Gotcha:** The grep pattern `TOKEN` matches words like "task-based" — always read the matched line before blocking. Check for actual key patterns (`sk-proj-`, `0x...`, `-----BEGIN`) not just keyword fragments.

### Step 4 — Set git identity + confirmation

```bash
cd /tmp/public-skills
git config user.name "your-username"
git config user.email "your-email@example.com"
```

Confirmation summary shown:
```
Ready to push:
  Repo:    https://github.com/your-username/public-skills
  Branch:  main (first push — initializing repo)
  Files:   README.md
           agents/code-implementation.md
           agents/code-reviewer.md
           agents/integration-test-validator.md
           skills/capture-learnings/SKILL.md
           skills/code-implementation/SKILL.md
           skills/gitpush/SKILL.md
           skills/skill-creator/SKILL.md + scripts/
  Commit:  "feat: add code-implementation, gitpush, capture-learnings, skill-creator skills + agents"
  Author:  your-username <your-email@example.com>  ✓
```

AskUserQuestion → User selected **"Yes, push it"**.

### Step 5 — Execute

```bash
cd /tmp/public-skills
git add .
git commit -m "feat: add code-implementation, gitpush, capture-learnings, skill-creator skills + agents

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

git push -u origin main
# → 11 files changed, 1597 insertions(+)
# → branch 'main' set up to track 'origin/main'
```

### Learnings from this push

| Learning | Detail |
|----------|--------|
| **Different repo → clone to /tmp** | When pushing files to a repo other than the current working directory, clone it to `/tmp`, copy files in, then push from there |
| **Check if empty before cloning** | Run `gh api repos/owner/repo/git/refs` — HTTP 409 = empty repo, needs `git push -u origin main` not just `git push` |
| **Secret scan false positives** | Grep for actual key prefixes (`sk-proj-`, `0x`, `-----BEGIN`) not fragments — "task-based" matches TOKEN naively |
| **First push to empty repo** | Always use `git push -u origin main` (not just `git push`) to set upstream tracking |
| **README required for first push** | Empty repos need a README before pushing — generate from repo contents if none exists |
