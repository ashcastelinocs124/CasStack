#!/usr/bin/env python3
"""One-command setup for personal-benchmark. Safe to re-run.

  python3 setup.py               check tools, mine your logs, write models.json
  python3 setup.py --check-auth  also send a 1-line prompt through each CLI to confirm login works
  python3 setup.py --force       rewrite models.json even if it exists

Nothing leaves your machine except the optional --check-auth pings.
"""
import argparse, getpass, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run import API_KEYS, KEYS_FILE, auth_env, host_agent, read_keys  # noqa: E402
PB_HOME = os.path.expanduser(os.environ.get("PB_HOME", "~/.personal-benchmark"))
HOME = os.path.expanduser("~")
OK, WARN, BAD = "  ✓", "  !", "  ✗"


def have(cmd):
    return shutil.which(cmd) is not None


def version(cmd):
    try:
        return subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=20,
                              stdin=subprocess.DEVNULL).stdout.strip().splitlines()[0]
    except Exception:
        return "?"


def harness_for(model_id):
    if model_id.startswith("claude-"):
        return "claude"
    if re.match(r"(gpt-|o\d|codex)", model_id):
        return "codex"
    return None


def short(model_id):  # claude-opus-5-5 -> opus-5.5 ; gpt-6-sol stays
    m = re.match(r"claude-([a-z]+)-(\d+)(?:-(\d+))?(?:-\d{8})?$", model_id)
    return f"{m.group(1)}-{m.group(2)}" + (f".{m.group(3)}" if m.group(3) else "") if m else model_id


PLAN = {"claude": "your Claude Code login (Pro/Max/Team plan)", "codex": "your ChatGPT login (Plus/Pro/Team plan)"}


def ask_auth(h, flag, current):
    """The prehook question: bill this CLI's runs to the user's plan or to an API key?"""
    if flag:
        return flag
    if sys.stdin.isatty():
        try:
            ans = input(f"  ? {h}: use {PLAN[h]} or an API key? [plan/api] "
                        f"(Enter = {current or 'plan'}): ").strip().lower()
        except EOFError:
            ans = ""
        return "api" if ans.startswith("a") else "plan" if ans.startswith("p") else (current or "plan")
    return current or "plan"


def ensure_key(h):
    """API mode needs a key: env var, the saved keys file, or a hidden prompt (saved chmod 600)."""
    name = API_KEYS[h][0]
    if any(os.environ.get(k) for k in API_KEYS[h]):
        print(f"{OK} {h}: API key from ${next(k for k in API_KEYS[h] if os.environ.get(k))}")
        return True
    if read_keys().get(name):
        print(f"{OK} {h}: API key saved in {KEYS_FILE}")
        return True
    if sys.stdin.isatty():
        try:
            val = getpass.getpass(f"  paste your {name} (input hidden, Enter to skip): ").strip()
        except EOFError:
            val = ""
        if val:
            keys = {**read_keys(), name: val}
            fd = os.open(KEYS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.writelines(f"{k}={v}\n" for k, v in keys.items())
            os.chmod(KEYS_FILE, 0o600)
            print(f"{OK} {h}: key saved to {KEYS_FILE} (readable only by you)")
            return True
    print(f"{BAD} {h}: API-key auth chosen but no key. Either export {name} in your shell, or run\n"
          f"      python3 {HERE}/setup.py --{h}-auth api   in your own terminal to enter it hidden")
    return False


def ping(harness, model=None):
    add, drop = auth_env({"harness": harness})
    env = {k: v for k, v in {**os.environ, **add}.items() if k not in drop}
    if harness == "claude":
        cmd = ["claude", "-p", "Reply with just: ok", "--no-session-persistence", "--output-format", "json"]
        cmd += ["--model", model] if model else []
    else:
        cmd = ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only", "Reply with just: ok"]
        cmd[2:2] = ["-m", model] if model else []
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL,
                           env=env, cwd=PB_HOME)
        out = (p.stdout + p.stderr).strip()
        if harness == "claude":
            try:
                d = json.loads(p.stdout.strip().splitlines()[-1])
                return not d.get("is_error"), d.get("result", "")[:200]
            except (ValueError, IndexError):
                return False, out[-200:]
        return p.returncode == 0, out[-200:]
    except Exception as e:
        return False, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-auth", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--claude-auth", choices=["plan", "api"], help="bill claude runs to your plan or an API key")
    ap.add_argument("--codex-auth", choices=["plan", "api"], help="bill codex runs to your plan or an API key")
    a = ap.parse_args()
    problems = 0

    print("1. Tools")
    if sys.version_info < (3, 10):
        print(f"{BAD} python {sys.version.split()[0]} — need 3.10+"); problems += 1
    else:
        print(f"{OK} python {sys.version.split()[0]}")
    print(f"{OK} git" if have("git") else f"{BAD} git missing — install Xcode CLT or git"); problems += not have("git")
    print(f"{OK} node {version('node')}" if have("node") else f"{WARN} node missing — JS tasks will fail; install Node 18+ if your work has JS")
    clis = [c for c in ("claude", "codex") if have(c)]
    for c in ("claude", "codex"):
        print(f"{OK} {c} {version(c)}" if c in clis else f"{WARN} {c} CLI not found (models from it can't be benchmarked)")
    if not clis:
        print(f"{BAD} need at least one agent CLI: Claude Code (`claude`) or Codex (`codex`)"); problems += 1
    host = host_agent()
    print(f"{OK} running inside {dict(claude='Claude Code', codex='Codex').get(host, 'a plain terminal')}"
          + (f": grading will use {host}" if host else ""))

    print("\n2. Logs")
    logs = {"claude": os.path.isdir(f"{HOME}/.claude/projects"), "codex": os.path.isdir(f"{HOME}/.codex/sessions")}
    for k, v in logs.items():
        print(f"{OK if v else WARN} {k} history {'found' if v else 'not found'}")
    try:
        keep = json.load(open(f"{HOME}/.claude/settings.json")).get("cleanupPeriodDays", 30)
    except (OSError, ValueError):
        keep = 30
    if logs["claude"] and keep < 90:
        print(f"{WARN} Claude Code deletes transcripts after {keep} days. The benchmark keeps everything it has"
              f" mined, but to keep more raw history set \"cleanupPeriodDays\": 365 in ~/.claude/settings.json")
    if not any(logs.values()):
        print(f"{BAD} no Claude Code or Codex history yet. Use an agent for a while first; the benchmark is built from it")
        problems += 1
    if problems:
        sys.exit(f"\n{problems} blocking problem(s) above. Fix them and re-run setup.py.")

    os.makedirs(f"{PB_HOME}/suite/tasks", exist_ok=True)
    print(f"\n3. Mining your history into {PB_HOME}/corpus …")
    subprocess.run([sys.executable, f"{HERE}/mine.py"], check=True, stdout=subprocess.DEVNULL)
    stats = json.load(open(f"{PB_HOME}/corpus/stats.json"))
    print(f"{OK} {stats['prompts']:,} prompts across {stats['sessions']:,} sessions")
    top = [c for c in stats["by_category"] if c not in ("followup", "other")][:4]
    print(f"{OK} you mostly do: {', '.join(top)}")

    print("\n4. Models")
    mpath = f"{PB_HOME}/models.json"
    if os.path.exists(mpath) and not a.force:
        cfg = json.load(open(mpath))
        print(f"{OK} keeping existing models.json ({len(cfg['models'])} models; --force to regenerate)")
    else:
        used = [(m, n) for m, n in stats["by_model"].items() if harness_for(m) in clis]
        models, seen = [], set()
        for mid, n in used:  # your most-used models first, max 2 per harness
            h = harness_for(mid)
            if sum(x["harness"] == h for x in models) < 2 and short(mid) not in seen:
                models.append({"name": short(mid), "harness": h, "model": mid}); seen.add(short(mid))
        if not models:  # fresh install: no model ids in logs yet
            models = [{"name": "default-" + c, "harness": c, "model": ""} for c in clis]
            print(f"{WARN} no model ids found in your logs. Fill in \"model\" in {mpath}")
        # grade with the agent the user is in; fall back to claude, then whatever is installed
        prefer = [h for h in (host_agent(), "claude", "codex") if h in clis]
        jm = next((m for h in prefer for m in models if m["harness"] == h), models[0])
        judge = {"harness": jm["harness"], "model": jm["model"]}
        cfg = {"judge": judge, "models": models}
        json.dump(cfg, open(mpath, "w"), indent=2)
        print(f"{OK} wrote models.json from your most-used models:")
        for m in models:
            print(f"      {m['name']:<16} {m['harness']:<7} {m['model']}")
        print(f"{OK} judge (grades rubric tasks; keep it fixed week to week): {judge['harness']} {judge['model']}")

    print("\n5. Billing: your plan or an API key?")
    auth, missing = dict(cfg.get("auth", {})), 0
    for h in clis:
        auth[h] = ask_auth(h, getattr(a, f"{h}_auth"), auth.get(h))
        if auth[h] == "plan":
            stray = [k for k in API_KEYS[h] if os.environ.get(k)]
            print(f"{OK} {h}: {PLAN[h]}" + (f" ({'/'.join(stray)} in your shell is ignored)" if stray else ""))
        else:
            missing += not ensure_key(h)
    cfg["auth"] = auth
    json.dump(cfg, open(mpath, "w"), indent=2)
    if missing:
        sys.exit("\nFix the missing key(s) above, then re-run setup.py.")

    if a.check_auth:
        print("\n6. Auth check (one tiny prompt per CLI)")
        for c in clis:
            m = next((x["model"] for x in cfg["models"] if x["harness"] == c and x["model"]), None)
            ok, msg = ping(c, m)
            print(f"{OK if ok else BAD} {c}{' ' + m if m else ''}: {'logged in' if ok else msg}")

    print(f"""
Setup done. Next: open Claude Code (or Codex) and say

    build my personal benchmark

The agent reads your mined prompts, designs ~12-20 tasks in your own voice, checks they're
fair, then runs your models and opens the dashboard. Day to day:

    "run my benchmark"                 run everything not run yet
    "add <new model> to my benchmark"  test a new release on your tasks
    "refresh my benchmark"             weekly: re-mine, adjust tasks, rerun
""")


if __name__ == "__main__":
    main()
