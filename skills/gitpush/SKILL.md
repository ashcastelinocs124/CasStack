---
name: gitpush
description: Safely push code to GitHub while preventing sensitive files. Use when the user asks to push, publish, or sync code to GitHub, or mentions git push/branching.
---

# gitpush

## Purpose
Push code to GitHub following basic industry practices, with explicit repo/branch confirmation and strict sensitive-file exclusions.

## Required Safety Rules
- Never push `.env`, `.claude/**`, credentials, or secrets (e.g., keys, tokens, config with secrets).
- Always review `git status` and `git diff` before pushing.
- **Always ask the user which repo and branch to push to — never assume.**
- Always show a final confirmation summary and get explicit approval before committing or pushing.
- Never force-push unless explicitly requested.
- If this is the first push (no remote history), ensure a `README.md` exists before pushing.
- **Always verify commits are attributed to the correct account.** Run `git config user.name` and `git config user.email` and confirm both match:
  - `user.name` = `ashcastelinocs124`
  - `user.email` = `ashleyn4@illinois.edu`
  - If either is wrong, run `git config user.name "ashcastelinocs124"` and `git config user.email "ashleyn4@illinois.edu"` to fix before committing.

## Workflow

### Step 1 — Gather info
Run `git status`, `git diff`, `git remote -v`, and `git branch` to understand current state.

Also run `git config user.name` and `git config user.email`. If they don't match `ashcastelinocs124` / `ashleyn4@illinois.edu`, fix them now:
```bash
git config user.name "ashcastelinocs124"
git config user.email "ashleyn4@illinois.edu"
```

### Step 2 — Ask the 3 confirmation questions (BLOCKING — do not skip)
Present these questions to the user and wait for answers before proceeding:

1. **Repo:** "Which GitHub repo should I push to? (detected remotes: `<list remotes>`)"
2. **Branch:** "Which branch should I push to? (current: `<branch>`) — main/master or another branch?"
3. If pushing to main/master, explicitly flag: "This will push directly to the default branch — confirm?"

### Step 3 — Scan for sensitive files
- `.env`, `.env.*`
- `.claude/**`
- `credentials.json`, `secrets.*`, `*.pem`, `*.key`
- Any file containing obvious secrets

If sensitive files are staged or modified, **stop and ask** the user what to do.

### Step 4 — Show final confirmation summary + AskUserQuestion gate (BLOCKING — do not skip)

Display the summary to the user:

```
Ready to push:
  Repo:    <remote URL>
  Branch:  <branch name>
  Files:   <list of staged files>
  Commit:  "<proposed commit message>"
  Author:  ashcastelinocs124 <ashleyn4@illinois.edu>  ✓
```

Then **immediately use the `AskUserQuestion` tool** with this exact question:

```
question: "Are you sure you want to push to <branch> on <repo>?"
header: "Confirm push"
options:
  - label: "Yes, push it"
    description: "Proceed with git push"
  - label: "No, cancel"
    description: "Abort — do not push anything"
```

**Do NOT run any git commit or git push command until the user selects "Yes, push it".
If they select "No, cancel" or "Other", abort immediately and tell the user nothing was pushed.**

### Step 5 — Execute
1. If first push, verify `README.md` exists; create one only if the user asks.
2. Ensure branch is up to date (pull/rebase if needed) unless user says otherwise.
3. Commit and push to the confirmed repo and branch.

## Example Prompt
User: "push my changes"
Assistant:
1. Run status/diff/remote/branch checks.
2. Ask: "Which repo should I push to? Detected: origin → https://github.com/user/repo"
3. Ask: "Which branch? Currently on `feature/auth`. Push here or to main?"
4. Scan for sensitive files.
5. Show full confirmation summary and wait for explicit yes.
6. Commit and push only after confirmation.

