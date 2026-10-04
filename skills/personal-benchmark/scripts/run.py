#!/usr/bin/env python3
"""Run the personal benchmark suite against models and grade the results.

  python3 run.py                       run every active model on every task (skips cached results)
  python3 run.py --models opus-5.5     only these model names (from models.json)
  python3 run.py --tasks t01,t02       only these task ids
  python3 run.py --validate            sanity-check tasks: check must FAIL on fixture, PASS on solution
  python3 run.py --force               ignore cached results
  python3 run.py --jobs 3              parallel runs (default 2)

Results land in $PB_HOME/results/<model>/<task_id>-<task_hash>.json, so editing a task
re-runs it for every model while untouched tasks keep their scores.
"""
import argparse, concurrent.futures as cf, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
from datetime import datetime, timezone

PB_HOME = os.path.expanduser(os.environ.get("PB_HOME", "~/.personal-benchmark"))
TASKS = f"{PB_HOME}/suite/tasks"


# Runs go through the user's logged-in agent CLIs (subscription), never raw API keys: a stray key in
# the shell silently overrides the login (e.g. "Credit balance is too low"). use_api_key opts back in.
API_KEYS = {"claude": ("ANTHROPIC_API_KEY",), "codex": ("OPENAI_API_KEY", "CODEX_API_KEY")}


KEYS_FILE = f"{PB_HOME}/.keys"  # KEY=value lines, chmod 600; only used for harnesses set to "api" auth


def read_keys():
    try:
        return dict(l.strip().split("=", 1) for l in open(KEYS_FILE) if "=" in l and not l.startswith("#"))
    except OSError:
        return {}


def auth_mode(harness):
    """'plan' (the logged-in Claude Code / ChatGPT subscription, default) or 'api' (bill an API key)."""
    try:
        return load_models().get("auth", {}).get(harness, "plan")
    except (OSError, ValueError):
        return "plan"


def auth_env(m):
    """-> (env to add, env names to drop) for one model/judge run, per the chosen auth mode."""
    h = m.get("harness", "claude")
    keys = API_KEYS.get(h, ())
    if not keys:
        return {}, ()
    if not (m.get("use_api_key") or auth_mode(h) == "api"):
        return {}, keys  # plan: hide stray keys so they can't override the login
    val = next((os.environ.get(k) for k in keys if os.environ.get(k)), None) or read_keys().get(keys[0])
    if not val:
        raise RuntimeError(f"infra error: {h} is set to API-key auth but no {keys[0]} in the environment or "
                           f"{KEYS_FILE}. Re-run setup.py or set auth.{h} to \"plan\" in models.json")
    return {k: val for k in keys}, ()


def host_agent():
    """The coding agent this script is running inside: 'codex', 'claude' or None (plain terminal)."""
    if os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID"):
        return "codex"  # checked first: innermost host wins when codex was launched from Claude Code
    if os.environ.get("CLAUDECODE"):
        return "claude"
    return None
PASS_SCORE = 7  # judge score (0-10) counted as a pass


def load_models():
    with open(f"{PB_HOME}/models.json") as f:
        return json.load(f)


def task_hash(tdir):
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(tdir)):
        dirs.sort()
        for fn in sorted(files):
            p = os.path.join(root, fn)
            h.update(os.path.relpath(p, tdir).encode())
            h.update(open(p, "rb").read())
    return h.hexdigest()[:10]


def load_tasks(only=None):
    out = []
    for tid in sorted(os.listdir(TASKS)) if os.path.isdir(TASKS) else []:
        tdir = f"{TASKS}/{tid}"
        if not os.path.isfile(f"{tdir}/task.json") or (only and tid not in only):
            continue
        t = json.load(open(f"{tdir}/task.json"))
        if t.get("retired"):
            continue
        t.update(id=tid, dir=tdir, hash=task_hash(tdir), prompt=open(f"{tdir}/prompt.md").read().strip())
        out.append(t)
    return out


def sh(cmd, cwd, timeout, stdin=None, env=None, drop_env=()):
    t0 = time.time()
    full_env = {k: v for k, v in {**os.environ, **(env or {})}.items() if k not in drop_env}
    try:
        # stdin must be closed when unused: claude/codex otherwise wait on it until the timeout
        p = subprocess.run(cmd, cwd=cwd, input=stdin, stdin=None if stdin is not None else subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=timeout, shell=isinstance(cmd, str), env=full_env)
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""), "TIMEOUT", time.time() - t0


# After the agent finishes, its tree is untrusted: check.sh runs the agent's code, and git reads the agent's
# .git/config (core.fsmonitor, diff.external, filters can all run commands). So post-agent steps run in an OS
# sandbox: writes only to the workdir + temp, no network. macOS: sandbox-exec; Linux: bubblewrap.
def _sandbox_profile(wd):
    allow = [os.path.realpath(p) for p in (wd, tempfile.gettempdir(), "/tmp", "/private/var/folders")]
    return ("(version 1)(allow default)(deny network-outbound (remote ip))(deny file-write*)"
            + "".join(f'(allow file-write* (subpath "{p}"))' for p in allow if os.path.exists(p))
            + '(allow file-write* (subpath "/dev"))')


_warned = []


def confined(cmd, wd):
    cmd = ["bash", "-c", cmd] if isinstance(cmd, str) else list(cmd)
    if sys.platform == "darwin" and shutil.which("sandbox-exec"):
        return ["sandbox-exec", "-p", _sandbox_profile(wd), *cmd]
    if shutil.which("bwrap"):
        return ["bwrap", "--ro-bind", "/", "/", "--bind", wd, wd, "--bind", "/tmp", "/tmp", "--dev", "/dev",
                "--proc", "/proc", "--unshare-net", "--die-with-parent", "--chdir", wd, *cmd]
    if not _warned:
        _warned.append(1)
        print("WARNING: no sandbox-exec/bwrap found; grading runs agent-written code UNSANDBOXED", file=sys.stderr)
    return cmd


# git settings that would let a planted .git/config run commands; GIT_CONFIG_* env beats repo config
SAFE_GIT_ENV = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
                **{k: v for i, (key, val) in enumerate([("core.fsmonitor", "false"), ("core.hooksPath", "/dev/null"),
                                                        ("diff.external", ""), ("core.pager", "cat"),
                                                        ("core.attributesFile", "/dev/null")])
                   for k, v in ((f"GIT_CONFIG_KEY_{i}", key), (f"GIT_CONFIG_VALUE_{i}", val))},
                "GIT_CONFIG_COUNT": "5"}


def agent_diff(wd, base, limit):
    """Everything the agent changed since `base` (committed or not), computed in the sandbox."""
    if not re.fullmatch(r"[0-9a-f]{40,64}", base or ""):
        return "(no base commit recorded)"
    git = ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null"]
    sh(confined([*git, "add", "-A"], wd), wd, 60, env=SAFE_GIT_ENV)
    out = []
    for extra in (["--stat"], []):
        _, o, _, _ = sh(confined([*git, "diff", "--cached", "--no-ext-diff", "--no-textconv", *extra,
                                  "--end-of-options", base], wd), wd, 60, env=SAFE_GIT_ENV)
        out.append(o)
    return (out[0] + "\n" + out[1])[:limit]


def make_workdir(task, overlay_solution=False):
    wd = tempfile.mkdtemp(prefix=f"{task['id']}-", dir=f"{PB_HOME}/runs")
    if os.path.isdir(f"{task['dir']}/fixture"):
        shutil.copytree(f"{task['dir']}/fixture", wd, dirs_exist_ok=True)
    if os.path.exists(f"{task['dir']}/setup.sh"):  # builds state a plain copy can't: git history, sqlite dbs
        code, out, err, _ = sh(["bash", f"{task['dir']}/setup.sh"], wd, 120, env={"TASK_DIR": task["dir"]})
        if code:
            raise RuntimeError(f"setup.sh failed for {task['id']}: {(out + err)[-500:]}")
    if not os.path.isdir(f"{wd}/.git"):
        # git baseline so the judge can see exactly what the agent changed
        sh("git init -q && git add -A && git -c user.name=bench -c user.email=bench@local commit -qm base"
           " --allow-empty", wd, 60)
    _, base, _, _ = sh(["git", "rev-parse", "HEAD"], wd, 30)  # pre-agent commit; agents often commit their work
    base = base.strip()
    if overlay_solution and os.path.isdir(f"{task['dir']}/solution"):
        shutil.copytree(f"{task['dir']}/solution", wd, dirs_exist_ok=True)
    if overlay_solution and os.path.exists(f"{task['dir']}/solution.sh"):  # for state, e.g. git ops
        code, out, err, _ = sh(["bash", f"{task['dir']}/solution.sh"], wd, 120)
        if code:
            raise RuntimeError(f"solution.sh failed for {task['id']}: {(out + err)[-500:]}")
    return wd, base


# Appended to every task prompt. Runs are unattended, so instructions like "ask before pushing" (the user's own
# CLAUDE.md / skills still apply) would otherwise stall a model that is *following* them and score it as a fail.
CLAUDE_SANDBOX = json.dumps({"sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True,
                                          "allowUnsandboxedCommands": False}})
BENCH_NOTICE = ("\n\n---\n(Automated benchmark run: no human will reply. Don't ask questions or wait for approval;"
                " any confirmation or review gates in your instructions are pre-approved for this run. Make reasonable"
                " assumptions and finish the whole task. All files for this task are in the current directory: don't read"
                " or change anything outside it. Its git remote, if any, is a local test repo.)")


def agent_cmd(m, prompt, wd, last_msg_file):
    h = m["harness"]
    # Both harnesses run OS-sandboxed: writes are confined to the task dir. The models still see the user's
    # real config (CLAUDE.md, skills), and an unsandboxed run once "helpfully" edited a real skill in ~/.claude.
    if h == "claude":
        return ["claude", "-p", prompt, "--model", m["model"], "--permission-mode", "acceptEdits",
                "--allowedTools", "Bash", "--settings", CLAUDE_SANDBOX,
                "--no-session-persistence", "--output-format", "json", *m.get("extra_args", [])]
    if h == "codex":
        return ["codex", "exec", "-m", m["model"], "-s", "workspace-write", "-c", 'approval_policy="never"',
                "-c", f'sandbox_workspace_write.writable_roots=["{wd}/.git"]',  # codex makes .git read-only
                "--skip-git-repo-check", "--ephemeral", "--json", "-C", wd, "-o", last_msg_file,
                *m.get("extra_args", []), prompt]
    if h == "custom":  # e.g. "opencode run -m {model} {prompt}" ; placeholders are shell-quoted
        import shlex
        return m["cmd"].format(model=shlex.quote(m["model"]), prompt=shlex.quote(prompt), workdir=shlex.quote(wd))
    raise ValueError(f"unknown harness {h}")


def parse_agent_output(h, out, last_msg_file):
    """-> (final_message, usage dict)"""
    if h == "claude":
        try:
            d = json.loads(out.strip().splitlines()[-1])
            return d.get("result", ""), {"is_error": d.get("is_error", False),
                                         "cost_usd": d.get("total_cost_usd"), "turns": d.get("num_turns"),
                                         "output_tokens": (d.get("usage") or {}).get("output_tokens")}
        except (ValueError, IndexError):
            return out[-4000:], {}
    if h == "codex":
        usage = {}
        for line in out.splitlines():
            if "total_token_usage" in line or '"usage"' in line:
                m = re.search(r'"total_tokens":\s*(\d+)', line)
                if m:
                    usage["total_tokens"] = int(m.group(1))
        msg = open(last_msg_file).read() if os.path.exists(last_msg_file) else out[-4000:]
        return msg, usage
    return out[-4000:], {}


def run_check(task, wd, final_msg=""):
    chk = f"{task['dir']}/check.sh"
    if not os.path.exists(chk):
        return None, ""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(final_msg)  # lets checks grade answers, not just file changes
    code, out, err, _ = sh(confined(["bash", chk], wd), wd, task.get("check_timeout_s", 300),
                           env={**SAFE_GIT_ENV, "TASK_DIR": task["dir"], "FINAL_MESSAGE_FILE": f.name})
    os.remove(f.name)
    return code == 0, (out + err)[-3000:]


def judge_config(cfg):
    """models.json "judge": {"harness": "claude"|"codex", "model": ...}; legacy "judge_model" string = claude.
    Unset -> grade with the host agent (the CLI the user is in), using its first configured model."""
    j = cfg.get("judge") or cfg.get("judge_model")
    if isinstance(j, dict):
        return j
    if j:
        return {"harness": "claude", "model": j}
    host = host_agent() or "claude"
    m = next((x for x in cfg.get("models", []) if x.get("harness") == host and x.get("model")), None)
    return {"harness": host, "model": m["model"] if m else ("claude-opus-5-5" if host == "claude" else "")}


def judge(task, wd, base, final_msg, j):
    rubric_path = f"{task['dir']}/rubric.md"
    if not os.path.exists(rubric_path):
        return None, None, ""
    diff = agent_diff(wd, base, 60000)
    prompt = f"""You are grading a coding agent's work on a benchmark task. Be strict and consistent.

## Task given to the agent
{task['prompt']}

## Rubric
{open(rubric_path).read()}

## Agent's final message
{final_msg[-6000:]}

## Changes the agent made (git diff)
{diff or '(no file changes)'}

Score 0-10 against the rubric only. Reply with ONLY a JSON object: {{"score": <int>, "reason": "<one sentence>"}}"""
    tmp = tempfile.mkdtemp(prefix="pb-judge-")
    if j["harness"] == "codex":  # read-only sandbox: the judge only reads the prompt
        last = os.path.join(tmp, "verdict.txt")
        add, drop = auth_env(j)
        code, out, err, _ = sh(["codex", "exec", *(["-m", j["model"]] if j.get("model") else []), "-s", "read-only",
                                "--skip-git-repo-check", "--ephemeral", "-o", last, prompt], tmp, 300,
                               env=add, drop_env=drop)
    else:
        code, out, err, _ = sh(["claude", "-p", "--model", j["model"], "--no-session-persistence",
                                "--output-format", "json"], tmp, 300, stdin=prompt,
                               env=auth_env(j)[0], drop_env=auth_env(j)[1])
    try:
        if j["harness"] == "codex":
            text = open(last).read()
        else:
            text = json.loads(out.strip().splitlines()[-1])["result"]
        shutil.rmtree(tmp, ignore_errors=True)
        d = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        return int(d["score"]) >= PASS_SCORE, int(d["score"]), d.get("reason", "")
    except Exception as e:  # judge failure must not look like a model failure
        return None, None, f"judge error: {e}: {(out + err)[-300:]}"


def run_one(m, task, judge_cfg):
    wd, base = make_workdir(task)
    # outside the workdir: the codex CLI (unsandboxed) writes it, so an agent-planted symlink must not be followed
    msg_dir = tempfile.mkdtemp(prefix="pb-msg-")
    last = os.path.join(msg_dir, "last-message.txt")
    try:
        add, drop = auth_env(m)
    except RuntimeError:
        shutil.rmtree(wd, ignore_errors=True)
        raise
    code, out, err, secs = sh(agent_cmd(m, task["prompt"] + BENCH_NOTICE, wd, last), wd, task.get("timeout_s", 900),
                              env=add, drop_env=drop)
    final_msg, usage = parse_agent_output(m["harness"], out, last)
    infra = usage.pop("is_error", False) or (code not in (0, 124) and not final_msg.strip())
    if infra:  # auth/credit/CLI problems say nothing about the model: report, don't cache
        shutil.rmtree(wd, ignore_errors=True)
        raise RuntimeError(f"infra error (exit {code}): {(final_msg or err)[-300:].strip()}")
    if os.path.exists(last):
        os.remove(last)
    shutil.rmtree(msg_dir, ignore_errors=True)
    diff = agent_diff(wd, base, 20000)  # what the agent changed, for the dashboard
    check_ok, check_log = run_check(task, wd, final_msg)
    judge_ok, judge_score, judge_reason = judge(task, wd, base, final_msg, judge_cfg)
    graded = [x for x in (check_ok, judge_ok) if x is not None]
    res = {
        "model": m["name"], "task": task["id"], "task_hash": task["hash"], "category": task.get("category"),
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "passed": bool(graded) and all(graded), "check_passed": check_ok, "judge_score": judge_score,
        "judge_reason": judge_reason, "exit_code": code, "timed_out": code == 124, "seconds": round(secs, 1),
        "usage": usage, "final_message": final_msg[-3000:], "check_log": check_log, "diff": diff,
        "agent_stderr": err[-1500:], "ungraded": not graded,
    }
    shutil.rmtree(wd, ignore_errors=True)
    os.makedirs(f"{PB_HOME}/results/{m['name']}", exist_ok=True)
    with open(f"{PB_HOME}/results/{m['name']}/{task['id']}-{task['hash']}.json", "w") as f:
        json.dump(res, f, indent=1)
    return res


def validate(tasks):
    """A task is only useful if its check discriminates: fail on the raw fixture, pass on the solution."""
    bad = 0
    for t in tasks:
        problems = []
        if not os.path.exists(f"{t['dir']}/check.sh") and not os.path.exists(f"{t['dir']}/rubric.md"):
            problems.append("no check.sh or rubric.md")
        if os.path.exists(f"{t['dir']}/check.sh"):
            wd, _ = make_workdir(t)
            ok, log = run_check(t, wd)
            shutil.rmtree(wd, ignore_errors=True)
            if ok:
                problems.append("check PASSES on untouched fixture (not discriminating)")
            if os.path.isdir(f"{t['dir']}/solution") or os.path.exists(f"{t['dir']}/solution.sh"):
                wd, _ = make_workdir(t, overlay_solution=True)
                ans = f"{t['dir']}/solution/ANSWER.md"
                ok, log = run_check(t, wd, open(ans).read() if os.path.exists(ans) else "")
                shutil.rmtree(wd, ignore_errors=True)
                if not ok:
                    problems.append(f"check FAILS on reference solution: {log[-400:]}")
            else:
                problems.append("no solution/ to prove the check is passable")
        bad += bool(problems)
        print(f"{'FAIL' if problems else 'ok  '} {t['id']}" + "".join(f"\n     - {p}" for p in problems))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models")
    ap.add_argument("--tasks")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--validate", action="store_true")
    a = ap.parse_args()
    os.makedirs(f"{PB_HOME}/runs", exist_ok=True)
    tasks = load_tasks(set(a.tasks.split(",")) if a.tasks else None)
    if not tasks:
        sys.exit(f"no tasks in {TASKS}")
    if a.validate:
        sys.exit(1 if validate(tasks) else 0)

    cfg = load_models()
    wanted = set(a.models.split(",")) if a.models else None
    models = [m for m in cfg["models"] if (m["name"] in wanted if wanted else m.get("active", True))]
    jobs = [(m, t) for m in models for t in tasks
            if a.force or not os.path.exists(f"{PB_HOME}/results/{m['name']}/{t['id']}-{t['hash']}.json")]
    print(f"{len(jobs)} runs to do ({len(models)} models x {len(tasks)} tasks, cached skipped)")
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        futs = {ex.submit(run_one, m, t, judge_config(cfg)): (m, t) for m, t in jobs}
        for f in cf.as_completed(futs):
            m, t = futs[f]
            try:
                r = f.result()
                mark = "PASS" if r["passed"] else ("UNGRADED" if r["ungraded"] else "fail")
                print(f"{mark:8} {m['name']:<22} {t['id']:<28} {r['seconds']:>6}s")
            except Exception as e:
                print(f"INFRA    {m['name']:<22} {t['id']:<28} {e}")


def forget_codex_trust():
    """codex exec adds each workdir to ~/.codex/config.toml as a trusted project; remove our temp dirs."""
    p = os.path.expanduser("~/.codex/config.toml")
    if not os.path.exists(p):
        return
    s = open(p).read()
    new = re.sub(r'\n?\[projects\."' + re.escape(f"{PB_HOME}/runs/") + r'[^"]*"\]\ntrust_level = "trusted"\n', "\n", s)
    if new != s:
        open(p, "w").write(new)


if __name__ == "__main__":
    try:
        main()
    finally:
        forget_codex_trust()
