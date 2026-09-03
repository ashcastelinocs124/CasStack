#!/usr/bin/env python3
"""Serve a visual review page for a PLAN before the user approves it.

Usage:
    generate_plan_review.py --plan plan.json [--plan-doc design.md]
                            [--model ID] [--timeout SECS] [--port N]
    generate_plan_review.py --plan plan.json --static --out PATH
    generate_plan_review.py --selftest

The page shows, for a plan that has NOT been built yet:
  * a Before -> After pair of mermaid diagrams (how the system behaves today
    vs. how it will behave once the plan ships),
  * the product changes (what a user will see or do differently),
  * the database changes (tables, columns, migrations, backfills),
  * the ordered build steps and any open questions,
  * a live chatbot the reviewer can interrogate the plan with, and
  * Approve / Deny buttons plus comment boxes.

plan.json shape (every field optional except title):

    {"title": "...",
     "overview": "1-2 plain-language sentences on the whole plan",
     "ui_mockup_html": "path/to/mock.html — REQUIRED for UI-visible changes: a static HTML mock of the proposed UI, approved before any code is written",
     "before": "how it behaves today, one line",
     "after": "how it behaves once this ships, one line",
     "before_diagram": "flowchart TD\\n  a[user] --> b[manual step]",
     "after_diagram":  "flowchart TD\\n  a[user] --> b[automatic ✅]",
     "product_changes": [{"what": "...", "why": "...",
                          "before": "...", "after": "...",
                          "before_diagram": "...", "after_diagram": "..."}],
     "database_changes": [{"object": "table users", "change": "add column tz",
                           "impact": "...", "migration": "backfill from ..."}],
     "agent_structure": {"summary": "one line on what the agent does — REQUIRED whenever the plan builds an agent/LLM assistant",
                         "memory": ["context sources fed into each call"],
                         "core": ["model/tier + why", "system-prompt rules", "single call vs loop"],
                         "tools": ["what it can emit/invoke; the output contract"],
                         "guardrails": ["RBAC, validation, human-approval gates, audit"],
                         "key_property": "the one safety property, e.g. 'agent can never write the DB'"},
     "steps": ["...", "..."],
     "open_questions": ["..."],
     "plan_markdown": "full plan text — chatbot context"}

The chatbot answers questions about the plan by calling the Anthropic API
(official SDK, model claude-opus-5 by default). Credentials resolve the normal
way: ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile.
If the SDK is missing or no credential resolves, the chat panel degrades to a
notice and the comment boxes still work.

Blocks until the user clicks Approve or Deny, then prints the chat transcript
and any comments, and exits: 0 = APPROVED, 1 = DENIED, 2 = TIMEOUT.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
import tempfile
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_MODEL = "claude-opus-5"

NO_CREDENTIAL = (
    "No Anthropic credential found, so the chat can't run. Set ANTHROPIC_API_KEY "
    "in your environment, or run `ant auth login`, then reopen this page. The "
    "comment boxes work either way — they reach Claude with your Approve/Deny click."
)


class ChatError(Exception):
    """A chat failure with a message meant for the reviewer, not a stack trace."""

CSS = """
body { font-family: -apple-system, sans-serif; margin: 0; color: #1f2328; }
#wrap { display: flex; align-items: flex-start; gap: 0; }
#main { flex: 1 1 auto; min-width: 0; padding: 2rem; padding-bottom: 7rem; }
#chat { flex: 0 0 24rem; position: sticky; top: 0; height: 100vh;
        border-left: 1px solid #d0d7de; display: flex; flex-direction: column;
        background: #f6f8fa; }
h1 { margin-top: 0; }
h2 { border-bottom: 1px solid #ddd; padding-bottom: .3rem; margin-top: 2.5rem; }
.overview { font-size: 16px; max-width: 48rem; }
.pill { display: inline-block; font-size: 11px; text-transform: uppercase;
        letter-spacing: .05em; background: #ddf4ff; color: #0969da;
        border-radius: 999px; padding: .15rem .6rem; margin-bottom: .5rem; }
.card { margin: 1.2rem 0; }
.card .what { font-size: 15px; max-width: 48rem; font-weight: 600; }
.panels { display: flex; gap: .5rem; flex-wrap: wrap; align-items: stretch; }
.panel { flex: 1 1 18rem; border-radius: 8px; padding: .2rem 1rem .6rem; }
.panel h3 { margin: .5rem 0 .2rem; font-size: 13px; text-transform: uppercase; color: #666; }
.panel.was { background: #fff0f0; border: 1px solid #ffd9d9; }
.panel.now { background: #effaef; border: 1px solid #cdeccd; }
.arrow { align-self: center; font-size: 30px; color: #888; padding: 0 .2rem; }
p.dbnote { color: #5B6B85; font-size: .88rem; margin: .2rem 0 .5rem; }
.dbcard { border: 1px solid #d0d7de; border-radius: 10px; margin: .7rem 0; overflow: hidden; }
.dbhead { display: flex; align-items: center; gap: .5rem; padding: .55rem .9rem;
          background: #F2F6FC; border-bottom: 1px solid #d0d7de; }
.dbhead .obj { font-size: .95rem; font-weight: 600; background: none; }
.dbhead .kind { margin-left: auto; color: #5B6B85; font-size: .78rem;
                text-transform: uppercase; letter-spacing: .05em; }
.dbgrid { display: grid; grid-template-columns: 1.15fr 1fr; }
.dbleft { padding: .7rem .9rem; border-right: 1px solid #eaeef3; }
.dbright { padding: .7rem .9rem; font-size: .86rem; color: #3d4552; }
.dbright p { margin: 0 0 .55rem; }
ul.chglist { list-style: none; margin: .25rem 0 .6rem; padding: 0; }
li.chg { display: flex; align-items: baseline; gap: .4rem; flex-wrap: wrap;
         padding: .3rem .5rem; margin-bottom: .25rem; border-radius: 7px;
         border: 1px solid transparent; cursor: default; transition: background .12s, border-color .12s; }
li.chg code { background: #eef2f7; font-size: .8rem; }
li.chg .verb { font-size: .66rem; font-weight: 700; text-transform: uppercase;
               letter-spacing: .05em; padding: .05rem .35rem; border-radius: 999px; color: #fff; }
li.chg.new .verb { background: #2F7A55; } li.chg.modified .verb { background: #B4791F; }
li.chg.removed .verb { background: #B4441F; }
li.chg .cnote { color: #5B6B85; font-size: .82rem; flex: 1 1 100%; }
li.chg:hover { background: #F6F8FC; border-color: #d0d7de; }
/* The pairing: hovering either side makes the other glow, so "add late (boolean)" and the
   row it refers to are never something the reader has to match up by eye. */
tr.glow td { animation: pulse 1.1s ease-in-out infinite; position: relative; z-index: 1; }
tr.glow td:first-child { box-shadow: inset 3px 0 0 #13294B, 0 0 0 2px rgba(19,41,75,.35); }
@keyframes pulse { 0%,100% { filter: brightness(1); } 50% { filter: brightness(.93); } }
li.chg.glow { background: #F2F6FC; border-color: #13294B; }
/* The ER entity lights up too, so a change points at its table as well as its row. */
g.node.er-linked rect { transition: filter .15s, stroke .15s, fill .15s; }
/* Same palette as the column rows below, so the two read as one legend. */
g.node.er-new rect      { fill: #E8F6EC !important; stroke: #2F7A55 !important; }
g.node.er-modified rect { fill: #FDF4E3 !important; stroke: #B4791F !important; }
g.node.er-removed rect  { fill: #FDECEC !important; stroke: #B4441F !important; }
g.node.er-new text, g.node.er-modified text, g.node.er-removed text { font-weight: 600; }
g.node.glow rect { stroke: #FF5F05 !important; stroke-width: 3px !important;
                   filter: drop-shadow(0 0 7px rgba(255,95,5,.65)); }
g.node.glow text { font-weight: 700; }
.dbcard.glow { border-color: #13294B; box-shadow: 0 0 0 2px rgba(19,41,75,.18); }
@media (prefers-reduced-motion: reduce) { tr.glow td { animation: none; } }
.dbright .k { display: block; font-size: .7rem; text-transform: uppercase; letter-spacing: .05em;
              color: #8792a2; font-weight: 600; margin-bottom: .1rem; }
.dbright .why { font-size: .89rem; color: #24292f; }
table.cols { width: 100%; border-collapse: collapse; font-size: .84rem; }
table.cols th { text-align: left; padding: .3rem .5rem; color: #8792a2; font-weight: 600;
                font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; }
table.cols td { padding: .34rem .5rem; border-top: 1px solid #eef1f5; }
table.cols .ty { color: #5B6B85; font-family: ui-monospace, monospace; font-size: .78rem; }
table.cols .nt { color: #5B6B85; }
/* the diff colours — new/changed/removed rows are tinted so they read at a glance */
tr.c-new     td { background: #E8F6EC; }
tr.c-new     td:first-child { box-shadow: inset 3px 0 0 #2F7A55; }
tr.c-modified td { background: #FDF4E3; }
tr.c-modified td:first-child { box-shadow: inset 3px 0 0 #B4791F; }
tr.c-removed td { background: #FDECEC; color: #8a3b3b; text-decoration: line-through; }
tr.c-removed td:first-child { box-shadow: inset 3px 0 0 #B4441F; }
.tag { font-size: .66rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em;
       padding: .08rem .4rem; border-radius: 999px; }
.tag.new { background: #2F7A55; color: #fff; }
.tag.modified { background: #B4791F; color: #fff; }
.tag.removed { background: #B4441F; color: #fff; }
.tag.unchanged { background: #e6eaef; color: #5B6B85; }
.plainchange { margin: .2rem 0; font-size: .9rem; }
.dblegend { display: flex; gap: .8rem; align-items: center; font-size: .76rem; color: #5B6B85;
            margin: .1rem 0 .6rem; }
.dblegend i { display: inline-block; width: .7rem; height: .7rem; border-radius: 3px;
              margin-right: .25rem; vertical-align: -1px; }
@media (max-width: 720px) { .dbgrid { grid-template-columns: 1fr; }
  .dbleft { border-right: 0; border-bottom: 1px solid #eaeef3; } }
pre.mermaid { background: #fff; border-radius: 6px; padding: .5rem; margin: .4rem 0;
              text-align: center; }
/* CDN unreachable: mermaid source degrades to small monospace instead of rendering */
pre.mermaid:not([data-processed]) { font-family: ui-monospace, monospace;
                                    font-size: 11px; color: #777; text-align: left; }
.caption { font-size: 13px; color: #444; margin: .3rem 0 0; }
.why { color: #444; max-width: 48rem; }
table.db { border-collapse: collapse; width: 100%; max-width: 60rem; font-size: 14px; }
table.db th, table.db td { border: 1px solid #d0d7de; padding: .5rem .7rem;
                           text-align: left; vertical-align: top; }
table.db th { background: #f6f8fa; font-size: 12px; text-transform: uppercase;
              letter-spacing: .04em; color: #555; }
table.db code { background: #f6f8fa; padding: .1rem .3rem; border-radius: 4px; }
/* agent structure — connected lanes: memory → core → tools → guardrails */
.agent-lanes { display: grid; grid-template-columns: 1fr 1.4rem 1fr 1.4rem 1fr 1.4rem 1fr;
               gap: 0; align-items: stretch; margin: .6rem 0; }
.lane { border: 1px solid #d0d7de; border-radius: 10px; padding: .7rem .8rem; background: #f6f8fa; }
.lane h4 { margin: 0 0 .5rem; font-size: .72rem; text-transform: uppercase;
           letter-spacing: .07em; display: flex; align-items: center; gap: .4rem; }
.lane h4 .dot { width: .55rem; height: .55rem; border-radius: 3px; display: inline-block; }
.lane.memory h4 { color: #1a7f37; } .lane.memory .dot { background: #1a7f37; }
.lane.core h4 { color: #5867e8; } .lane.core .dot { background: #5867e8; }
.lane.tools h4 { color: #9a6700; } .lane.tools .dot { background: #9a6700; }
.lane.guardrails h4 { color: #cf222e; } .lane.guardrails .dot { background: #cf222e; }
.lane ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: .35rem; }
.lane li { background: #fff; border: 1px solid #d0d7de; border-radius: 6px;
           padding: .3rem .5rem; font-size: .82rem; line-height: 1.45; }
.lane-arrow { display: flex; align-items: center; justify-content: center;
              color: #8c959f; font-weight: 700; }
.agent-key { background: #fff8c5; border: 1px solid #d4a72c66; border-radius: 8px;
             padding: .5rem .8rem; font-size: .85rem; max-width: 60rem; }
.agent-comps { display: grid; grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr));
               gap: .7rem; margin: .8rem 0 1rem; }
.acomp { border: 1px solid #d0d7de; border-radius: 10px; background: #fff; padding: .7rem .85rem; }
.acomp h5 { margin: 0 0 .35rem; font-size: .78rem; text-transform: uppercase;
            letter-spacing: .06em; color: #1f6feb; }
.acomp p { margin: 0; font-size: .84rem; line-height: 1.5; color: #333; }
.acomp .in-code { margin-top: .4rem; font-size: .74rem; color: #57606a;
                  font-family: ui-monospace, monospace; }
@media (max-width: 720px) { .agent-lanes { grid-template-columns: 1fr; }
  .lane-arrow { transform: rotate(90deg); padding: .2rem 0; } }
ol.steps li, ul.qs li { margin: .35rem 0; max-width: 48rem; }
ul.qs { color: #9a6700; }
textarea.cmt { display: block; width: 100%; box-sizing: border-box; margin-top: .6rem;
               padding: .5rem .75rem; font: inherit; font-size: 13px;
               border: 1px solid #d0d7de; border-radius: 8px; resize: vertical; }
#bar { position: fixed; bottom: 0; left: 0; right: 24rem; background: #fff;
       border-top: 1px solid #ccc; padding: 1rem 2rem; display: flex;
       gap: 1rem; align-items: center; }
#bar textarea.cmt { flex: 1; margin-top: 0; }
#bar button { font-size: 15px; padding: .5rem 1.5rem; border-radius: 6px;
              border: none; cursor: pointer; color: #fff; }
#bar .ok { background: #2da44e; }
#bar .no { background: #cf222e; }
#chat h2 { margin: 0; padding: 1rem; border: none; font-size: 15px; }
#log { flex: 1 1 auto; overflow-y: auto; padding: 0 1rem; }
#log .msg { margin: .6rem 0; padding: .5rem .75rem; border-radius: 8px;
            font-size: 14px; white-space: pre-wrap; }
#log .user { background: #ddf4ff; }
#log .bot { background: #fff; border: 1px solid #d0d7de; }
#log .err { background: #ffebe9; border: 1px solid #ffcecb; color: #82071e; }
#ask { display: flex; gap: .5rem; padding: 1rem; border-top: 1px solid #d0d7de; }
#ask textarea { flex: 1; font: inherit; font-size: 14px; padding: .5rem;
                border: 1px solid #d0d7de; border-radius: 8px; resize: vertical; }
#ask button { background: #0969da; color: #fff; border: none; border-radius: 6px;
              padding: .5rem 1rem; cursor: pointer; }
.offline { padding: 1rem; font-size: 13px; color: #57606a; }
@media (max-width: 60rem) {
  #wrap { flex-direction: column; }
  #chat { position: static; height: auto; width: 100%; flex: none;
          border-left: none; border-top: 1px solid #d0d7de; }
  #log { max-height: 20rem; }
  #bar { right: 0; }
}
"""


def esc(s):
    return html.escape(str(s))


def comment_box(on):
    """Per-section comment box; contents ride back with the Approve/Deny click."""
    return ('<textarea class="cmt" data-on="%s" rows="2"'
            ' placeholder="Comments on this part of the plan (optional)'
            ' — sent to Claude with your decision"></textarea>'
            % esc(on))


def panels(entry):
    """Before -> After pair; diagram on top, one-line caption beneath."""
    out = []
    for key, cls, heading in (("before", "was", "Today"), ("after", "now", "After this plan")):
        diagram, caption = entry.get(key + "_diagram"), entry.get(key)
        if not (diagram or caption):
            continue
        inner = "<h3>%s</h3>" % heading
        if diagram:
            inner += '<pre class="mermaid">%s</pre>' % esc(diagram)
        if caption:
            inner += '<p class="caption">%s</p>' % esc(caption)
        out.append('<div class="panel %s">%s</div>' % (cls, inner))
    if not out:
        return ""
    return ('<div class="panels">%s</div>'
            % '<div class="arrow">&#10132;</div>'.join(out))


def build_page(plan, with_buttons, chat_status):
    s = ['<h1>%s</h1>' % esc(plan.get("title", "Plan review"))]
    s.append('<p class="pill">Proposed plan &mdash; nothing built yet</p>')
    if plan.get("overview"):
        s.append('<p class="overview">%s</p>' % esc(plan["overview"]))

    top = panels(plan)
    if top:
        s.append("<h2>Before &amp; after</h2>")
        s.append(top)
        if with_buttons:
            s.append(comment_box("before/after"))

    # ui_mockup_html: path to a standalone HTML mock of the proposed UI, shown BEFORE any code is
    # written so the user approves how it will look and work, not just a prose plan. Embedded via
    # iframe srcdoc so it renders identically in server and --static modes.
    mock_path = plan.get("ui_mockup_html")
    if mock_path and os.path.exists(mock_path):
        with open(mock_path, encoding="utf-8") as mf:
            mock_html = mf.read()
        s.append("<h2>How it will look (mockup &mdash; not built yet)</h2>")
        s.append('<iframe class="mockup" srcdoc="%s" '
                 'style="width:100%%;height:640px;border:1px solid #d0d4dc;border-radius:10px;background:#fff"></iframe>'
                 % esc(mock_html))
        if with_buttons:
            s.append(comment_box("ui mockup"))

    changes = plan.get("product_changes") or []
    if changes:
        s.append("<h2>Product changes</h2>")
        for i, c in enumerate(changes):
            body = ['<div class="card">']
            if c.get("what"):
                body.append('<p class="what">%s</p>' % esc(c["what"]))
            body.append(panels(c))
            if c.get("why"):
                body.append('<p class="why"><strong>Why:</strong> %s</p>' % esc(c["why"]))
            body.append("</div>")
            s.append("".join(body))
            if with_buttons:
                s.append(comment_box("product: %s" % (c.get("what") or i)))

    # agent_structure: when the plan builds an agent (LLM assistant, chatbot, loop), the page
    # draws its architecture — what it sees, what it can do, what stops it doing harm — as
    # connected lanes. Screens alone hide exactly the part the reviewer most needs to judge.
    ag = plan.get("agent_structure")
    if ag:
        s.append("<h2>How the agent is structured</h2>")
        if ag.get("summary"):
            s.append('<p class="dbnote">%s</p>' % esc(ag["summary"]))
        # diagram: a mermaid flowchart of the agent's actual pipeline — when the user has drawn
        # their own architecture (whiteboard, Excalidraw), mirror THAT drawing's shape and names
        # so they recognise it instantly. The lanes below become supporting detail.
        if (ag.get("diagram") or "").strip():
            s.append('<pre class="mermaid">%s</pre>' % esc(ag["diagram"].strip()))
        # components: one card per box in the diagram — what it does, in plain language.
        # This is the shared-understanding layer: the diagram shows the shape, these say
        # what each named piece actually is, so reviewer and builder mean the same thing.
        comps = ag.get("components") or []
        if comps:
            s.append('<div class="agent-comps">%s</div>' % "".join(
                '<div class="acomp"><h5>%s</h5><p>%s</p>%s</div>'
                % (esc(c.get("name", "")), esc(c.get("does", "")),
                   ('<p class="in-code">In code: %s</p>' % esc(c["in_code"])) if c.get("in_code") else "")
                for c in comps))
        lanes = [("memory", "Memory / context"), ("core", "Agent core"),
                 ("tools", "Tools / output"), ("guardrails", "Guardrails")]
        parts = []
        for i, (key, label) in enumerate(lanes):
            items = ag.get(key) or []
            if i:
                parts.append('<div class="lane-arrow">&#8594;</div>')
            parts.append('<div class="lane %s"><h4><span class="dot"></span>%s</h4><ul>%s</ul></div>'
                         % (key, esc(label),
                            "".join("<li>%s</li>" % esc(x) for x in items) or "<li>—</li>"))
        s.append('<div class="agent-lanes">%s</div>' % "".join(parts))
        if ag.get("key_property"):
            s.append('<p class="agent-key"><strong>Key property:</strong> %s</p>'
                     % esc(ag["key_property"]))
        if with_buttons:
            s.append(comment_box("agent structure"))

    db = plan.get("database_changes") or []
    er = (plan.get("er_diagram") or "").strip()
    if db or er:
        s.append("<h2>Database changes</h2>")
    if er:
        # The tables and how they relate, drawn rather than described. A reader cannot
        # judge "add a column to Interview" without seeing what Interview is attached to,
        # and a mermaid erDiagram renders through the same pipeline as the flowcharts.
        s.append('<p class="dbnote">The tables involved and how they relate — '
                 'changed tables and fields are marked.</p>')
        s.append('<pre class="mermaid">%s</pre>' % esc(er))
    if db:
        s.append('<div class="dblegend">'
                 '<span><i style="background:#E8F6EC;border:1px solid #2F7A55"></i>new</span>'
                 '<span><i style="background:#FDF4E3;border:1px solid #B4791F"></i>changed</span>'
                 '<span><i style="background:#FDECEC;border:1px solid #B4441F"></i>removed</span>'
                 '<span><i style="background:#fff;border:1px solid #d0d7de"></i>unchanged</span>'
                 '</div>')
        for i, d in enumerate(db):
            s.append(db_card(d, i))
        if with_buttons:
            s.append(comment_box("database"))

    steps = plan.get("steps") or []
    if steps:
        s.append("<h2>Build steps</h2>")
        s.append("<ol class=\"steps\">%s</ol>"
                 % "".join("<li>%s</li>" % esc(x) for x in steps))
        if with_buttons:
            s.append(comment_box("steps"))

    qs = plan.get("open_questions") or []
    if qs:
        s.append("<h2>Open questions</h2>")
        s.append('<ul class="qs">%s</ul>'
                 % "".join("<li>%s</li>" % esc(x) for x in qs))
        if with_buttons:
            s.append(comment_box("open questions"))

    bar = ""
    if with_buttons:
        bar = ("<div id=\"bar\">"
               "<span>Does this plan look right? Comments and the chat go back to Claude"
               " with your click.</span>"
               "<textarea id=\"general-cmt\" class=\"cmt\" data-on=\"general\" rows=\"1\""
               " placeholder=\"Overall comments\"></textarea>"
               "<button class=\"ok\" onclick=\"decide('approve')\">Approve plan</button>"
               "<button class=\"no\" onclick=\"decide('deny')\">Deny</button>"
               "</div>")

    if chat_status is None:
        chat_body = ('<div id="log"></div>'
                     '<div id="ask">'
                     '<textarea id="q" rows="2" placeholder="Ask about this plan…"></textarea>'
                     '<button onclick="ask()">Send</button></div>')
    else:
        chat_body = '<div class="offline">Chat unavailable: %s<br><br>' \
                    'Use the comment boxes instead — they reach Claude with your' \
                    ' Approve/Deny click.</div>' % esc(chat_status)

    script = """
var history = [];
function line(cls, text) {
  var d = document.createElement('div');
  d.className = 'msg ' + cls; d.textContent = text;
  var log = document.getElementById('log');
  log.appendChild(d); log.scrollTop = log.scrollHeight;
  return d;
}
async function ask() {
  var box = document.getElementById('q');
  var q = box.value.trim();
  if (!q) return;
  box.value = '';
  line('user', q);
  history.push({role: 'user', content: q});
  var pending = line('bot', '…');
  try {
    var r = await fetch('/chat', {method: 'POST', body: JSON.stringify({messages: history})});
    var j = await r.json();
    if (j.error) { pending.className = 'msg err'; pending.textContent = j.error; history.pop(); }
    else { pending.textContent = j.text; history.push({role: 'assistant', content: j.text}); }
  } catch (e) {
    pending.className = 'msg err'; pending.textContent = String(e); history.pop();
  }
}
document.addEventListener('keydown', function (e) {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && document.getElementById('q')) ask();
});
function decide(d) {
  var comments = [];
  document.querySelectorAll('textarea.cmt').forEach(function (t) {
    if (t.value.trim()) comments.push({on: t.getAttribute('data-on'), text: t.value.trim()});
  });
  fetch('/decision', {method: 'POST', body: JSON.stringify({decision: d, comments: comments})})
    .then(function () {
      document.body.innerHTML = '<div style="padding:2rem"><h1>' +
        (d === 'approve' ? 'Plan approved' : 'Plan denied') + '</h1><p>' +
        (comments.length ? 'Your ' + comments.length + ' comment(s) were sent to Claude. ' : '') +
        'Back to your Claude session &mdash; you can close this tab.</p></div>';
    });
}
"""

    return ("<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">"
            "<title>Plan review — %s</title><style>%s</style></head><body>"
            "<div id=\"wrap\"><div id=\"main\">%s</div>"
            "<div id=\"chat\"><h2>Ask about this plan</h2>%s</div></div>%s"
            "<script>%s</script>"
            "<script src=\"https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js\"></script>"
            "<script>if (window.mermaid) mermaid.initialize({startOnLoad: true, theme: 'neutral'});</script>"
            "%s"
            "</body></html>"
            % (esc(plan.get("title", "Plan")), CSS, "\n".join(s), chat_body, bar, script, PAIR_JS))


PAIR_JS = """<script>
(function () {
  /* Hovering a change lights up the row it describes AND the table it lives in.
     Reading "add late (boolean)" and then hunting for `late` in a column list, and then
     working out which table that even is, is the friction that makes people skim a schema
     change rather than check it. */
  function pair(a, b) {
    if (!a || !b) return;
    a.addEventListener('mouseenter', function () { b.classList.add('glow'); });
    a.addEventListener('mouseleave', function () { b.classList.remove('glow'); });
  }
  var norm = function (t) { return (t || '').replace(/[^a-z0-9]/gi, '').toUpperCase(); };

  // rows <-> change entries
  document.querySelectorAll('li.chg[data-target]').forEach(function (li) {
    var row = document.querySelector("tr[data-row='" + li.dataset.target + "']");
    pair(li, row); pair(row, li);
  });

  // ...and both of those <-> the entity in the ER diagram.
  // Mermaid renders asynchronously, so poll briefly rather than assume it is ready.
  var tries = 0;
  (function wire() {
    var svg = document.querySelector('pre.mermaid svg');
    var nodes = svg && svg.querySelectorAll('g.nodes > g.node');
    if (!nodes || !nodes.length) {
      if (tries++ < 40) return setTimeout(wire, 120);
      return; // CDN offline: the diagram degraded to text, nothing to light up
    }
    var byName = {};
    nodes.forEach(function (n) { byName[norm(n.textContent)] = n; });

    document.querySelectorAll('.dbcard').forEach(function (card) {
      var objEl = card.querySelector('.dbhead .obj');
      var entity = byName[norm(objEl && objEl.textContent)];
      if (!entity) return;
      entity.classList.add('er-linked');
      /* Tint the entity to match its card, so the diagram carries the same diff colours
         as the tables below it — a reader should be able to see which tables are new
         before reading a single word. Applied here rather than in mermaid source
         because erDiagram's own styling support is unreliable across versions. */
      var st = (card.dataset.status || '').toLowerCase();
      if (st) entity.classList.add('er-' + st);
      pair(card.querySelector('.dbhead'), entity);
      pair(entity, card);
      card.querySelectorAll('li.chg').forEach(function (li) { pair(li, entity); });
      card.querySelectorAll('tr[data-row]').forEach(function (tr) { pair(tr, entity); });
    });
  })();
})();
</script>"""

STATUS_LABEL = {"new": "new", "modified": "changed", "removed": "removed", "unchanged": ""}


def db_card(d, idx=0):
    """One affected table, drawn as a table, with the reason beside it.

    A flat "Object | Change | Impact" row asks the reader to hold the schema in their head
    and imagine where the change lands. Drawing the columns and tinting the ones that move
    means they can see it instead — and the explanation sits alongside rather than below,
    so the what and the why are read together.
    """
    obj = esc(d.get("object", ""))
    status = (d.get("status") or ("new" if not d.get("columns") else "modified")).lower()
    cols = d.get("columns") or []
    kind = esc(d.get("kind") or ("table" if cols else "change"))

    if cols:
        rows = ['<tr><th>Column</th><th>Type</th><th>Note</th></tr>']
        for c in cols:
            cs = (c.get("status") or "unchanged").lower()
            tag = STATUS_LABEL.get(cs, "")
            badge = ' <span class="tag %s">%s</span>' % (cs, esc(tag)) if tag else ""
            key = "db%d-%s" % (idx, esc(str(c.get("name", ""))))
            rows.append(
                '<tr class="c-%s" data-row="%s"><td><code>%s</code>%s</td>'
                '<td class="ty">%s</td><td class="nt">%s</td></tr>'
                % (esc(cs), key, esc(c.get("name", "")), badge,
                   esc(c.get("type", "")), esc(c.get("note", "")))
            )
        body = '<table class="cols">%s</table>' % "".join(rows)
    else:
        body = '<p class="plainchange">%s</p>' % esc(d.get("change", ""))

    side = []
    if d.get("explain"):
        side.append('<p class="why">%s</p>' % esc(d["explain"]))

    # One entry per column that actually moves, each wired to its row on the left.
    # Reading "add late (boolean)" and then hunting for `late` in the table is exactly
    # the small friction that makes people skim a schema change instead of checking it.
    moved = [c for c in cols if (c.get("status") or "unchanged").lower() != "unchanged"]
    if moved:
        items = []
        for c in moved:
            cs = (c.get("status") or "").lower()
            key = "db%d-%s" % (idx, esc(str(c.get("name", ""))))
            items.append(
                '<li class="chg %s" data-target="%s"><code>%s</code>'
                '<span class="verb">%s</span><span class="cnote">%s</span></li>'
                % (esc(cs), key, esc(c.get("name", "")),
                   esc(STATUS_LABEL.get(cs, cs)), esc(c.get("note", "")))
            )
        side.append('<p><span class="k">What moves &mdash; hover to locate it</span></p>')
        side.append('<ul class="chglist">%s</ul>' % "".join(items))
    if d.get("change") and cols:
        side.append('<p><span class="k">Change</span>%s</p>' % esc(d["change"]))
    if d.get("impact"):
        side.append('<p><span class="k">Impact on existing data</span>%s</p>' % esc(d["impact"]))
    if d.get("migration"):
        side.append('<p><span class="k">Migration</span>%s</p>' % esc(d["migration"]))
    for r in (d.get("relations") or []):
        side.append('<p><span class="k">Relates to</span>%s</p>' % esc(r))

    head = ('<div class="dbhead"><code class="obj">%s</code>'
            '<span class="tag %s">%s</span><span class="kind">%s</span></div>'
            % (obj, esc(status), esc(STATUS_LABEL.get(status, status) or "unchanged"), kind))
    right = "".join(side) or '<p class="why">&mdash;</p>'

    # With nothing to draw on the left — a change with no column detail — a two-column
    # grid leaves an empty box that reads as a rendering fault. Go full width instead.
    if not cols and not d.get("change"):
        return ('<div class="dbcard" data-status="%s">%s<div class="dbright wide">%s</div></div>'
                % (esc(status), head, right))

    return ('<div class="dbcard" data-status="%s">%s<div class="dbgrid">'
            '<div class="dbleft">%s</div><div class="dbright">%s</div></div></div>'
            % (esc(status), head, body, right))


def make_chat(plan, plan_doc, model):
    """Return (send, status). status is None when chat is live, else the reason it isn't."""
    try:
        import anthropic
    except ImportError:
        return None, "the `anthropic` package isn't installed (pip install anthropic)"
    try:
        client = anthropic.Anthropic()
    except Exception as e:  # no credential resolved, bad config, ...
        return None, "no Anthropic credentials resolved (%s)" % e

    context = plan_doc or json.dumps(plan, indent=2)
    system = (
        "You are helping a reviewer decide whether to approve an implementation plan "
        "that has NOT been built yet. Answer their questions about it: what it will do, "
        "what it will change, what the risks and gaps are. Be concise and concrete — a "
        "few sentences unless they ask for depth. You cannot edit the plan; when they want "
        "something different, say what to ask for, and remind them they can type it into a "
        "comment box or deny so it reaches the Claude session waiting on their click. If the "
        "plan does not answer something, say so plainly rather than inventing detail.\n\n"
        "THE PLAN:\n" + context
    )

    def send(messages):
        try:
            r = client.messages.create(
                model=model,
                max_tokens=8000,
                system=system,
                output_config={"effort": "low"},
                messages=messages,
            )
        except TypeError as e:  # SDK raises this when no credential resolves
            if "authentication" in str(e).lower():
                raise ChatError(NO_CREDENTIAL)
            raise
        except anthropic.AuthenticationError:
            raise ChatError(NO_CREDENTIAL)
        if r.stop_reason == "refusal":
            return "(Claude declined to answer that.)"
        return "".join(b.text for b in r.content if b.type == "text").strip() or "(empty reply)"

    return send, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", help="JSON file describing the plan (see module docstring)")
    ap.add_argument("--plan-doc", default=None,
                    help="markdown plan/spec file — full context for the chatbot")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--static", action="store_true", help="just write the page, no server, no buttons")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--no-chat", action="store_true", help="skip the chatbot panel")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.plan:
        sys.exit("--plan is required (or use --selftest)")

    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    plan_doc = None
    if args.plan_doc:
        with open(args.plan_doc, encoding="utf-8") as f:
            plan_doc = f.read()

    if args.static or args.no_chat:
        send, chat_status = None, "not enabled for this page"
    else:
        send, chat_status = make_chat(plan, plan_doc, args.model)

    page = build_page(plan, with_buttons=not args.static, chat_status=chat_status)

    if args.static:
        out = args.out or os.path.join(tempfile.gettempdir(), "plan-review.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(page)
        print(out)
        if not args.no_open:
            webbrowser.open("file://" + os.path.abspath(out))
        return

    decision = {"value": None, "comments": []}
    transcript = []
    # Persist the verdict the instant it's clicked, so a click is never lost — even if this
    # process later exits on timeout, the decision survives in this file.
    verdict_path = os.path.join(tempfile.gettempdir(), "plan-review-verdict.json")

    class Handler(BaseHTTPRequestHandler):
        def _json(self, obj, code=200):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            body = page.encode("utf-8") if self.path == "/" else b"not found"
            self.send_response(200 if self.path == "/" else 404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n).decode("utf-8", "replace").strip()
            try:
                payload = json.loads(raw)
            except ValueError:
                payload = {}

            if self.path == "/chat":
                messages = payload.get("messages") or []
                if not send:
                    return self._json({"error": "chat is not available"})
                try:
                    text = send(messages)
                except ChatError as e:
                    return self._json({"error": str(e)})
                except Exception as e:
                    return self._json({"error": "%s: %s" % (type(e).__name__, e)})
                transcript.append(("you", messages[-1].get("content", "") if messages else ""))
                transcript.append(("claude", text))
                return self._json({"text": text})

            if self.path == "/decision" and payload.get("decision") in ("approve", "deny"):
                decision["value"] = payload["decision"]
                decision["comments"] = payload.get("comments") or []
                try:  # durable record so a click survives this process exiting
                    with open(verdict_path, "w") as vf:
                        json.dump({"decision": decision["value"],
                                   "comments": decision["comments"],
                                   "chat": transcript}, vf)
                except OSError:
                    pass
            return self._json({"ok": True})

        def log_message(self, *a):
            pass

    try:  # drop any stale verdict from a previous run
        os.remove(verdict_path)
    except OSError:
        pass

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.timeout = 1  # poll interval for handle_request
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    print("Plan review at %s — waiting for Approve/Deny (timeout %ss; verdict also saved to %s)"
          % (url, args.timeout, verdict_path), flush=True)
    if chat_status:
        print("Chat panel disabled: %s" % chat_status, flush=True)
    if not args.no_open:
        webbrowser.open(url)

    deadline = time.time() + args.timeout
    while decision["value"] is None and time.time() < deadline:
        server.handle_request()
    server.server_close()

    # Chat and comments print BEFORE the verdict so the verdict stays the last line.
    if transcript:
        print("CHAT:")
        for who, text in transcript:
            print("- [%s] %s" % (who, text))
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


def selftest():
    plan = {
        "title": "Timezone-aware reminders",
        "overview": "Reminders fire in the user's local time instead of UTC.",
        "before": "everyone gets 9am UTC",
        "after": "everyone gets 9am local",
        "before_diagram": "flowchart TD\n  a[cron 9am UTC] --> b[all users 💥]",
        "after_diagram": "flowchart TD\n  a[cron hourly] --> b{user tz?} --> c[9am local ✅]",
        "product_changes": [{"what": "Reminder time follows the user",
                             "why": "Users in Asia got 5pm reminders.",
                             "before": "9am UTC", "after": "9am local"}],
        "database_changes": [{"object": "table users", "change": "add column tz text",
                              "impact": "null for existing rows",
                              "migration": "backfill from last-seen IP, default UTC"}],
        "agent_structure": {"summary": "A reminder-phrasing assistant.",
                            "memory": ["user's reminder history"],
                            "core": ["gpt-4.1 tier, single call"],
                            "tools": ["returns {reply, suggestion?} JSON"],
                            "guardrails": ["never sends — user confirms"],
                            "key_property": "the agent can never write the DB"},
        "steps": ["Add the column", "Backfill", "Switch the cron to hourly"],
        "open_questions": ["What do we do for users who never set a tz?"],
    }
    page = build_page(plan, with_buttons=True, chat_status=None)
    for must in ("Timezone-aware reminders", "Product changes", "Database changes",
                 "Build steps", "Open questions", "Ask about this plan",
                 "Approve plan", "flowchart TD", "data-on=\"database\"",
                 "How the agent is structured", "agent-lanes",
                 "data-on=\"agent structure\"", "Key property"):
        assert must in page, "missing from page: %r" % must
    # HTML in plan text must not become live markup
    hostile = build_page({"title": "<script>x</script>"}, with_buttons=True, chat_status=None)
    assert "<script>x</script>" not in hostile.replace("&lt;script&gt;x&lt;/script&gt;", "")
    # static mode drops the buttons and the comment boxes
    plain = build_page(plan, with_buttons=False, chat_status="offline")
    assert "Approve plan" not in plain and "textarea class=\"cmt\"" not in plain
    print("selftest OK")


if __name__ == "__main__":
    main()
