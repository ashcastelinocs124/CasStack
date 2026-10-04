#!/usr/bin/env python3
"""Mine local coding-agent transcripts into a prompt corpus + stats.

Sources:
  Claude Code: ~/.claude/projects/*/*.jsonl
  Codex:       ~/.codex/sessions/**/*.jsonl, ~/.codex/archived_sessions/*.jsonl

Writes (under $PB_HOME, default ~/.personal-benchmark):
  corpus/prompts.jsonl  one human prompt per line, secrets redacted
  corpus/stats.json     category / project / model / correction-rate breakdown

Usage: python3 mine.py [--since YYYY-MM-DD] [--self-test]
"""
import argparse, collections, glob, json, os, re, sys
from datetime import datetime, timezone

PB_HOME = os.path.expanduser(os.environ.get("PB_HOME", "~/.personal-benchmark"))
HOME = os.path.expanduser("~")

SECRET_RES = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"\b(sk-(?:ant-|proj-)?[A-Za-z0-9_\-]{16,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}"
               r"|github_pat_[A-Za-z0-9_]{20,}|xox[abpr]-[A-Za-z0-9\-]{10,}|AKIA[0-9A-Z]{16}"
               r"|AIza[0-9A-Za-z_\-]{30,}|eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]+)"),
    re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{16,}"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    re.compile(r"\b[A-Fa-f0-9]{40,}\b"),
]

# note: keyword heuristic, only used for weighting/stats; the agent does the real clustering.
CATEGORIES = [
    ("git-ops", r"\b(push|pull|commit|merge|rebase|branch|pr\b|pull request|cherry)"),
    ("debug-fix", r"\b(bug|fix|error|broken|crash|fail|failing|not working|doesn'?t work|issue|traceback|exception)"),
    ("ui-frontend", r"\b(ui|css|button|page|layout|style|frontend|component|design|mockup|tailwind|react)"),
    ("deploy-config", r"\b(deploy|azure|docker|ci\b|env|config|settings|install|setup|hook|cron|launchd)"),
    ("data-script", r"\b(csv|excel|xlsx|json|data|scrape|parse|sql|query|database|db\b|chart|plot)"),
    ("refactor", r"\b(refactor|clean ?up|simplify|rename|restructure|reorganize|dedupe)"),
    ("review-explain", r"\b(explain|what (is|does|are)|why|how (is|does|do)|review|analy[sz]e|summar|understand|look at|status|diff)"),
    ("edit-tweak", r"\b(remove|change|update|mention|rename|move|replace|delete|tweak|adjust|instead)"),
    ("agent-llm", r"\b(agent|llm|prompt|model|claude|openai|gpt|skill|mcp|rag|embedding)"),
    ("feature-build", r"\b(add|build|create|make|implement|new feature|support|wire up)"),
]
CORRECTION = re.compile(
    r"^\s*(no\b|nope|wrong|that'?s not|not what|didn'?t|doesn'?t|still\b|revert|undo|why did you|"
    r"stop\b|you (broke|forgot|missed)|it'?s broken|try again|that broke)", re.I)
NOISE = re.compile(r"^\s*(<(system-reminder|local-command|command-message|task-notification|"
                   r"user_instructions|environment_context|recommended_plugins|app-context|"
                   r"turn_aborted|bash-)|Caveat:|\[Request interrupted|Automation: )")


def redact(t):
    for r in SECRET_RES:
        t = r.sub("[REDACTED]", t)
    return t.replace(HOME, "~")


HARNESS_CMDS = re.compile(r"^/(clear|login|logout|model|exit|quit|resume|compact|config|status|cost|help|"
                          r"init|memory|permissions|fast|effort|doctor|mcp|plugin|ide|theme|vim|rewind|context)\b")


def categorize(text):
    low = text.lower()
    if len(low.split()) <= 3 and not low.startswith("/"):
        return ["followup"]  # "yes", "push it", "looks good": steering, not a task
    return [c for c, rx in CATEGORIES if re.search(rx, low)] or ["other"]


def clean(text):
    """Return user-meaningful text, or None for harness noise."""
    if not text:
        return None
    m = re.search(r"<command-name>(.*?)</command-name>", text, re.S)
    if m:  # slash command invocation -> "/name args"
        args = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
        cmd = f"{m.group(1).strip()} {args.group(1).strip() if args else ''}".strip()
        return None if HARNESS_CMDS.match(cmd) else cmd
    if NOISE.match(text) or HARNESS_CMDS.match(text.strip()):
        return None
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S).strip()
    return text or None


def claude_prompts():
    for path in glob.glob(f"{HOME}/.claude/projects/*/*.jsonl"):
        project = os.path.basename(os.path.dirname(path))
        recs, model = [], None
        try:
            fh = open(path, errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"type":"assistant"' in line and model is None:
                    m = re.search(r'"model":"([^"]+)"', line)
                    model = m and m.group(1)
                if '"type":"user"' not in line and '"type":"assistant"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("isSidechain"):
                    continue
                if d.get("type") == "assistant":
                    if recs:
                        recs[-1]["tool_calls"] += sum(
                            1 for b in d.get("message", {}).get("content", []) or []
                            if isinstance(b, dict) and b.get("type") == "tool_use")
                    continue
                if d.get("isMeta") or (d.get("origin") or {}).get("kind", "human") != "human":
                    continue
                c = d.get("message", {}).get("content")
                if isinstance(c, list):
                    if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
                        continue
                    c = "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                text = clean(c if isinstance(c, str) else "")
                if text:
                    recs.append({"source": "claude", "session": d.get("sessionId"), "ts": d.get("timestamp"),
                                 "cwd": (d.get("cwd") or "").replace(HOME, "~"), "project": project,
                                 "text": text, "tool_calls": 0})
        for r in recs:
            r["model"] = model
        yield from recs


def codex_prompts():
    paths = glob.glob(f"{HOME}/.codex/sessions/**/*.jsonl", recursive=True)
    paths += glob.glob(f"{HOME}/.codex/archived_sessions/*.jsonl")
    for path in paths:
        recs, cwd, model, sid = [], "", None, None
        try:
            fh = open(path, errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                # cheap substring filters before json parsing; codex lines can be MBs
                if '"session_meta"' in line[:200] or '"turn_context"' in line[:200]:
                    try:
                        p = json.loads(line).get("payload", {})
                    except ValueError:
                        continue
                    cwd = p.get("cwd", cwd)
                    sid = p.get("session_id", p.get("id", sid))
                    model = p.get("model", model)
                elif '"UserMessage"' in line:
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    item = d.get("payload", {}).get("item", {})
                    if item.get("type") != "UserMessage":
                        continue
                    text = clean("\n".join(c.get("text", "") for c in item.get("content", []) if isinstance(c, dict)))
                    if text:
                        recs.append({"source": "codex", "session": sid, "ts": d.get("timestamp"),
                                     "cwd": cwd.replace(HOME, "~"),
                                     "project": os.path.basename(cwd.rstrip("/")) or "~",
                                     "text": text, "tool_calls": 0})
                elif '"custom_tool_call"' in line[:300] or '"function_call"' in line[:300]:
                    if recs and '_output"' not in line[:300]:
                        recs[-1]["tool_calls"] += 1
        for r in recs:
            r["model"] = model
        yield from recs


def build(since=None):
    os.makedirs(f"{PB_HOME}/corpus", exist_ok=True)
    bench_tmp = f"{PB_HOME}/runs"
    rows = [r for r in list(claude_prompts()) + list(codex_prompts())
            if not r["cwd"].startswith(bench_tmp.replace(HOME, "~")) and (not since or (r["ts"] or "") >= since)]
    for r in rows:  # same repo shows up as "-Users-you-foo" (claude) and "foo" (codex)
        r["project"] = os.path.basename(r["cwd"].rstrip("/")) or "~"
    rows.sort(key=lambda r: (r["session"] or "", r["ts"] or ""))
    # follow-up correction = next prompt in same session looks like pushback
    for a, b in zip(rows, rows[1:] + [None]):
        a["corrected"] = bool(b and b["session"] == a["session"] and CORRECTION.match(b["text"]))
    # Claude Code deletes transcripts after cleanupPeriodDays (default 30), so keep what was
    # mined before: the corpus only grows. Fresh rows come first and win on duplicates.
    old = []
    if os.path.exists(f"{PB_HOME}/corpus/prompts.jsonl"):
        with open(f"{PB_HOME}/corpus/prompts.jsonl") as f:
            old = [json.loads(l) for l in f if l.strip()]
    old = [o for o in old if not since or (o.get("ts") or "") >= since]
    seen, out = set(), []
    for r in rows + old:
        r["text"] = redact(r["text"])[:4000]
        key = (r["source"], r["session"], r["ts"], r["text"][:200])
        if key in seen:
            continue
        seen.add(key)
        r["categories"] = categorize(r["text"])
        r["words"] = len(r["text"].split())
        out.append(r)
    with open(f"{PB_HOME}/corpus/prompts.jsonl", "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")

    cat, cat_corr, proj, src, models, months = (collections.Counter() for _ in range(6))
    for r in out:
        for c in r["categories"]:
            cat[c] += 1
            cat_corr[c] += r["corrected"]
        proj[r["project"]] += 1
        src[r["source"]] += 1
        models[r["model"] or "?"] += 1
        months[(r["ts"] or "")[:7]] += 1
    substantive = [r for r in out if r["words"] >= 6]
    stats = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prompts": len(out), "substantive_prompts": len(substantive),
        "sessions": len({r["session"] for r in out}),
        "by_source": dict(src), "by_model": dict(models.most_common()),
        "by_month": dict(sorted(months.items())),
        "by_category": {c: {"count": n, "share": round(n / max(1, len(out)), 3),
                            "correction_rate": round(cat_corr[c] / n, 3)} for c, n in cat.most_common()},
        "top_projects": dict(proj.most_common(15)),
        "median_words": sorted(r["words"] for r in out)[len(out) // 2] if out else 0,
    }
    with open(f"{PB_HOME}/corpus/stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    return stats


def self_test():
    assert redact("key sk-ant-abcdefghijklmnopqrstuvwx ok") == "key [REDACTED] ok"
    assert "[REDACTED]" in redact("API_KEY=hunter2")
    assert clean("<system-reminder>x</system-reminder>") is None
    assert clean("<command-name>/gitpush</command-name>\n<command-args>main</command-args>") == "/gitpush main"
    assert clean("fix the login bug") == "fix the login bug"
    assert "git-ops" in categorize("commit and push the changes")
    assert categorize("looks good") == ["followup"]
    assert clean("<command-name>/clear</command-name>") is None
    assert "debug-fix" in categorize("the build is failing with a TypeError")
    assert CORRECTION.match("no that's wrong") and not CORRECTION.match("now add tests")
    print("self-test ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--since")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        sys.exit()
    s = build(a.since)
    print(json.dumps({k: s[k] for k in ("prompts", "substantive_prompts", "sessions", "by_source", "by_category")}, indent=1))
    print(f"corpus -> {PB_HOME}/corpus/")
