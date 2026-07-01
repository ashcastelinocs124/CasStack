#!/usr/bin/env python3
"""Generate an HTML before/after view of the change just implemented,
with Approve / Deny buttons that resume the waiting Claude session.

Usage:
    generate_before_after.py [--base REF] [--timeout SECS] [--port N] [paths...]
    generate_before_after.py --static --out PATH [--base REF] [paths...]

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


def build_page(base, paths, cwd, with_buttons):
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

    if not changes:
        sys.exit("No changes found against %s" % base)

    differ = difflib.HtmlDiff(wrapcolumn=100)
    sections = []
    for status, old_path, new_path in changes:
        before = "" if status.startswith("A") else old_version(base, old_path, cwd)
        after = ""
        if not status.startswith("D") and os.path.isfile(os.path.join(cwd, new_path)):
            try:
                with open(os.path.join(cwd, new_path), encoding="utf-8") as f:
                    after = f.read()
            except UnicodeDecodeError:
                sections.append(
                    "<h2>%s</h2><p>(binary file, diff skipped)</p>"
                    % html.escape(new_path)
                )
                continue
        label = {"A": "added", "D": "deleted", "M": "modified"}.get(status[0], status)
        table = differ.make_table(
            before.splitlines(), after.splitlines(),
            "before", "after", context=True, numlines=3,
        )
        sections.append(
            "<h2>%s <small>(%s)</small></h2>%s"
            % (html.escape(new_path), label, table)
        )

    buttons = ""
    if with_buttons:
        buttons = """
<div id="bar">
  <span>Does this change look right?</span>
  <button class="ok" onclick="send('approve')">Approve</button>
  <button class="no" onclick="send('deny')">Deny</button>
</div>
<script>
function send(d) {
  fetch('/decision', {method: 'POST', body: d}).then(function () {
    document.body.innerHTML = '<h1>' + (d === 'approve' ? 'Approved' : 'Denied') +
      '</h1><p>Back to your Claude session &mdash; you can close this tab.</p>';
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
#bar {{ position: fixed; bottom: 0; left: 0; right: 0; background: #fff;
       border-top: 1px solid #ccc; padding: 1rem 2rem; display: flex;
       gap: 1rem; align-items: center; }}
#bar button {{ font-size: 15px; padding: .5rem 1.5rem; border-radius: 6px;
              border: none; cursor: pointer; color: #fff; }}
#bar .ok {{ background: #2da44e; }}
#bar .no {{ background: #cf222e; }}
</style></head><body>
<h1>Before / After</h1>
<p>Base: <code>{base}</code> &mdash; {n} file(s) changed</p>
{body}
{buttons}
</body></html>""".format(base=html.escape(base), n=len(changes),
                         body="\n".join(sections), buttons=buttons)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--static", action="store_true",
                    help="just write the page, no server, no buttons")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--timeout", type=int, default=570)
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("paths", nargs="*")
    args = ap.parse_args()

    cwd = os.getcwd()
    page = build_page(args.base, args.paths, cwd, with_buttons=not args.static)

    if args.static:
        out = args.out or os.path.join(tempfile.gettempdir(), "before-after.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(page)
        print(out)
        if not args.no_open:
            webbrowser.open("file://" + os.path.abspath(out))
        return

    decision = {"value": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = page.encode("utf-8") if self.path == "/" else b"not found"
            self.send_response(200 if self.path == "/" else 404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            verdict = self.rfile.read(n).decode("utf-8", "replace").strip()
            if self.path == "/decision" and verdict in ("approve", "deny"):
                decision["value"] = verdict
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    server.timeout = 1  # poll interval for handle_request
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    print("Review at %s — waiting for Approve/Deny (timeout %ss)"
          % (url, args.timeout), flush=True)
    if not args.no_open:
        webbrowser.open(url)

    deadline = time.time() + args.timeout
    while decision["value"] is None and time.time() < deadline:
        server.handle_request()
    server.server_close()

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
