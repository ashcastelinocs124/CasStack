#!/usr/bin/env python3
"""Generate an HTML before/after view of the change just implemented.

Usage:
    generate_before_after.py [--base REF] [--out PATH] [--no-open] [paths...]

Defaults: --base HEAD (i.e. uncommitted changes in the working tree);
if the change was already committed, pass --base HEAD~1.
Writes one HTML page with a side-by-side before/after table per changed file.
"""
from __future__ import annotations

import argparse
import difflib
import html
import os
import subprocess
import sys
import tempfile
import webbrowser


def git(args, cwd):
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True
    )


def old_version(base, path, cwd):
    r = git(["show", "%s:%s" % (base, path)], cwd)
    return r.stdout if r.returncode == 0 else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("paths", nargs="*")
    args = ap.parse_args()

    cwd = os.getcwd()
    r = git(["diff", "--name-status", args.base, "--"] + args.paths, cwd)
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
        sys.exit("No changes found against %s" % args.base)

    differ = difflib.HtmlDiff(wrapcolumn=100)
    sections = []
    for status, old_path, new_path in changes:
        before = "" if status.startswith("A") else old_version(args.base, old_path, cwd)
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

    page = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Before / After</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 2rem; }}
h2 {{ border-bottom: 1px solid #ddd; padding-bottom: .3rem; margin-top: 2.5rem; }}
table.diff {{ font-family: ui-monospace, monospace; font-size: 12px; border-collapse: collapse; width: 100%; }}
table.diff td, table.diff th {{ padding: 1px 6px; vertical-align: top; }}
.diff_header {{ background: #f3f3f3; color: #888; }}
.diff_add {{ background: #d8f5d8; }}
.diff_chg {{ background: #fff3c2; }}
.diff_sub {{ background: #ffd9d9; }}
</style></head><body>
<h1>Before / After</h1>
<p>Base: <code>{base}</code> &mdash; {n} file(s) changed</p>
{body}
</body></html>""".format(base=html.escape(args.base), n=len(changes),
                         body="\n".join(sections))

    out = args.out or os.path.join(tempfile.gettempdir(), "before-after.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(out)
    if not args.no_open:
        webbrowser.open("file://" + os.path.abspath(out))


if __name__ == "__main__":
    main()
