# personal-benchmark

**Which model is best for *your* work?** Public benchmarks measure someone else's tasks.
This skill mines your own Claude Code and Codex history, turns the kinds of tasks you actually
do into a small benchmark with hidden graders (written the way *you* phrase things), and runs
any new model against it. The results go into a local dashboard you can refresh every week.

- **Built from your history:** if most of your prompts are "push it to main and staging" or
  "why is the accuracy so low", that's what gets tested.
- **Hidden graders:** each task ships with a check script or rubric the model never sees, plus
  a reference solution that proves the task is passable.
- **Any model:** Anthropic models run through `claude -p`, OpenAI models through `codex exec`,
  and others through any CLI agent you configure.
- **Local and offline:** the corpus, tasks and dashboard stay on your machine. Task prompts go
  to the model providers being tested, the same as normal use.

## Install

You need Python 3.10+, git, and at least one of [Claude Code](https://claude.com/claude-code)
or [Codex CLI](https://github.com/openai/codex), logged in. Node 18+ is optional (for JS tasks).

```bash
git clone https://github.com/ashcastelinocs124/CasStack.git
cp -r CasStack/skills/personal-benchmark ~/.claude/skills/
python3 ~/.claude/skills/personal-benchmark/scripts/setup.py --check-auth
```

(Or run CasStack's `setup.sh`, which installs every skill in the repo.)

Using Codex too? Make the skill visible there as well:

```bash
mkdir -p ~/.codex/skills && ln -s ~/.claude/skills/personal-benchmark ~/.codex/skills/personal-benchmark
```

`setup.py` checks your tools, mines your history into `~/.personal-benchmark/`, and writes
`models.json` from the models you use most. `--check-auth` sends one tiny prompt through each
CLI to confirm you're logged in. It's safe to re-run.

## Use

Open Claude Code (or Codex) and say:

| Say | What happens |
|---|---|
| `build my personal benchmark` | First run: designs ~12–20 tasks from your history, validates them, runs your models, opens the dashboard |
| `run my benchmark` | Runs any model × task pair that hasn't run yet |
| `add gpt-7 to my benchmark` | Tests a new release on your tasks, reusing everyone else's cached results |
| `refresh my benchmark` | Weekly: re-mines, adds/retires a few tasks, checks for new model releases, reruns |

Or call the scripts directly:

```bash
S=~/.claude/skills/personal-benchmark/scripts
python3 $S/run.py --validate            # every task: fails on the starter code, passes on the solution
python3 $S/run.py --models opus-5.5     # run one model
python3 $S/report.py --open             # rebuild and open the dashboard
```

A full run is one real agent session per model per task (e.g. 5 models × 15 tasks = 75 sessions),
billed to your plans. Run it when you have quota to spare.

## Files

```
~/.personal-benchmark/
  corpus/       your mined prompts (secrets redacted) + stats. Treat as private
  suite/tasks/  your benchmark tasks (fixture, prompt, hidden check/rubric, reference solution)
  models.json   which models to run + the fixed judge model
  results/      one JSON per model × task
  report.html   the dashboard
```

To configure models, edit `models.json`:

```json
{
  "judge": {"harness": "claude", "model": "claude-opus-5-5"},
  "models": [
    {"name": "opus-5.5", "harness": "claude", "model": "claude-opus-5-5"},
    {"name": "gpt-6-sol", "harness": "codex", "model": "gpt-6-sol"},
    {"name": "gemini-x", "harness": "custom", "model": "gemini-x", "cmd": "gemini -m {model} -y -p {prompt}"}
  ]
}
```

## Good to know

- **Runs use your real setup.** Your global CLAUDE.md, hooks and plugins apply to every run, so
  the score is "model + your config". For a model-only comparison with an API key, add
  `"extra_args": ["--bare"]`.
- **API keys are ignored by default.** `claude` runs drop `ANTHROPIC_API_KEY` so they use your
  subscription login. Set `"use_api_key": true` on a model to bill the key instead.
- **History expires.** Claude Code deletes transcripts after 30 days by default. The benchmark
  keeps everything it has already mined. Set `"cleanupPeriodDays": 365` in
  `~/.claude/settings.json` to keep more raw history.
- **Automation is opt-in.** The default is to say "refresh my benchmark" once a week. Scheduling
  it unattended means an agent running with permissions bypassed on a timer, so it's left to you
  and not set up by the skill.

## Uninstall

```bash
rm -rf ~/.claude/skills/personal-benchmark ~/.codex/skills/personal-benchmark ~/.personal-benchmark
```
