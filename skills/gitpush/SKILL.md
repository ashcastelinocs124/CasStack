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
- **Always verify commits are attributed to the correct account.** Run `git config user.name` and `git config user.email` and confirm both match the user's GitHub identity. If either is wrong, ask the user what name and email to use, then fix:
  ```bash
  git config user.name "<their-github-username>"
  git config user.email "<their-email>"
  ```

## Workflow

### Step 1 — Gather info + Identity check (BLOCKING — use AskUserQuestion)

Run `git status`, `git diff`, `git remote -v`, and `git branch` to understand current state.

Also run `git config user.name` and `git config user.email`. Then immediately use `AskUserQuestion`:

```
question: "Git identity is set to: <user.name> <<user.email>>. Is this the correct GitHub account to commit as?"
header: "Git identity"
options:
  - label: "Yes, that's correct"
    description: "Proceed with this identity"
  - label: "No, change it"
    description: "I'll provide the correct name and email"
```

- If user selects "No, change it": ask for the correct name and email, then run:
  ```bash
  git config user.name "<their-name>"
  git config user.email "<their-email>"
  ```

---

### Step 1.5 — Repo selection when no remote is set (BLOCKING — use AskUserQuestion)

**Trigger:** `git remote -v` returns empty output OR the user did not provide a repo URL.

Run:
```bash
gh repo list <detected-github-username> --limit 5 --json name,url,updatedAt --sort updated
```

This returns the 5 most recently updated repos. Build an `AskUserQuestion` from the results:

```
question: "No remote is set. Which GitHub repo should this be pushed to?"
header: "Target repo"
options:
  - label: "<repo-name-1>"
    description: "Last updated: <updatedAt> — github.com/<user>/<repo-name-1>"
  - label: "<repo-name-2>"
    description: "Last updated: <updatedAt> — ..."
  - label: "Paste a link"
    description: "I'll provide the full repo URL myself"
```

- If user selects a repo from the list: set remote with `git remote add origin <url>` then continue.
- If user selects "Paste a link" or types "Other": ask for the full URL, then `git remote add origin <url>`.
- If `gh` is not authenticated or fails: skip to the "Paste a link" fallback directly.

**Do not assume or guess a repo. Always ask.**

---

### Step 2 — Branch selection (BLOCKING — use AskUserQuestion)

Use the `AskUserQuestion` tool to ask which branch to push to. Build the options dynamically from `git branch -a` output:

```
question: "Which branch do you want to push to?"
header: "Target branch"
options:
  - label: "<current branch>"         ← always first
    description: "Push to current branch (currently checked out)"
  - label: "main"                     ← if exists and different from current
    description: "Push to main branch"
  - label: "New branch"
    description: "Create and push to a new branch — I'll ask for the name"
```

- If user selects "New branch", ask for the name with a follow-up `AskUserQuestion` or text prompt.
- If pushing to main/master, note: "This pushes directly to the default branch."

### Step 2.5 — README check (BLOCKING — use AskUserQuestion)

Check if a `README.md` exists in the repo root. Then use `AskUserQuestion`:

```
question: "Does the README need to be updated before pushing?"
header: "README update"
options:
  - label: "No, README is fine"
    description: "Proceed without touching the README"
  - label: "Yes, update it"
    description: "I'll describe what changed and you update the README before pushing"
  - label: "No README exists — create one"    ← only show if README is missing
    description: "Generate a basic README before pushing"
```

- If user selects "Yes, update it": ask them what to add/change, make the edits, then continue.
- If user selects "create one": generate a minimal README based on the repo contents, show it for approval, then continue.

### Step 3 — Scan for sensitive files
- `.env`, `.env.*`
- `.claude/**`
- `credentials.json`, `secrets.*`, `*.pem`, `*.key`
- Any file containing obvious secrets

If sensitive files are staged or modified, **stop and ask** the user what to do.

**Also audit `.gitignore` coverage before staging:**
- `.env` in `.gitignore` does NOT match `.env.local` or `.env.*` — check that all dotenv variants are covered
- If `.gitignore` is missing `.env.*` or `.env.local`, offer to add them before proceeding with `git add`

### Step 4 — Show final confirmation summary + AskUserQuestion gate (BLOCKING — do not skip)

Display the summary to the user:

```
Ready to push:
  Repo:    <remote URL>
  Branch:  <branch name>
  Files:   <list of staged files>
  Commit:  "<proposed commit message>"
  Author:  <git config user.name> <<git config user.email>>  ✓
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
1. Run status/diff/remote/branch checks + confirm git identity with user.
2. **If no remote set:** run `gh repo list` → AskUserQuestion with last 5 repos + "Paste a link" option → set remote.
3. AskUserQuestion → "Which branch?" (options: current branch / main / new branch)
4. AskUserQuestion → "Does the README need updating?" (yes / no / create)
5. Scan for sensitive files — stop if any found.
6. Show confirmation summary (repo, branch, files, commit message, author).
7. AskUserQuestion → "Are you sure you want to push?" (Yes, push it / No, cancel)
8. Commit and push only after explicit "Yes, push it".
