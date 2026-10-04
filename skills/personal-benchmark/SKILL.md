---
name: personal-benchmark
description: Builds and maintains a PERSONAL coding-model benchmark mined from the user's own Claude Code and Codex history (~/.claude/projects, ~/.codex/sessions). It extracts the kinds of tasks the user actually does, turns them into reproducible graded tasks written in the user's voice, runs any model (Anthropic, OpenAI or other agent CLIs) against them, and keeps a weekly leaderboard. Use this whenever the user wants to know whether a new model release (a new Claude, GPT, Codex, Gemini or open model) is better *for them*, wants to compare models on their own work, mentions benchmarking or evaluating models on their own tasks or prompts, asks to "add <model> to my benchmark", "run my benchmark", "refresh the benchmark", or asks which model to switch to, even if they don't say "benchmark".
---

# Personal Benchmark

Public benchmarks measure someone else's work. This skill measures the user's: it mines their
coding-agent history, finds the task types they repeat and the ones where agents needed
correcting, and turns those into a small, hidden-graded suite they can point at every new model.

Everything lives in `$PB_HOME` (default `~/.personal-benchmark/`):

```
corpus/prompts.jsonl   mined human prompts (redacted)        <- scripts/mine.py
corpus/stats.json      category mix, correction rates, models
suite/tasks/<id>/      the benchmark tasks                    <- you write these
suite/SUITE.md         changelog: what was added/retired and why
models.json            which models to run + the fixed judge model
results/<model>/       one JSON per (task, task-hash)        <- scripts/run.py
report.html            interactive dashboard (offline, one file) <- scripts/report.py + assets/dashboard.html
report.md              plain-text leaderboard twin
history.jsonl          score snapshots, used for the week-over-week trend
```

Scripts are in this skill's `scripts/` dir (call it `S`). All are stdlib Python 3.

Figure out which mode the user wants. If no suite exists yet, start with **Setup**.

---

## Setup (first run)

0. **Bootstrap.** If `$PB_HOME/models.json` doesn't exist, run `python3 S/setup.py` first. It checks tools (python, git, node, claude/codex CLIs), mines the history, and writes `models.json` from the user's most-used models. If it reports blocking problems, help the user fix them before continuing. `README.md` is the human-facing install guide.

1. **Mine.** `python3 S/mine.py` (setup already did this on a first run). Then read `corpus/stats.json`. Tell the user in a few lines what it found: how many prompts and sessions, the top categories by share, the categories with the highest correction rate (the next prompt was pushback like "no, that's wrong"), and the projects they work in most.

2. **Understand the work, not the keywords.** The miner's categories are a keyword heuristic for weighting only. Read the actual prompts to build the real picture. `prompts.jsonl` has ~thousands of rows, so sample instead of reading it whole: e.g. 40 random substantive prompts (`words >= 6`) per major category, plus every prompt where `corrected` is true, which marks where agents struggled. Skip `followup` rows ("yes", "push it"): they steer, they aren't tasks. Use them only to learn the user's register. Write down 6–10 recurring **task archetypes**, each with a one-line description, rough frequency and example prompts. Examples: "add a small UI control to an existing React page", "fix a failing data-pipeline step from a traceback", "explain what a module does", "wire a new LLM tool into an agent loop".

3. **Design the suite.** Aim for 12–20 tasks to start (it's run once per model, so a bigger suite costs more per model). Allocate tasks to archetypes by frequency (`weight` carries the rest), with extra coverage where correction rates are high. Those are the tasks where models actually differ for this user. Present the plan to the user as a short table (archetype → n tasks → grading method) and confirm before writing tasks. It's the one decision worth their input.

4. **Write the tasks.** Follow `references/task-format.md` exactly; read it before writing the first task. The key ideas:
   - Prompts in the user's own voice: terse, their phrasing, their level of under-specification.
   - Small offline synthetic fixtures shaped like their real projects (same languages/frameworks), never copied from their repos.
   - Hidden `check.sh` + `solution/` whenever success is mechanically checkable; `rubric.md` for judgment-heavy tasks.

5. **Validate.** `python3 S/run.py --validate` must show `ok` for every task. Fix anything that fails: a check that passes on the raw fixture doesn't discriminate, and one that fails on the solution is a grader bug.

6. **Configure models.** Create `models.json` if missing (see below). Pre-fill with the model running this session and the user's most-used models from `stats.json.by_model`. Ask which others to include.

7. **Run + report.** `python3 S/run.py` then `python3 S/report.py --open`. Runs take a while (each task is a full agent session), so run it in the background and report when done. The dashboard has headline tiles, the leaderboard, a category heatmap, a weekly trend, score-vs-speed and score-vs-cost charts, and a task grid where clicking a result shows the prompt, the grader's reason, the check log and the model's answer. Summarize the leaderboard in 3–5 lines: who wins overall, where the ranking flips by category, and cost/speed trade-offs.

8. Write `suite/SUITE.md` with the date, archetypes, task list and the reasoning, so next week's refresh has context.

## models.json

```json
{
  "judge": {"harness": "claude", "model": "claude-opus-5-5"},
  "models": [
    {"name": "opus-5.5",   "harness": "claude", "model": "claude-opus-5-5"},
    {"name": "sonnet-5.5", "harness": "claude", "model": "claude-sonnet-5-5"},
    {"name": "gpt-5.5",    "harness": "codex",  "model": "gpt-5.5"},
    {"name": "old-model",  "harness": "claude", "model": "...", "active": false},
    {"name": "gemini-x",   "harness": "custom", "model": "gemini-x",
     "cmd": "gemini -m {model} -y -p {prompt}"}
  ]
}
```

- `harness: claude` runs `claude -p` and `codex` runs `codex exec`, both with permissions bypassed inside a throwaway temp dir and with session persistence off (so benchmark runs never pollute the mined corpus). `custom` is any CLI agent; `{model}`, `{prompt}`, `{workdir}` are shell-quoted placeholders, and the command runs with cwd = workdir. `extra_args` appends flags.
- Note for the user: runs go through *their real harness* (their global CLAUDE.md, hooks and plugins apply to `claude -p`). For a personal benchmark that's arguably the point, since it measures the model in the setup they actually use. It does mean the comparison is "model + my config". If they want a bare comparison and have `ANTHROPIC_API_KEY`, add `"extra_args": ["--bare"]`.
- `judge` grades rubric tasks: `claude` or `codex` harness (Codex-only users get a Codex judge from setup.py). A legacy `"judge_model": "<id>"` string still works and means a Claude judge.
- **Keep the judge fixed across weeks.** Changing it changes every rubric score, which breaks the trend. If it must change, rerun all models with `--force` and note it in SUITE.md.
- Set `active: false` to stop running a model while keeping it in history.
- Auth: `claude` runs drop `ANTHROPIC_API_KEY` from the environment so they use the claude.ai login. A stray key in the shell silently overrides the login and fails with "Credit balance is too low". Set `"use_api_key": true` on a model to keep it.
- Results print `INFRA` for auth, credit or CLI failures. Those aren't cached or scored, because they say nothing about the model. Fix the setup and rerun.

## Add / test a new model

The main recurring use. User says "GPT-6 just dropped, how does it do on my stuff":
1. Add it to `models.json`. Pick the harness by provider: Anthropic → `claude`, OpenAI → `codex`, others → `custom` with that vendor's CLI. Confirm the exact model id (check the vendor's model list, or try `claude -p --model X "hi"` / `codex exec -m X "hi"`) before burning a full run on a typo.
2. `python3 S/run.py --models <name>`. Cached results for other models are reused, so only the new model runs.
3. `python3 S/report.py --open`, then answer the question they actually asked: should I switch? Compare it to the model they use most (from `stats.json`). Say where it wins and loses by category, mention cost and speed, and point out tasks every model fails (suite gaps, not model signal).

## Weekly refresh

The user's work drifts, and a benchmark mined in June goes stale by September. The refresh:

1. `python3 S/mine.py`, then compare `stats.json` to the snapshot in `suite/SUITE.md`. Has the category mix shifted? Are there new projects, languages or frameworks? A new high-correction cluster?
2. **Check for new model releases.** If `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` are set, list models (`GET https://api.anthropic.com/v1/models`, `GET https://api.openai.com/v1/models`). Otherwise use web search: "new Anthropic model release", "new OpenAI model release", "new coding model release this week". Add any new *coding-capable frontier* model to `models.json` as active. Skip embeddings, TTS, image models and dated snapshots of models already listed.
3. **Evolve the suite conservatively.** Add 1–3 tasks for new or under-covered archetypes, and retire (`"retired": true`) tasks that all active models pass three weeks running, since they no longer discriminate. Adjust weights to the new category mix. Leave other tasks alone: every edit forces a re-run for every model, and stability is what makes week-over-week numbers mean something. Validate new tasks with `--validate`.
4. `python3 S/run.py` (runs only missing pairs: new models × all tasks, all models × new tasks), then `python3 S/report.py`.
5. Append a dated entry to `suite/SUITE.md`: mix shift, tasks added/retired, models added, headline movement on the leaderboard.

**Scheduling** is the user's call, because it means an unattended agent running with permissions bypassed every week. Don't install a scheduler on your own. If they want automation, explain that trade-off and let them set it up: a launchd/cron entry they install that runs `mine.py`, then `claude -p "use the personal-benchmark skill: weekly refresh"`, then `run.py` and `report.py`. A milder option is to skip unattended runs and refresh when they ask, or remind them weekly.

## Privacy

The corpus stays on disk under `$PB_HOME`. `mine.py` redacts keys, tokens, emails and long hex strings, but it's a heuristic, so treat `corpus/` as sensitive. Prompts and fixtures *are* sent to whichever model provider runs them, the same as normal use, which is another reason fixtures must be synthetic and must not copy code from the user's real repos.
