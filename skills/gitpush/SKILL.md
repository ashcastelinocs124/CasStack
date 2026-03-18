---
name: gitpush
description: Safely push code to GitHub while preventing sensitive files. Use when the user asks to push, publish, or sync code to GitHub, or mentions git push/branching.
---

# gitpush

## Purpose
Push code to GitHub following basic industry practices, with explicit repo/branch confirmation and strict sensitive-file exclusions.

## Required Safety Rules
- Never push `.env`, `.claude/**`, credentials, or secrets (e.g., keys, tokens, config with secrets).
- Never push `.gitignore` — unstage it silently if it's staged.
- Never push `memory.md` — unstage it silently if it's staged.
- Never push `CLAUDE.md` — unstage it silently if it's staged.
- Never push `learnings.md` — unstage it silently if it's staged.
- Never push plans or specs files (e.g., `PLAN.md`, `SPEC.md`, `*-plan.md`, `*-spec.md`, `plans/`, `specs/`) — unstage them silently if staged. These are internal working documents for the user, not for the repo.
- Always review `git status` and `git diff` before pushing.
- **Always ask the user which repo and branch to push to — never assume.**
- Always show a final confirmation summary and get explicit approval before committing or pushing.
- Never force-push unless explicitly requested.
- If this is the first push (no remote history), ensure a `README.md` exists before pushing.
- **"Chat about this" = full stop.** Every hook includes a "Chat about this" option. If selected, stop the workflow completely, read what the user says, and respond. Do NOT continue pushing. Resume only when they explicitly say to.
- **Always verify commits are attributed to the correct account.** Run `git config user.name` and `git config user.email` and confirm both match the values in the **Stored GitHub Identity** section below. If either is wrong, fix them with `git config user.name` and `git config user.email` before committing.

## Stored GitHub Identity
- **Username:** `<your-username>`
- **Email:** `<your-email>`
- Always verify and fix git config to match before committing (see Step 1).

---

## Workflow

### Step 0 — Confirm target repo (BLOCKING — use AskUserQuestion)

Run `git remote -v` first. Then ask:

**If a remote is already set:**
```
question: "Push to <current remote URL>?"
header: "Target repo"
options:
  - label: "Yes — push here"
    description: "<current remote URL>"
  - label: "No — different repo"
    description: "I'll pick a different repo"
  - label: "Chat about this"
    description: "Stop — I want to talk about this first"
```
- If "Yes": proceed with current remote.
- If "No": run `gh repo list --limit 5 --json name,url,updatedAt --sort updated`, show results as options + "Paste a link", set new remote with `git remote set-url origin <url>`.
- If "Chat about this": stop completely and listen.

**If no remote is set:** skip to Step 1.5 (repo selection).

### Step 1 — Gather info
Run `git status`, `git diff`, `git remote -v`, and `git branch` to understand current state.

Also run `git config user.name` and `git config user.email`. If they don't match the **Stored GitHub Identity** values, fix them now:
```bash
git config user.name "<your-username>"
git config user.email "<your-email>"
```

### Step 1.5 — Repo selection when no remote is set (BLOCKING — use AskUserQuestion)

**Trigger:** `git remote -v` returns empty output OR the user did not provide a repo URL.

Run:
```bash
gh repo list --limit 5 --json name,url,updatedAt --sort updated
```

This returns the 5 most recently updated repos. Build an `AskUserQuestion` from the results:

```
question: "No remote is set. Which GitHub repo should this be pushed to?"
header: "Target repo"
options:
  - label: "<repo-name-1>"
    description: "Last updated: <updatedAt> — <repo-url-1>"
  - label: "<repo-name-2>"
    description: "Last updated: <updatedAt> — <repo-url-2>"
  - label: "<repo-name-3>"
    description: "Last updated: <updatedAt> — ..."
  - label: "Paste a link"
    description: "I'll provide the full repo URL myself"
  - label: "Chat about this"
    description: "Stop — I want to talk about this first"
```

- If user selects a repo from the list: set remote with `git remote add origin <url>` then continue.
- If user selects "Paste a link" or types "Other": ask them to provide the full URL, then `git remote add origin <url>`.
- If user selects "Chat about this": stop completely and listen.
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
  - label: "Chat about this"
    description: "Stop — I want to talk about this first"
```

- If user selects "New branch", ask for the name with a follow-up `AskUserQuestion` or text prompt.
- If user selects "Chat about this": stop completely and listen.
- If pushing to main/master, note: "This pushes directly to the default branch."

### Step 2.5 — Screen recording for README (BLOCKING — use AskUserQuestion)

Ask before touching the README:

```
question: "Do you want to record the app and embed a demo in the README?"
header: "Demo recording"
options:
  - label: "Yes — record and embed"
    description: "Invoke the screen-recording skill, render a GIF, and add it to the README"
  - label: "I already have a video — add it"
    description: "I'll paste a YouTube URL or GIF path to embed"
  - label: "No — skip recording"
    description: "Proceed without a demo video"
  - label: "Chat about this"
    description: "Stop — I want to talk about this first"
```

**If "Yes — record and embed":**
1. Invoke the `screen-record` skill to capture the app flow
2. After recording completes, render a GIF: look for a `render:gif` script in package.json or equivalent
3. Commit the GIF to the repo (e.g. `docs/demo.gif` or `video/out/demo.gif`)
4. Add to README at a visible position (below the description, before install steps):
   ```markdown
   ![Demo](docs/demo.gif)
   ```
5. Continue to README check step

**If "I already have a video — add it":**
- If YouTube URL: add a linked thumbnail to README:
  ```markdown
  [![Watch the demo](https://img.youtube.com/vi/VIDEO_ID/maxresdefault.jpg)](https://youtu.be/VIDEO_ID)
  ```
- If local GIF path: copy to `docs/` and embed with `![Demo](docs/demo.gif)`
- Continue to README check step

**If "No — skip recording":** continue immediately.
**If "Chat about this":** stop completely and listen.

---

### Step 2.6 — README check (BLOCKING — use AskUserQuestion)

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
    description: "Generate an in-depth README before pushing"
  - label: "Chat about this"
    description: "Stop — I want to talk about this first"
```

- If user selects "Yes, update it": ask them what to add/change, make the edits, then continue.
- If user selects "create one": generate an **in-depth README** based on the repo contents — not a minimal stub. Include: project description, features/highlights, requirements, full setup/installation steps, usage guide with examples, architecture overview, configuration details, and license. Read enough source files to write something comprehensive. Show it for approval, then continue.
- If user selects "Chat about this": stop completely and listen.

### Step 3 — Scan for sensitive files
- `.env`, `.env.*`
- `.claude/**`
- `credentials.json`, `secrets.*`, `*.pem`, `*.key`
- `.gitignore` — always exclude, unstage without asking
- `memory.md` — always exclude, unstage without asking
- `CLAUDE.md` — always exclude, unstage without asking
- `learnings.md` — always exclude, unstage without asking
- Plans and specs files (`PLAN.md`, `SPEC.md`, `*-plan.md`, `*-spec.md`, `plans/`, `specs/`, `PROGRESS.md`) — always exclude, unstage without asking
- Any file containing obvious secrets

If sensitive files are staged or modified, **stop and ask** the user what to do. For `.gitignore`, `memory.md`, `CLAUDE.md`, `learnings.md`, and plan/spec files, unstage them silently with `git reset HEAD <file>` and note it in the confirmation summary.

**Also audit `.gitignore` coverage before staging:**
- `.env` in `.gitignore` does NOT match `.env.local` or `.env.*` — check that all dotenv variants are covered
- If `.gitignore` is missing `.env.*` or `.env.local`, offer to add them before proceeding with `git add`

### Step 3.5 — Security scan (BLOCKING — do not skip)

Before showing the confirmation summary, **launch the security-scanner agent** to audit the entire codebase for security violations and sensitive data exposure.

Dispatch a **general-purpose** Agent with this prompt:

```
Agent tool (general-purpose):
  description: "Pre-push security scan"
  prompt: |
    You are the Security Scanner. Perform a fast pre-push security audit of the codebase at [project root].
    This is a BLOCKING check — the push must NOT proceed if Critical findings exist.

    ## Scan Checklist (execute ALL):

    1. **Secrets in staged files** — scan `git diff --cached` for:
       - API keys (sk-, ak_, ghp_, xoxb-, AKIA)
       - Tokens (Discord bot tokens, JWT, bearer)
       - Passwords/secrets in variable assignments
       - Private keys (BEGIN RSA/OPENSSH PRIVATE KEY)
       - Connection strings with embedded credentials
       - .env file contents

    2. **Secrets in full working tree** — grep the entire codebase for the patterns above

    3. **.gitignore coverage** — verify .env*, *.pem, *.key, *.sqlite, credentials.json are covered

    4. **Code security patterns** — check for:
       - eval()/Function() with user input
       - SQL injection (raw string concat in queries)
       - Command injection (exec/spawn with unsanitized input)
       - Missing permission checks on commands
       - Prompt injection vulnerabilities in AI modules

    5. **Config files** — verify YAML/JSON configs use ${ENV_VAR} syntax, no hardcoded secrets

    ## Output Format:
    CRITICAL: [list or "none"]
    HIGH: [list or "none"]
    MEDIUM: [list or "none"]
    LOW: [list or "none"]
    VERDICT: [SAFE TO PUSH | BLOCK — fix critical issues first]
```

**After the agent returns:**

- If **VERDICT = SAFE TO PUSH** (zero Critical/High findings): proceed to Step 4 with a one-line summary (e.g., "Security scan: PASS — 0 critical, 2 low findings").

- If **any findings exist (Critical, High, Medium, or Low):** present EACH finding to the user individually using `AskUserQuestion` as a prehook-style gate. Walk through findings from most severe to least severe.

**For each finding, use this AskUserQuestion format:**

```
question: "Security finding: <short description of the issue>"
header: "<CRITICAL|HIGH|MEDIUM|LOW>"
options:
  - label: "Fix it — remove/redact this"
    description: "<explain WHY this is a security violation in plain language, e.g. 'This API key is hardcoded in source code. If pushed to GitHub, anyone with repo access can steal it and rack up charges on your account.'>"
  - label: "Keep it — I accept the risk"
    description: "Push this as-is. I understand the risk: <1-line consequence summary>"
  - label: "Chat about this"
    description: "Stop — I want to discuss this finding before deciding"
```

**Rules for the prehook walkthrough:**
- Show ONE finding at a time — do not batch them into a single question
- For each finding, explain in the description **why** it's a violation and **what could go wrong** (credential theft, unauthorized access, data leak, etc.) — don't just name the pattern, explain the real-world impact
- If the user selects "Fix it": perform the fix immediately (delete the secret, move to env var, add to .gitignore, etc.) before showing the next finding
- If the user selects "Keep it": log it as an accepted risk, move to the next finding
- If the user selects "Chat about this": stop and listen, resume only when they redirect
- After walking through ALL findings: if ANY Critical finding was kept (not fixed), show a final warning:
  ```
  question: "You chose to keep N critical security issue(s). Are you absolutely sure you want to push with these unresolved?"
  header: "Final warning"
  options:
    - label: "Yes — push anyway"
      description: "I accept full responsibility for these security risks"
    - label: "Go back — let me fix them"
      description: "Re-run the security findings I kept"
    - label: "Cancel push"
      description: "Abort — don't push anything"
  ```
- Include a one-line security summary in the Step 4 confirmation showing: findings total, fixed count, accepted count (e.g., "Security scan: 4 findings — 3 fixed, 1 accepted (LOW)").

---

### Step 4 — Show final confirmation summary + AskUserQuestion gate (BLOCKING — do not skip)

Display the summary to the user:

```
Ready to push:
  Repo:    <remote URL>
  Branch:  <branch name>
  Files:   <list of staged files>
  Commit:  "<proposed commit message>"
  Author:  <your-username> <<your-email>>  ✓
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
  - label: "Chat about this"
    description: "Stop — I want to talk about this first"
```

**Do NOT run any git commit or git push command until the user selects "Yes, push it".**
**If "No, cancel": abort and tell the user nothing was pushed.**
**If "Chat about this": stop completely, listen to what they say, and wait for them to redirect before doing anything.**

### Step 5 — Execute
1. If first push, verify `README.md` exists; create one only if the user asks.
2. Ensure branch is up to date (pull/rebase if needed) unless user says otherwise.
3. Commit and push to the confirmed repo and branch.

---

### Step 6 — Deploy (BLOCKING — use AskUserQuestion)

After a successful push, always ask:

```
question: "Do you want to deploy after pushing?"
header: "Deploy"
options:
  - label: "No — push only"
    description: "Done. No deployment."
  - label: "Vercel"
    description: "Deploy frontend/fullstack app to Vercel"
  - label: "Railway"
    description: "Deploy backend or full-stack app to Railway"
  - label: "GitHub Pages"
    description: "Deploy static site from /docs or gh-pages branch"
  - label: "Netlify"
    description: "Deploy static site or JAMstack app to Netlify"
  - label: "Chrome Web Store"
    description: "Package and submit extension update to the Chrome Web Store"
  - label: "Chat about this"
    description: "Stop — I want to talk about this first"
```

**If "Chat about this":** stop completely and listen.

#### Platform playbooks

**Vercel:**
```bash
# Install CLI if needed
npm i -g vercel
# Deploy production
vercel --prod
```
- Ask if this is a first deploy (needs `vercel link` first)
- After deploy: print the live URL
- Verify with `curl -s <url> | head -5`

**Railway:**
```bash
railway up --detach
# Then run migrations if applicable
railway run <migrate-command>
```
- After deploy: `railway logs | tail -20` to check for errors
- Print the Railway dashboard URL

**GitHub Pages:**
```bash
# Option A — docs/ folder on main (most common)
# Ensure Settings → Pages → Source = main / docs/
# Nothing to run — GitHub deploys on push automatically

# Option B — gh-pages branch
npx gh-pages -d build   # or 'dist', 'out', '_site'
```
- Ask which option: docs/ folder vs gh-pages branch
- If docs/ folder: confirm Pages is enabled in repo settings, print the Pages URL
- After deploy: `curl -s <pages-url>` to verify it's live

**Netlify:**
```bash
npm i -g netlify-cli
netlify deploy --prod --dir=build  # adjust dir as needed
```
- Ask for the publish directory if not obvious (`build`, `dist`, `out`, `public`)
- After deploy: print the live URL

**Chrome Web Store:**
- Remind user the store has a manual review process (no CLI automation)
- Steps to walk through:
  1. Build the production zip (exclude `node_modules`, `tests/`, dev files)
  2. Go to [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
  3. Select the extension → **Package** → **Upload new package** → upload zip
  4. Fill in any updated store listing details
  5. Click **Submit for review**
- Offer to build the zip now: `zip -r extension.zip <src-dir>/ --exclude "*/node_modules/*" --exclude "*/tests/*"`

---

## Example Prompt
User: "push my changes"
Assistant:
1. Run status/diff/remote/branch checks + fix git identity if needed.
2. **If no remote set:** run `gh repo list` → AskUserQuestion with last 5 repos + "Paste a link" option → set remote.
3. AskUserQuestion → "Which branch?" (options: current branch / main / new branch)
4. AskUserQuestion → "Record app for README?" (yes / have video / skip)
5. AskUserQuestion → "Does the README need updating?" (yes / no / create)
6. Scan for sensitive files — stop if any found.
7. **Launch security-scanner agent** — full codebase audit. Block push if critical findings.
8. Show confirmation summary (repo, branch, files, commit message, author, security scan result).
9. AskUserQuestion → "Are you sure you want to push?" (Yes, push it / No, cancel)
10. Commit and push only after explicit "Yes, push it".
11. AskUserQuestion → "Deploy?" (No / Vercel / Railway / GitHub Pages / Netlify / Chrome Web Store)

---

## Examples

See [`examples.md`](.claude/skills/gitpush/examples.md) for full annotated walkthroughs.

**Available examples:**
- **Example 1** — Pushing files to a separate empty repo (different repo from working directory, first-time push, false-positive secret scan)

