---
name: gitpush
description: This skill should be used when the user asks to "gitpush", "push my code", "push to the repo", "push this branch", "push changes upstream", or otherwise wants to push local commits to a remote. It runs prehook questions (configure the remote if missing, choose the branch, decide on a security review) and guarantees the chosen branch is in sync with origin's default branch before pushing.
version: 0.1.0
---

# gitpush

Push local commits to a remote safely. Before any `git push` runs, gather the
repo's real state, ask the user the required prehook questions, and make sure
the branch being pushed is in sync with origin's default branch (main/master)
so the push is a clean fast-forward and never clobbers remote history.

## Workflow

Run these steps in order. Do not push until every gate passes.

### Step 1 — Preflight (gather state)

Run the preflight script and parse its `KEY=VALUE` output:

```bash
bash "${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/skills/gitpush}/scripts/preflight.sh"
```

It reports: `IS_GIT_REPO`, `CURRENT_BRANCH`, `LOCAL_BRANCHES`, `HAS_ORIGIN`,
`ORIGIN_URL`, `WORKTREE_DIRTY`, `UNCOMMITTED_COUNT`, `FETCH_OK`,
`DEFAULT_BRANCH`, `UPSTREAM`, `BEHIND_UPSTREAM`/`AHEAD_UPSTREAM`, and
`BEHIND_DEFAULT`/`AHEAD_DEFAULT`. The script never mutates the repo (it does a
read-only `git fetch`). Base all decisions below on these values, not guesses.

If `IS_GIT_REPO=false`, stop and ask whether to `git init` here before
continuing — there is nothing to push otherwise.

### Step 2 — Prehook questions

Ask the prehook questions with the **AskUserQuestion** tool. Skip any question
whose answer is already unambiguous from preflight, and surface them together
where possible rather than one message at a time.

1. **Remote (only if `HAS_ORIGIN=false`).** No `origin` is configured, so ask
   for the repository to push to. Offer to create/connect it:
   - If the GitHub CLI is available (`gh auth status` succeeds), offer
     `gh repo create <name> --source=. --remote=origin` (ask public vs private).
   - Otherwise ask for the remote URL and run
     `git remote add origin <url>`.
   Confirm the URL before adding it. If `HAS_ORIGIN=true`, skip this question.

2. **Branch to push.** Ask which branch to push, defaulting to
   `CURRENT_BRANCH`. Offer the entries from `LOCAL_BRANCHES` as options. If the
   user picks a branch other than the current one, `git switch <branch>` first
   and re-run preflight so the sync numbers reflect that branch.

3. **Security review.** Ask whether a security review is needed before pushing.
   Recommend "yes" when the diff touches auth, secrets, crypto, input handling,
   network calls, or dependencies. If yes, run the **security-review** skill (or
   the `/security-review` command) and report findings **before** pushing. If it
   surfaces serious issues, stop and let the user decide whether to proceed.

### Step 3 — Sync with origin's default branch

Guarantee the branch being pushed is in sync with origin before pushing.

- If `FETCH_OK=false`, the remote was unreachable — resolve connectivity (or
  re-add the remote) before continuing.
- If `WORKTREE_DIRTY=true`, there are uncommitted changes. Ask whether to
  commit them (and with what message) or stash them; do not push around them
  silently.
- Inspect `BEHIND_DEFAULT` (commits on `origin/<DEFAULT_BRANCH>` not in the
  branch):
  - `0` → in sync, proceed.
  - `>0` → the branch is behind origin's default branch. Integrate first:
    `git rebase origin/<DEFAULT_BRANCH>` (preferred for a clean history) or
    `git merge origin/<DEFAULT_BRANCH>` if the user prefers. Resolve any
    conflicts, then re-run preflight to confirm `BEHIND_DEFAULT=0`.
  - `unknown` → the default branch could not be determined; confirm the target
    branch with the user before proceeding.
- Also check `BEHIND_UPSTREAM` for the branch's own upstream when one exists
  (`UPSTREAM` non-empty): if `>0`, the remote branch has commits the local one
  lacks — integrate them so the push stays a fast-forward.

Never use `--force` to work around a non-fast-forward. Only consider
`--force-with-lease` after an intentional rebase, and confirm with the user
first.

### Step 4 — Verify authorship (HARD GATE)

**THIS IS A HARD GATE. The push MUST NOT proceed until every commit to be
pushed passes this check. No exceptions.**

Before pushing, verify every commit that will reach the remote:

```bash
# List commits about to be pushed (local ahead of upstream)
git log origin/<branch>..HEAD --format='%h %an <%ae> | %cn <%ce>'
```

For every commit in the output:

1. **Author** (`%an <%ae>`) must be exactly:
   **`ashcastelinocs124 <ashleyn4@illinois.edu>`**
2. **Committer** (`%cn <%ce>`) must be exactly:
   **`ashcastelinocs124 <ashleyn4@illinois.edu>`**
3. **No co-authors.** Run `git log origin/<branch>..HEAD --format='%(trailers)'`
   and confirm there are zero `Co-authored-by:` trailers. Also check commit
   bodies for any "Generated with", "Co-authored-by:", or agent attribution
   lines.

If ANY commit fails ANY of these checks:
- **Stop immediately.** Do not push.
- Fix the offending commits. For author/committer:
  ```bash
  GIT_COMMITTER_NAME="ashcastelinocs124" \
  GIT_COMMITTER_EMAIL="ashleyn4@illinois.edu" \
  git commit --amend --author="ashcastelinocs124 <ashleyn4@illinois.edu>" --no-edit
  ```
  For multiple commits, use `git rebase` with `GIT_COMMITTER_*` env vars set.
- For co-author/agent trailers: amend to strip those lines from the message body.
- Re-run this check after fixing. Push only when every commit is clean.

Only proceed to Step 4b when this gate passes.

### Step 4b — Exclude plans & internal docs (HARD GATE)

**Never push internal planning or design material to the repo.** These are
working artifacts, not shippable code — they stay local. Surface and remove
them BEFORE pushing.

Inspect every path in the commits about to go out:

```bash
git diff --name-only origin/<branch>..HEAD   # new branch: diff against the base, e.g. origin/<DEFAULT_BRANCH>..HEAD
```

Stop and drop from the commit any path that is a plan or internal doc:

- **Planning docs** — `docs/plans/**`, `docs/superpowers/plans/**`,
  `docs/superpowers/specs/**`, and any `*-plan.md` / `*-spec.md`.
- **Design briefs** — `docs/design/**` (e.g. frontend-design skill output).
- **Strategy / premortem reports** — root-level `premortem-*.html`,
  `*-report-*.html`, and their transcripts.
- **Internal docs generally** — any markdown/notes not needed at runtime or by
  consumers of the repo (session logs, scratch notes, agent briefs). When
  unsure whether a doc is "internal," ask the user before including it.

To drop a path from the commit: `git restore --staged <path>` (if only staged),
or `git checkout <base> -- <path>` then re-amend, then re-run this gate. Push
only code and the docs that genuinely ship with it (README, runtime config).

Only proceed to Step 4c when this gate passes.

### Step 4c — Formatting & lint check (HARD GATE)

**Push only code that meets the project's own formatting and lint standards.**
Unformatted code creates noisy diffs and reads as careless to anyone browsing the
repo, so verify the working tree is clean *by the project's own tooling* before it
goes out. Run everything in CHECK mode here — the gate verifies, it must not
rewrite files mid-push.

Detect what the project uses (look for config in `pyproject.toml`, `ruff.toml`,
`.prettierrc*`, `package.json` scripts) and run the matching checks from the
directory that owns each config:

- **Python** (ruff configured, or `pyproject.toml`/`ruff.toml` present):
  ```bash
  ruff format --check .
  ruff check .
  ```
  Fall back to `black --check . && flake8` if that's the repo's chosen tooling.
- **JS/TS** (`package.json` present): run whichever scripts exist —
  ```bash
  npm run format:check    # or: npx prettier --check .
  npm run typecheck       # if defined (e.g. tsc -b / tsc --noEmit)
  npm run lint            # if defined
  ```
- Honor whatever formatter/linter the repo already configures rather than imposing
  one. If the project has no formatting tooling at all, say so and skip this gate.

If any check reports unformatted files or errors:
- **Stop. Do not push.**
- Offer to fix it: run the formatter in write mode (`ruff format .`,
  `npx prettier --write .`) plus auto-fixable lint (`ruff check --fix .`), then
  resolve anything left by hand.
- Commit the fix **respecting the Step 4 authorship rules** (author and committer
  `ashcastelinocs124 <ashleyn4@illinois.edu>`), or amend it into the relevant
  commit when that keeps history clean.
- Re-run this gate. Push only when every check passes.

Only proceed to Step 5 when this gate passes.

### Step 5 — Push

Once sync is confirmed, review is done, and authorship is verified, push:

- First push of a new branch (no `UPSTREAM`):
  `git push -u origin <branch>`
- Existing tracking branch: `git push`

Report the result: the branch pushed, the remote, the commit range, and the
compare/PR URL if the remote prints one. If `gh` is available and the user
wants a PR, offer `gh pr create`.

## Notes

- Treat the seven gates — repo/remote exists, branch chosen, review decided,
  sync confirmed, authorship verified, no plans/internal docs included,
  formatting/lint clean — as mandatory. Pushing is outward-facing and hard to
  reverse, so confirm before the actual push.
- Re-run the preflight script after any branch switch, commit, stash, or rebase
  so decisions always reflect current state.
- When this skill creates a commit (e.g. committing the dirty worktree in
  Step 3), always set both author and committer explicitly:
  ```bash
  GIT_COMMITTER_NAME="ashcastelinocs124" \
  GIT_COMMITTER_EMAIL="ashleyn4@illinois.edu" \
  git commit --author="ashcastelinocs124 <ashleyn4@illinois.edu>" -m "..."
  ```
  Then verify with `git log -1 --format='Author: %an <%ae> | Committer: %cn <%ce>'`.
