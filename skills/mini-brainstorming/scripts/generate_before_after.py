#!/usr/bin/env python3
"""Generate an HTML before/after view of the change just implemented,
with Approve / Deny buttons that resume the waiting Claude session.

Usage:
    generate_before_after.py [--summary FILE] [--base REF] [--timeout SECS] [--port N] [paths...]
    generate_before_after.py --static --out PATH [--base REF] [paths...]

The page leads with a HUMAN explanation of the change, not code. Pass
--summary a JSON file (written by the calling session) shaped like:

    {"title": "...", "overview": "plain-language paragraph on the whole change",
     "changes": [{"file": "path", "what": "...", "why": "...",
                  "before": "behavior before, in plain words",
                  "after": "behavior now, in plain words",
                  "before_diagram": "flowchart LR\\n  a[...] --> b[...]",
                  "after_diagram": "flowchart LR\\n  a[...] --> c[...]"}]}

Each summarized file renders as a card: Before ➜ After panels showing the
mermaid diagrams (rendered via CDN; text captions beneath), the Why, and the
raw code diff collapsed behind a "Show code" toggle. Files without a
summary entry fall back to the open code diff. Without --summary the whole
page is the old code-diff view.

Default mode serves the page on localhost, opens the browser, and BLOCKS
until the user clicks Approve or Deny (or the timeout passes), then prints
the verdict and exits: 0 = APPROVED, 1 = DENIED, 2 = TIMEOUT. Run it in the
foreground and read the exit code / last line to continue the session.
--static skips the server and just writes the page (headless fallback).
"""
from __future__ import annotations

import argparse
import difflib
import html
import json
import os
import subprocess
import sys
import tempfile
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer


def git(args, cwd):
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True
    )


def old_version(base, path, cwd):
    r = git(["show", "%s:%s" % (base, path)], cwd)
    return r.stdout if r.returncode == 0 else ""


def summary_card(entry):
    """Visual card: Before ➜ After diagram panels, text as captions."""
    panels = []
    for key, cls, heading in (("before", "was", "Before"), ("after", "now", "After")):
        diagram, caption = entry.get(key + "_diagram"), entry.get(key)
        if not (diagram or caption):
            continue
        inner = "<h3>%s</h3>" % heading
        if diagram:
            inner += '<pre class="mermaid">%s</pre>' % html.escape(diagram)
        if caption:
            inner += '<p class="caption">%s</p>' % html.escape(caption)
        panels.append('<div class="panel %s">%s</div>' % (cls, inner))
    parts = ['<div class="card">']
    if entry.get("what"):
        parts.append('<p class="what">%s</p>' % html.escape(entry["what"]))
    if panels:
        parts.append('<div class="panels">%s</div>'
                     % '<div class="arrow">&#10132;</div>'.join(panels))
    if entry.get("why"):
        parts.append('<p class="why"><strong>Why:</strong> %s</p>'
                     % html.escape(entry["why"]))
    parts.append("</div>")
    return "".join(parts)


def comment_box(on):
    """Per-card comment box; contents ride back with the Approve/Deny click."""
    return (
        '<textarea class="cmt" data-on="%s" rows="2"'
        ' placeholder="Comments on this change (optional) — sent to Claude with your decision"></textarea>'
    ) % html.escape(on, quote=True)


def build_page(base, paths, cwd, with_buttons, summary=None):
    r = git(["diff", "--name-status", base, "--"] + paths, cwd)
    if r.returncode != 0:
        sys.exit("git diff failed: %s" % r.stderr.strip())

    changes = []
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        status = parts[0]
        # renames (R100 old new) report two paths; diff old name vs new name
        old_path = parts[1]
        new_path = parts[-1]
        changes.append((status, old_path, new_path))

    # untracked files are part of the change too — treat as added
    r = git(["ls-files", "--others", "--exclude-standard", "--"] + paths, cwd)
    for p in r.stdout.splitlines():
        changes.append(("A", p, p))

    if not changes:
        sys.exit("No changes found against %s" % base)

    by_file = {c.get("file"): c for c in (summary or {}).get("changes", [])}

    differ = difflib.HtmlDiff(wrapcolumn=100)
    sections = []
    for status, old_path, new_path in changes:
        entry = by_file.pop(new_path, None) or by_file.pop(old_path, None)
        before = "" if status.startswith("A") else old_version(base, old_path, cwd)
        after = ""
        is_binary = False
        if not status.startswith("D") and os.path.isfile(os.path.join(cwd, new_path)):
            try:
                with open(os.path.join(cwd, new_path), encoding="utf-8") as f:
                    after = f.read()
            except UnicodeDecodeError:
                is_binary = True
        if is_binary:
            table = "<p>(binary file, diff skipped)</p>"
        else:
            table = differ.make_table(
                before.splitlines(), after.splitlines(),
                "before", "after", context=True, numlines=3,
            )
        label = {"A": "added", "D": "deleted", "M": "modified"}.get(status[0], status)
        # summarized file: human card first, code collapsed; otherwise open code
        if entry:
            body = summary_card(entry) + (
                "<details><summary>Show code</summary>%s</details>" % table)
        else:
            body = table
        if with_buttons:
            body += comment_box(new_path)
        sections.append(
            "<h2>%s <small>(%s)</small></h2>%s"
            % (html.escape(new_path), label, body)
        )

    # summary entries whose file didn't show up in the diff — still explain them
    for entry in by_file.values():
        body = summary_card(entry)
        if with_buttons:
            body += comment_box(entry.get("file", "?"))
        sections.append(
            "<h2>%s <small>(no code diff found)</small></h2>%s"
            % (html.escape(entry.get("file", "?")), body)
        )

    intro = ""
    if summary:
        if summary.get("title"):
            intro += "<h1>%s</h1>" % html.escape(summary["title"])
        if summary.get("overview"):
            intro += '<p class="overview">%s</p>' % html.escape(summary["overview"])
        if summary.get("diagram"):
            intro += '<pre class="mermaid">%s</pre>' % html.escape(summary["diagram"])
            if with_buttons:
                intro += comment_box("overall diagram")
    if not intro:
        intro = "<h1>Before / After</h1>"

    buttons = ""
    if with_buttons:
        buttons = """
<div id="bar">
  <span>Does this change look right? Comments (per card or here) go back to Claude with your click.</span>
  <textarea id="general-cmt" class="cmt" data-on="general" rows="1" placeholder="Overall comments (optional)"></textarea>
  <button class="ok" onclick="send('approve')">Approve</button>
  <button class="no" onclick="send('deny')">Deny</button>
</div>
<script>
function send(d) {
  var comments = [];
  document.querySelectorAll('textarea.cmt').forEach(function (t) {
    if (t.value.trim()) comments.push({on: t.getAttribute('data-on'), text: t.value.trim()});
  });
  fetch('/decision', {method: 'POST', body: JSON.stringify({decision: d, comments: comments})}).then(function () {
    document.body.innerHTML = '<h1>' + (d === 'approve' ? 'Approved' : 'Denied') +
      '</h1><p>' + (comments.length ? 'Your ' + comments.length + ' comment(s) were sent to Claude. ' : '') +
      'Back to your Claude session &mdash; you can close this tab.</p>';
  });
}
</script>"""

    return """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Before / After</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 2rem; margin-bottom: 6rem; }}
h2 {{ border-bottom: 1px solid #ddd; padding-bottom: .3rem; margin-top: 2.5rem; }}
table.diff {{ font-family: ui-monospace, monospace; font-size: 12px; border-collapse: collapse; width: 100%; }}
table.diff td, table.diff th {{ padding: 1px 6px; vertical-align: top; }}
.diff_header {{ background: #f3f3f3; color: #888; }}
.diff_add {{ background: #d8f5d8; }}
.diff_chg {{ background: #fff3c2; }}
.diff_sub {{ background: #ffd9d9; }}
.overview {{ font-size: 16px; max-width: 48rem; }}
.card {{ margin: 1rem 0; }}
.card .what {{ font-size: 15px; max-width: 48rem; }}
.panels {{ display: flex; gap: .5rem; flex-wrap: wrap; align-items: stretch; }}
.panel {{ flex: 1 1 18rem; border-radius: 8px; padding: .2rem 1rem .6rem; }}
.panel h3 {{ margin: .5rem 0 .2rem; font-size: 13px; text-transform: uppercase; color: #666; }}
.panel.was {{ background: #fff0f0; border: 1px solid #ffd9d9; }}
.panel.now {{ background: #effaef; border: 1px solid #cdeccd; }}
.arrow {{ align-self: center; font-size: 30px; color: #888; padding: 0 .2rem; }}
pre.mermaid {{ background: #fff; border-radius: 6px; padding: .5rem; margin: .4rem 0;
              text-align: center; }}
/* CDN unreachable: mermaid source degrades to small monospace instead of rendering */
pre.mermaid:not([data-processed]) {{ font-family: ui-monospace, monospace;
                                    font-size: 11px; color: #777; text-align: left; }}
.caption {{ font-size: 13px; color: #444; margin: .3rem 0 0; }}
.why {{ color: #444; max-width: 48rem; }}
details {{ margin-top: .8rem; }}
details summary {{ cursor: pointer; color: #0969da; font-size: 13px; }}
textarea.cmt {{ display: block; width: 100%; box-sizing: border-box; margin-top: .6rem;
               padding: .5rem .75rem; font: inherit; font-size: 13px;
               border: 1px solid #d0d7de; border-radius: 8px; resize: vertical; }}
#bar textarea.cmt {{ flex: 1; margin-top: 0; }}
#bar {{ position: fixed; bottom: 0; left: 0; right: 0; background: #fff;
       border-top: 1px solid #ccc; padding: 1rem 2rem; display: flex;
       gap: 1rem; align-items: center; }}
#bar button {{ font-size: 15px; padding: .5rem 1.5rem; border-radius: 6px;
              border: none; cursor: pointer; color: #fff; }}
#bar .ok {{ background: #2da44e; }}
#bar .no {{ background: #cf222e; }}
</style></head><body>
{intro}
<p>Base: <code>{base}</code> &mdash; {n} file(s) changed</p>
{body}
{buttons}
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<script>if (window.mermaid) mermaid.initialize({{startOnLoad: true, theme: 'neutral'}});</script>
</body></html>""".format(intro=intro, base=html.escape(base), n=len(changes),
                         body="\n".join(sections), buttons=buttons)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--summary", default=None,
                    help="JSON file with plain-language explanations (see module docstring)")
    ap.add_argument("--static", action="store_true",
                    help="just write the page, no server, no buttons")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("paths", nargs="*")
    args = ap.parse_args()

    summary = None
    if args.summary:
        with open(args.summary, encoding="utf-8") as f:
            summary = json.load(f)

    cwd = os.getcwd()
    page = build_page(args.base, args.paths, cwd,
                      with_buttons=not args.static, summary=summary)

    if args.static:
        out = args.out or os.path.join(tempfile.gettempdir(), "before-after.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(page)
        print(out)
        if not args.no_open:
            webbrowser.open("file://" + os.path.abspath(out))
        return

    decision = {"value": None, "comments": []}
    # Persist the verdict the instant it's clicked, so a click is never lost — even if this process
    # later exits on timeout, the decision survives in this file and can be recovered.
    verdict_path = os.path.join(tempfile.gettempdir(), "mini-review-verdict.json")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = page.encode("utf-8") if self.path == "/" else b"not found"
            self.send_response(200 if self.path == "/" else 404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n).decode("utf-8", "replace").strip()
            # JSON {decision, comments} from the current page; bare "approve"/"deny" kept for old tabs
            verdict, comments = raw, []
            try:
                payload = json.loads(raw)
                verdict = payload.get("decision")
                comments = payload.get("comments") or []
            except ValueError:
                pass
            if self.path == "/decision" and verdict in ("approve", "deny"):
                decision["value"] = verdict
                decision["comments"] = comments
                try:  # durable record so a click is recoverable even after this process exits
                    with open(verdict_path, "w") as vf:
                        json.dump({"decision": verdict, "comments": comments}, vf)
                except OSError:
                    pass
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):
            pass

    try:  # drop any stale verdict from a previous run so it can't be mistaken for this one
        os.remove(verdict_path)
    except OSError:
        pass
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    server.timeout = 1  # poll interval for handle_request
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    print("Review at %s — waiting for Approve/Deny (timeout %ss; verdict also saved to %s)"
          % (url, args.timeout, verdict_path), flush=True)
    if not args.no_open:
        webbrowser.open(url)

    deadline = time.time() + args.timeout
    while decision["value"] is None and time.time() < deadline:
        server.handle_request()
    server.server_close()

    # Comments print BEFORE the verdict so the verdict stays the last line (session contract).
    if decision["comments"]:
        print("COMMENTS:")
        for c in decision["comments"]:
            print("- [%s] %s" % (c.get("on", "general"), c.get("text", "")))
    if decision["value"] == "approve":
        print("APPROVED")
        sys.exit(0)
    elif decision["value"] == "deny":
        print("DENIED")
        sys.exit(1)
    else:
        print("TIMEOUT")
        sys.exit(2)


if __name__ == "__main__":
    main()
