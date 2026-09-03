#!/usr/bin/env python3
"""Show application screenshots side-by-side with Approve / Deny buttons.

Usage:
    generate_visual_before_after.py --pair BEFORE AFTER LABEL [--pair BEFORE AFTER LABEL ...]
    generate_visual_before_after.py --static --out PATH --pair BEFORE AFTER LABEL [...]

The caller is responsible for capturing screenshots before and after the change.
This script only renders those screenshots in a review page and waits for the
user's decision.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import os
import sys
import tempfile
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer


def data_uri(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return "data:%s;base64,%s" % (mime, encoded)


def live_section(live: list[list[str]] | None, with_buttons: bool) -> str:
    """A panel that opens the running app at the changed feature.

    Screenshots answer "does it look right". They cannot answer "does it feel right" —
    whether a control responds, whether the flow is obvious, whether the timing is
    tolerable. So when the app is running, offer the real thing, deep-linked to the route
    the change touched rather than the home page: a reviewer sent to the front door has to
    go find the feature, and usually will not.
    """
    if not live:
        return ""
    cards = []
    for url, label in live:
        esc_url = html.escape(url, quote=True)
        cards.append(
            '<div class="livecard">'
            '<div class="livelabel">{label}</div>'
            '<a class="livebtn" href="{url}" target="_blank" rel="noopener">Open it &rarr;</a>'
            '<div class="liveurl"><code>{url}</code></div>'
            '<iframe class="liveframe" src="{url}" loading="lazy"></iframe>'
            '</div>'.format(label=html.escape(label), url=esc_url)
        )
    box = ""
    if with_buttons:
        box = ('<textarea class="cmt" data-on="live" rows="2"'
               ' placeholder="How did it feel to use? (optional)"></textarea>')
    return ('<section class="pair"><h2>Try it yourself</h2>'
            '<p class="livenote">The running app, opened at the part that changed. '
            'If the frame is blank, use &ldquo;Open it&rdquo; &mdash; some pages refuse to be embedded.</p>'
            + "".join(cards) + box + '</section>')


def build_page(pairs: list[list[str]], with_buttons: bool, live=None) -> str:
    if not pairs:
        sys.exit("At least one --pair BEFORE AFTER LABEL is required")

    sections = []
    for before, after, label in pairs:
        if not os.path.isfile(before):
            sys.exit("Missing before screenshot: %s" % before)
        if not os.path.isfile(after):
            sys.exit("Missing after screenshot: %s" % after)
        comment_box = ""
        if with_buttons:
            comment_box = (
                '<textarea class="cmt" data-on="{label}" rows="2"'
                ' placeholder="Comments on this screen (optional) — sent to Claude with your decision"></textarea>'
            ).format(label=html.escape(label, quote=True))
        sections.append(
            """
<section class="pair">
  <h2>{label}</h2>
  <div class="grid">
    <figure><figcaption>Before</figcaption><img src="{before}" alt="Before: {label}"></figure>
    <figure><figcaption>After</figcaption><img src="{after}" alt="After: {label}"></figure>
  </div>
  {comment_box}
</section>
""".format(
                label=html.escape(label),
                before=data_uri(before),
                after=data_uri(after),
                comment_box=comment_box,
            )
        )

    buttons = ""
    if with_buttons:
        buttons = """
<div id="bar">
  <span>Does the application change look right? Comments (per screen or below) go back to Claude with your click.</span>
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
<html><head><meta charset="utf-8"><title>Application Before / After</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; margin-bottom: 6rem; background: #f6f7f9; color: #111; }}
h1 {{ margin-bottom: .25rem; }}
.pair {{ margin-top: 2rem; }}
.grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; align-items: start; }}
figure {{ margin: 0; background: #fff; border: 1px solid #d0d7de; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,.06); }}
figcaption {{ padding: .75rem 1rem; font-weight: 700; border-bottom: 1px solid #d0d7de; background: #fff; }}
img {{ display: block; width: 100%; height: auto; }}
.livenote {{ color: #57606a; font-size: 13px; margin: .2rem 0 .8rem; }}
.livecard {{ border: 1px solid #d0d7de; border-radius: 10px; padding: .8rem 1rem; margin-bottom: .8rem; }}
.livelabel {{ font-weight: 600; margin-bottom: .5rem; }}
.livebtn {{ display: inline-block; background: #FF5F05; color: #fff; text-decoration: none;
            border-radius: 999px; padding: .4rem 1rem; font-weight: 600; font-size: 13px; }}
.liveurl {{ margin: .5rem 0; font-size: 12px; color: #57606a; }}
.liveframe {{ width: 100%; height: 460px; border: 1px solid #d0d7de; border-radius: 8px; background: #fff; }}
textarea.cmt {{ display: block; width: 100%; box-sizing: border-box; margin-top: .6rem; padding: .5rem .75rem; font: inherit; font-size: 13px; border: 1px solid #d0d7de; border-radius: 8px; resize: vertical; }}
#bar {{ position: fixed; bottom: 0; left: 0; right: 0; background: #fff; border-top: 1px solid #ccc; padding: 1rem 2rem; display: flex; gap: 1rem; align-items: center; z-index: 10; }}
#bar textarea.cmt {{ flex: 1; margin-top: 0; }}
#bar button {{ font-size: 15px; padding: .5rem 1.5rem; border-radius: 6px; border: none; cursor: pointer; color: #fff; }}
#bar .ok {{ background: #2da44e; }}
#bar .no {{ background: #cf222e; }}
@media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
</style></head><body>
<h1>Application Before / After</h1>
<p>Review the actual app screenshots, not the code diff.</p>
{body}
{buttons}
</body></html>""".format(body="\n".join(sections) + live_section(live, with_buttons), buttons=buttons)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", action="append", nargs=3, metavar=("BEFORE", "AFTER", "LABEL"))
    ap.add_argument("--live", action="append", nargs=2, metavar=("URL", "LABEL"),
                    help="running app URL, deep-linked to the changed feature; repeatable")
    ap.add_argument("--static", action="store_true", help="write the page only, no server")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--port", type=int, default=0)
    args = ap.parse_args()

    page = build_page(args.pair or [], with_buttons=not args.static, live=args.live)

    if args.static:
        out = args.out or os.path.join(tempfile.gettempdir(), "app-before-after.html")
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
    server.timeout = 1
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    print("Review at %s - waiting for Approve/Deny (timeout %ss; verdict also saved to %s)"
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
    if decision["value"] == "deny":
        print("DENIED")
        sys.exit(1)
    print("TIMEOUT")
    sys.exit(2)


if __name__ == "__main__":
    main()
