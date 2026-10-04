# Task format

Each task is a directory under `$PB_HOME/suite/tasks/<id>/` (default `~/.personal-benchmark`).
Use ids like `t07-csv-dedupe` (number + slug) so they sort and read well in the report.

```
t07-csv-dedupe/
├── task.json      metadata (required)
├── prompt.md      exactly what the model receives (required)
├── fixture/       starting repo, copied into a fresh git-initialized temp dir (optional for pure Q&A)
├── check.sh       hidden deterministic grader, run from the workdir; exit 0 = pass (preferred)
├── hidden/        hidden test files that check.sh copies in or references via $TASK_DIR/hidden
├── setup.sh       optional: builds state a file copy can't (git history + a local bare remote, a sqlite db), runs in the workdir after the copy
├── solution/      reference solution, overlaid onto fixture by `run.py --validate` (required with check.sh)
├── solution.sh    alternative/extra reference solution as commands (for state-based tasks, e.g. git merges)
└── rubric.md      LLM-judge rubric (use when the outcome can't be checked mechanically)
```

check.sh gets `$TASK_DIR` (this task's dir) and `$FINAL_MESSAGE_FILE` (the model's final reply),
so a check can grade an *answer* ("who signed up since sept 28?") as well as file changes.
For validation, put the reference answer in `solution/ANSWER.md`. If setup.sh creates its own
git repo, the runner leaves it alone. Otherwise it git-inits the fixture so the judge sees a clean diff.

The model only ever sees `fixture/` and `prompt.md`. Everything else is outside its workdir,
which is what keeps the grader hidden. Never put tests the grader relies on inside `fixture/`,
because the model could edit them.

## task.json

```json
{
  "title": "Dedupe customer CSV by normalized email",
  "category": "data-script",
  "weight": 1.5,
  "grading": "check",
  "timeout_s": 900,
  "derived_from": "12 prompts like 'clean up this csv, there are dupes' (2026-07..2026-09)",
  "why": "data-script has the highest correction rate in my history (4%)",
  "created": "2026-10-03"
}
```

- `category`: use the categories from `corpus/stats.json` (merge or split them when the agent's clustering finds a better taxonomy, but keep names stable across weeks so trends stay readable).
- `weight`: proportional to how often the user does this kind of task. 1 = typical. The leaderboard is weighted, so a category the user hits daily should count for more than one they hit once a month.
- `retired: true` removes a task from scoring but keeps its history. Prefer retiring over deleting.
- Editing ANY file in the task changes its hash and causes every model to re-run it, so edit deliberately.

## prompt.md: write it in the user's voice

The value of a *personal* benchmark is that it asks the way this user asks. Copy the user's
register from the corpus: terse, lowercase, typos, "do it", missing context the agent has
to discover from the repo. A model that only does well on fully specified prompts is not
the model this user needs. Don't add hints the user wouldn't give.

The prompt must still be *answerable* from the fixture. If the real prompt depended on
context that isn't in the fixture (an earlier conversation, a live URL, credentials),
put that context into the fixture (a README, an issue.md, a log file) rather than into the prompt.

## Grading: prefer check.sh

Use `check.sh` whenever success is mechanically verifiable: tests pass, output file matches,
a function returns the right thing, a bug no longer reproduces, a lint rule holds. Make it
check the *behavior*, not the exact implementation: several correct solutions should all pass.

```bash
#!/bin/bash
# runs with cwd = the model's workdir; $TASK_DIR = this task's dir
set -e
cp "$TASK_DIR/hidden/test_dedupe.py" .
python3 -m pytest -q test_dedupe.py
```

Use `rubric.md` for judgment-heavy work: explanations, reviews, plans, UI copy, "what does
this code do". The judge sees the prompt, the rubric, the model's final message and the
git diff. Write rubrics as concrete, checkable criteria with points, plus explicit
deductions for the failure modes the user actually corrected in their history:

```markdown
- (4) Identifies the root cause: the cache key omits `user_id`, so users see each other's data.
- (3) Proposes a fix that adds `user_id` to the key; doesn't just disable the cache.
- (2) Mentions the existing stale entries need invalidating.
- (1) Under 250 words; no unrequested refactors.
Deduct 3 if it edits files (the user asked for an explanation only).
```

`grading: "both"` is allowed: then both check and judge (score ≥ 7) must pass.

## Fixtures: small, real-shaped, offline

- Small: < 50 files and < 2 MB. Mirror the *shape* of the user's real projects (their languages, frameworks, layout conventions), but synthesize the content. Never copy proprietary code, data or secrets from the user's real repos into a fixture.
- Offline: assume no network. Vendor whatever's needed or stick to the stdlib. A task that fails because `pip install` timed out measures the network, not the model.
- Deterministic: no wall-clock, randomness or ordering dependencies in the grader.
- Fast: check.sh should finish in seconds.

## Validate before you trust a task

`python3 scripts/run.py --validate` must print `ok` for every task:
1. check.sh FAILS on the untouched fixture (otherwise the task can't tell good models from bad ones)
2. check.sh PASSES on fixture + `solution/` (otherwise no model can pass, and the task only measures your grader bug)

Rubric-only tasks skip this check, so read the rubric once more and ask: would two careful graders give the same score?
