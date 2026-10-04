#!/usr/bin/env python3
"""Build the dashboard ($PB_HOME/report.html) + plain-text report.md, and snapshot scores to history.jsonl.

Only results matching each task's CURRENT hash count, so every model is scored on the same suite.
The dashboard is assets/dashboard.html with the data embedded as JSON: one offline file, no server.
Usage: python3 report.py [--open] [--no-history]
"""
import argparse, collections, json, os, subprocess, sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from run import PB_HOME, load_models, load_tasks  # noqa: E402

TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "assets", "dashboard.html")


def iso_week(d):
    y, w, _ = date.fromisoformat(d[:10]).isocalendar()
    return f"{y}-W{w:02d}"


def collect():
    tasks = load_tasks()
    models = load_models()["models"]
    table = {}  # model -> task_id -> result
    for m in models:
        for t in tasks:
            p = f"{PB_HOME}/results/{m['name']}/{t['id']}-{t['hash']}.json"
            if os.path.exists(p):
                table.setdefault(m["name"], {})[t["id"]] = json.load(open(p))
    return tasks, models, table


def score(tasks, res):
    """Weighted pass rate over graded results; the dashboard JS mirrors this."""
    w = {t["id"]: t.get("weight", 1) for t in tasks}
    graded = [r for r in res.values() if not r.get("ungraded")]
    if not graded:
        return None
    return round(100 * sum(w[r["task"]] * r["passed"] for r in graded) / sum(w[r["task"]] for r in graded), 1)


def daily_driver(models):
    """The configured model the user has actually used most, per the mined corpus."""
    try:
        by_model = json.load(open(f"{PB_HOME}/corpus/stats.json"))["by_model"]
    except (OSError, KeyError, ValueError):
        return None
    ranked = sorted(models, key=lambda m: -by_model.get(m["model"], 0))
    return ranked[0]["name"] if ranked and by_model.get(ranked[0]["model"]) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--no-history", action="store_true")
    a = ap.parse_args()
    tasks, models, table = collect()
    today = date.today().isoformat()
    scores = {n: s for n, res in table.items() if (s := score(tasks, res)) is not None}

    hist_path = f"{PB_HOME}/history.jsonl"
    if not a.no_history and scores:
        with open(hist_path, "a") as f:
            for n, s in scores.items():
                f.write(json.dumps({"date": today, "week": iso_week(today), "model": n, "score": s,
                                    "coverage": f"{len(table[n])}/{len(tasks)}", "n_tasks": len(tasks)}) + "\n")
    weekly = {}  # last snapshot per (model, week) wins
    for line in open(hist_path) if os.path.exists(hist_path) else []:
        h = json.loads(line)
        weekly[(h["model"], h.get("week") or iso_week(h["date"]))] = h["score"]

    shown = [m for m in models if m.get("active", True) or m["name"] in table]
    data = {
        "generated": date.today().strftime("%b %-d, %Y"),
        "daily_driver": daily_driver(shown),
        "corpus": (lambda s: {"prompts": s.get("prompts"), "sessions": s.get("sessions")})(
            json.load(open(f"{PB_HOME}/corpus/stats.json")) if os.path.exists(f"{PB_HOME}/corpus/stats.json") else {}),
        "categories": sorted({t.get("category") for t in tasks}),
        "tasks": [{k: t.get(k) for k in ("id", "title", "category", "weight", "grading", "prompt")} for t in tasks],
        "models": [{k: m.get(k) for k in ("name", "harness", "model", "active")} for m in shown],
        "results": {n: {tid: {"passed": r["passed"], "ungraded": r.get("ungraded", False),
                              "judge_score": r.get("judge_score"), "judge_reason": r.get("judge_reason"),
                              "check_log": r.get("check_log"), "final_message": r.get("final_message"),
                              "seconds": r.get("seconds"), "timed_out": r.get("timed_out"), "date": r.get("date", "")[:10],
                              "cost_usd": (r.get("usage") or {}).get("cost_usd"),
                              "tokens": (r.get("usage") or {}).get("total_tokens")}
                        for tid, r in res.items()} for n, res in table.items()},
        "history": [{"week": w, "model": n, "score": s} for (n, w), s in sorted(weekly.items(), key=lambda x: x[0][1])],
    }
    page = open(TEMPLATE).read().replace("/*__DATA__*/null/*__END__*/", json.dumps(data).replace("</", "<\\/"))
    open(f"{PB_HOME}/report.html", "w").write(page)

    # plain-text twin for terminals / diffs
    cats = data["categories"]
    rows = sorted(scores.items(), key=lambda x: -x[1])
    md = [f"# Personal benchmark — {today}", "", f"{len(tasks)} tasks across {len(cats)} categories.", "",
          "| # | Model | Score | Coverage | " + " | ".join(cats) + " |", "|---|---|---|---|" + "---|" * len(cats)]
    for i, (n, s) in enumerate(rows, 1):
        per = collections.defaultdict(list)
        for r in table[n].values():
            if not r.get("ungraded"):
                per[r["category"]].append(r["passed"])
        md.append(f"| {i} | {n} | **{s}** | {len(table[n])}/{len(tasks)} | "
                  + " | ".join(str(round(100 * sum(v) / len(v))) if (v := per.get(c)) else "–" for c in cats) + " |")
    open(f"{PB_HOME}/report.md", "w").write("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"\ndashboard -> {PB_HOME}/report.html")
    if a.open:
        subprocess.run(["open", f"{PB_HOME}/report.html"])


if __name__ == "__main__":
    main()
