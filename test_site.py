"""Structural tests for myportfolioos.com. Stdlib only, no network, no browser.

WHY A TEST FILE FOR A STATIC SITE. The landing page was converted by hand from a
Claude Design canvas (`Yehudi Baptiste Portfolio.dc.html`). That canvas is full of
markup only the design editor understands — `<x-dc>`, `<sc-for>`, `{{ bindings }}`,
`style-hover="…"`, and a `window.claude.complete()` call that does not exist outside
a published Artifact. Every one of those fails SILENTLY in a browser: no error, just
a dead hover state or an empty panel. A person re-checking that by eye will miss one.

WHAT IT GUARDS, in priority order:

  1. NO DESIGN RUNTIME LEAKED IN. The conversion is only finished if none of it is left.
  2. THE HEAD IS RIGHT. The whole point of this page is ranking for "Yehudi Baptiste",
     and on 2026-09-10 a search for the old page's exact title returned zero results —
     the domain was not indexed at all. A missing <title> is the failure that costs most.
  3. THE ANSWERS ARE IN THE MARKUP. If the six answers live only in JavaScript, a
     crawler sees an empty panel and the page cannot rank for anything it says.
  4. HIS CONTENT SURVIVED. His instruction on 2026-09-11 was to keep the existing
     Portfolio OS copy and drop only the About section. Both halves are asserted.
  5. NO SECRET SHIPPED. v2 adds a model proxy. The day someone pastes a key into the
     page instead of the Worker, this fails.

Run: python3 test_site.py            # the suite
     python3 test_site.py --serve    # serve on :8000 for tests.html
"""
import html.parser
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

BAD = 0
RAN = 0


def check(label, got, want=True):
    global BAD, RAN
    RAN += 1
    ok = got == want
    BAD += not ok
    line = f"{'ok  ' if ok else 'FAIL'} {label[:72]:74}"
    if not ok:
        line += f" got {got!r}"
    print(line)


def read(*parts):
    p = os.path.join(HERE, *parts)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return f.read()


class Tags(html.parser.HTMLParser):
    """Collects (tag, attrs-dict, text) triples. Enough for structural assertions."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self._stack = []

    def handle_starttag(self, tag, attrs):
        rec = {"tag": tag, "attrs": dict(attrs), "text": ""}
        self.tags.append(rec)
        if tag not in ("meta", "link", "br", "hr", "img", "input"):
            self._stack.append(rec)

    def handle_endtag(self, tag):
        while self._stack:
            rec = self._stack.pop()
            if rec["tag"] == tag:
                break

    def handle_data(self, data):
        for rec in self._stack:
            rec["text"] += data

    def find(self, tag, **attrs):
        out = []
        for r in self.tags:
            if r["tag"] != tag:
                continue
            if all(r["attrs"].get(k) == v for k, v in attrs.items()):
                out.append(r)
        return out

    def by_class(self, tag, cls):
        return [r for r in self.tags
                if r["tag"] == tag and cls in (r["attrs"].get("class") or "").split()]


def main():
    index = read("index.html")
    if index is None:
        print("FAIL index.html is missing")
        return 1
    css = read("landing.css")
    js = read("site.js")
    writing = read("writing", "prices-fell-evidence-didnt.html")

    doc = Tags()
    doc.feed(index)

    # ---------------------------------------------------------------- 1. runtime
    print("\nNO DESIGN-CANVAS RUNTIME LEFT IN THE PAGE\n")
    for needle, why in (
        ("<x-dc", "the canvas root element"),
        ("sc-for", "the canvas loop element"),
        ("sc-if", "the canvas conditional element"),
        ("DCLogic", "the canvas component base class"),
        ("support.js", "the 69KB canvas runtime, which also needs window.React"),
        ("style-hover", "an attribute only the design editor understands"),
        ("{{", "an unrendered canvas binding"),
        ("window.claude", "only exists inside a published Claude Artifact"),
    ):
        check(f"index.html contains no {needle!r} — {why}", needle in index, False)

    if js:
        check("site.js contains no window.claude call", "window.claude" in js, False)

    # ---------------------------------------------------------------- 2. the head
    print("\nTHE HEAD — THIS IS WHAT RANKING FOR HIS NAME DEPENDS ON\n")
    titles = doc.find("title")
    check("a <title> exists at all", len(titles), 1)
    title = titles[0]["text"].strip() if titles else ""
    check("the title carries his full name", "Yehudi Baptiste" in title)
    check(f"the title is not the old product-only title ({title[:40]!r})",
          title.startswith("Portfolio OS"), False)

    desc = doc.find("meta", name="description")
    check("a meta description exists", len(desc), 1)
    dtext = desc[0]["attrs"].get("content", "") if desc else ""
    check(f"the description is a usable length ({len(dtext)} chars)", 50 <= len(dtext) <= 320)
    check("the description names him", "Yehudi Baptiste" in dtext)

    canon = doc.find("link", rel="canonical")
    check("a canonical URL is declared", len(canon), 1)
    check("the canonical points at the apex domain",
          canon[0]["attrs"].get("href") if canon else None, "https://myportfolioos.com/")

    for prop in ("og:type", "og:url", "og:title", "og:description"):
        check(f"{prop} is set", len(doc.find("meta", property=prop)), 1)

    check("html has a lang attribute", doc.find("html")[0]["attrs"].get("lang"), "en")
    check("a viewport meta exists", len(doc.find("meta", name="viewport")), 1)

    h1s = doc.find("h1")
    check("exactly one <h1>", len(h1s), 1)

    # JSON-LD is what puts a name into a knowledge panel rather than a blue link.
    ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', index, re.S)
    check("a JSON-LD block exists", bool(ld))
    if ld:
        try:
            data = json.loads(ld.group(1))
            check("the JSON-LD parses", True)
            check("it describes a Person", data.get("@type"), "Person")
            check("with his name", data.get("name"), "Yehudi Baptiste")
            check("and at least one sameAs profile", len(data.get("sameAs") or []) >= 1)
        except ValueError as e:
            check(f"the JSON-LD parses ({e})", False)

    # ---------------------------------------------------------------- 2b. viewport fit
    print("\nTHE PORTFOLIO + CHAT FITS ONE VIEWPORT (meddahabdallah.pro model)\n")
    check("the .screen wrapper exists", 'class="screen"' in index)
    check("it is locked to one viewport height", "height: 100dvh" in (css or ""))
    check("and does not scroll the page", ".screen {" in (css or "")
          and "overflow: hidden" in (css or ""))
    check("the header does not shrink", ".site-header { flex: none; }" in (css or ""))
    check("the stage takes the remaining height", "flex: 1 1 0" in (css or ""))
    check("the rail has its own content region", 'class="rail-scroll"' in index)
    # 2026-09-11, his instruction: "make the whole resume section on the left fit inside
    # the panel. i should be able to see education without scrolling." tests.html measures
    # that it actually fits at 1440x900, 1366x768 and 1280x720.
    check("the rail keeps overflow as a floor for tiny windows, not as the layout",
          "overflow-y: auto" in (css or ""))
    check("no fade over the cut — nothing is cut any more",
          "mask-image" in (css or ""), False)
    check("the résumé link is pinned outside the content region",
          bool(re.search(r'</div>\s*\n\s*<a class="resume"', index)))
    check("the decorative rules are gone (they cost 40px of rail height)",
          "<hr>" in index, False)
    check("short laptops get their own rhythm (1280x720 clipped two cards)",
          "@media (max-height: 800px)" in (css or ""))
    # Removed by Yehudi on 2026-09-11: the phone number, the composer note and the
    # disclaimer line. Asserted as ABSENT so none of them creeps back.
    check("no phone number on a page that ranks for his name", "tel:" in index, False)
    check("no composer note", "composer" in index, False)
    check("no disclaimer line", "disclaimer" in index, False)
    # Four findings from the 2026-09-11 design review, all fixed here.
    check("the panel has a bottom edge and a route below the fold",
          'class="panel-foot"' in index)
    check("the first screen points at the Portfolio OS section",
          'href="#portfolio-os"' in index)
    check("the h1 is floored at 16px on short laptops, not shrunk under the cards",
          ".lede { font-size: 16px; line-height: 1.4; }" in (css or ""))
    check("the timeline connector uses --chip, not the 1.21:1 --line",
          bool(re.search(r"\.timeline \{[^}]*border-left: 1px solid var\(--chip\)", css or "", re.S)))
    check("role dates use --muted (6.56:1), not --faint (3.44:1, fails AA)",
          bool(re.search(r"\.timeline \.years \{[^}]*color: var\(--muted\)", css or "", re.S)))
    check("no dead .msg rules left behind", ".msg .glyph" in (css or ""), False)
    check("the lock is released below 900px",
          ".screen { height: auto; overflow: visible; }" in (css or ""))
    # 2026-09-11: .stage kept `flex: 1 1 0` here and collapsed to 0px. The whole
    # phone layout painted on top of itself and 106 tests stayed green.
    check("and .stage is explicitly un-flexed there, or the phone layout collapses",
          bool(re.search(r"@media \(max-width: 900px\)\s*\{[^}]*\}?(?:[^@]*?)\.stage \{ flex: none;", css or "", re.S)))
    check("the try-asking grid is one column",
          "grid-template-columns: minmax(0, 1fr);" in (css or ""))
    # The long-form answer needs headings, lists and the two formula blocks, and the no-JS
    # fallback must render them the same way the replayed answer does.
    for sel in (".turn.ai .bubble h4", ".qa-item .answer h4",
                ".turn.ai .bubble ul", ".qa-item .answer ul",
                ".turn.ai .bubble .chain", ".qa-item .answer .chain"):
        check(f"styled for both paths: {sel}", sel in (css or ""))

    # ---------------------------------------------------------------- 3. answers
    print("\nTHE SIX ANSWERS ARE IN THE MARKUP, NOT ONLY IN JAVASCRIPT\n")
    items = doc.by_class("article", "qa-item")
    check("six questions are present", len(items), 6)

    ids = [r["attrs"].get("id") for r in items]
    check("every question has an id (they are deep-linkable)", all(ids))
    check("the ids are unique", len(set(ids)), len(ids))

    blocks = re.findall(r'<article class="qa-item" id="([^"]+)">(.*?)</article>', index, re.S)
    check("each question block was matched for content", len(blocks), 6)
    for qid, body in blocks:
        h3 = re.search(r"<h3>(.*?)</h3>", body, re.S)
        ans = re.search(r'<div class="answer">(.*?)</div>\s*$', body.strip(), re.S)
        check(f"{qid}: has a question heading", bool(h3 and h3.group(1).strip()))
        check(f"{qid}: has an answer body", bool(ans))
        if ans:
            text = re.sub(r"<[^>]+>", "", ans.group(1))
            text = re.sub(r"\s+", " ", text).strip()
            check(f"{qid}: the answer is real, not a stub ({len(text)} chars)", len(text) > 250)
            check(f"{qid}: the answer has at least two paragraphs",
                  ans.group(1).count("<p>") >= 2)

    # ---------------------------------------------------------------- 4. his content
    print("\nHIS RULING: KEEP THE EXISTING CONTENT, DROP ONLY THE ABOUT SECTION\n")
    for needle, what in (
        ("How I Build AI Products", "the panel heading"),
        ("227 developments", "the Portfolio OS live-test number"),
        ("it remembers why you invested", "the product line"),
        ("Principles", "the principles section"),
        ("Book a call", "the call to action"),
        ("calendar.app.google", "the booking link"),
        ("loom.com/share", "the 3-minute demo"),
        ("prices-fell-evidence-didnt.html", "the essay link"),
        ("no tracking, no ads, no feed", "the footer line"),
    ):
        check(f"kept: {what}", needle in index)

    check("the v2 caveat is gone entirely", "Live chat arrives in v2" in index, False)
    # The page speaks in first person throughout — heading and every answer.
    check("no third-person agent framing", "portfolio agent" in index, False)
    # Removed 2026-09-11 on his instruction, questions moved to the top of the panel.
    check("no intro bubble", "msg ai intro" in index, False)
    check("no </> glyph", 'class="glyph"' in index, False)
    check("the questions are the first thing in the transcript",
          index.index('id="qa"') < index.index('id="log"'))
    check("the untouched panel no longer centres itself",
          ".transcript.is-empty { justify-content: center; }" in (css or ""), False)
    for third in ("he launched", "he evaluates", "he runs"):
        check(f"no third-person reference: {third!r}", third in index, False)
    check("the card grid precedes the answer log, so cards survive a click",
          index.index('id="qa"') < index.index('id="log"'))

    for needle, what in (
        ("I build AI systems that help people and institutions",
         "the old About opener — the rail replaces it"),
        ("Before this: product at HubSpot, Intuit, and Outreach",
         "the old About paragraph — the timeline replaces it"),
    ):
        check(f"removed: {what}", needle in index, False)

    # ---------------------------------------------------------------- 5. links
    print("\nEVERY INTERNAL LINK RESOLVES; EVERY NEW TAB IS SAFE\n")
    for a in doc.find("a"):
        href = a["attrs"].get("href", "")
        if not href or href.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            continue
        rel = href.lstrip("/")
        target = os.path.join(HERE, rel)
        if rel.endswith("/") or rel == "":
            target = os.path.join(HERE, rel, "index.html")
        check(f"internal link resolves: {href}", os.path.exists(target))

    for a in doc.find("a"):
        if a["attrs"].get("target") == "_blank":
            rel = a["attrs"].get("rel", "")
            check(f"target=_blank carries rel=noopener: {a['attrs'].get('href','')[:46]}",
                  "noopener" in rel)

    # ---------------------------------------------------------------- 6. assets
    print("\nASSETS AND STYLESHEETS EXIST\n")
    check("landing.css exists", css is not None)
    check("site.js exists", js is not None)
    check("style.css still exists for /writing", read("style.css") is not None)
    pdf = os.path.join(HERE, "assets", "Yehudi_Baptiste_Resume_2026.pdf")
    check("the résumé PDF is in place", os.path.exists(pdf))
    if os.path.exists(pdf):
        check(f"the résumé PDF is not a stub ({os.path.getsize(pdf)} bytes)",
              os.path.getsize(pdf) > 10_000)
    check("CNAME still points at the apex domain", (read("CNAME") or "").strip(),
          "myportfolioos.com")

    # The page was live and absent from Google's index; these are what a crawler looks for.
    robots = read("robots.txt") or ""
    check("robots.txt exists", bool(robots))
    check("it does not disallow the site", "Disallow: /" in robots, False)
    check("and points at the sitemap", "Sitemap: https://myportfolioos.com/sitemap.xml" in robots)
    sitemap = read("sitemap.xml") or ""
    check("sitemap.xml exists", bool(sitemap))
    if sitemap:
        import xml.dom.minidom
        try:
            xml.dom.minidom.parseString(sitemap)
            check("the sitemap is valid XML", True)
        except Exception as e:
            check(f"the sitemap is valid XML ({e})", False)
        check("it lists the home page", "<loc>https://myportfolioos.com/</loc>" in sitemap)
        check("it lists the essay",
              "prices-fell-evidence-didnt.html</loc>" in sitemap)
    check("nothing on the page asks not to be indexed", "noindex" in index, False)

    # ---------------------------------------------------------------- 7. secrets
    print("\nNO SECRET IN ANYTHING THAT SHIPS\n")
    for name in ("index.html", "site.js", "landing.css", "style.css"):
        body = read(name) or ""
        check(f"{name}: no Anthropic key", "sk-ant" in body, False)
        check(f"{name}: no generic api_key assignment",
              bool(re.search(r"""api[_-]?key\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}""", body, re.I)),
              False)

    # ---------------------------------------------------------------- 8. a11y
    print("\nACCESSIBILITY BASICS\n")
    check("the conversation log announces new answers",
          'aria-live="polite"' in index)
    for img in doc.find("img"):
        check(f"img has alt text: {img['attrs'].get('src','?')[:40]}",
              "alt" in img["attrs"])
    check("a focus-visible style is defined", ":focus-visible" in (css or ""))
    check("reduced motion is respected", "prefers-reduced-motion" in (css or ""))
    # Deliberately NOT the only mobile check. A string match on this media query was
    # green while the phone layout was completely broken; tests.html measures the box.
    check("a small-screen breakpoint exists (tests.html measures whether it works)",
          "max-width: 900px" in (css or ""))
    check("contact links clear the 24px hit-area minimum",
          ".contact a { padding: 4px 0; }" in (css or ""))
    check("the single-theme decision is written down, not silent",
          "Single-theme light on purpose" in (css or ""))

    # ---------------------------------------------------------------- 9. writing
    print("\nTHE ESSAY PAGE STILL FITS THE SITE\n")
    check("the essay page exists", writing is not None)
    if writing:
        check("its nav no longer calls the home page 'Portfolio OS'",
              '<a href="/">Portfolio OS</a>' in writing, False)
        check("it still links home", 'href="/"' in writing)
        check("it does not link to a removed #about anchor",
              'href="/#about"' in writing, False)

    print(f"\n{RAN - BAD}/{RAN} passed")
    return 1 if BAD else 0


def serve(port=8000):
    import http.server
    import socketserver
    os.chdir(HERE)
    handler = http.server.SimpleHTTPRequestHandler

    # socketserver.TCPServer leaves allow_reuse_address False, so a restart inside the
    # TIME_WAIT window dies with "Address already in use" on a port lsof reports as free.
    class Server(socketserver.TCPServer):
        allow_reuse_address = True

    with Server(("", port), handler) as httpd:
        print(f"serving {HERE} at http://localhost:{port}/")
        print(f"interaction harness: http://localhost:{port}/tests.html")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    if "--serve" in sys.argv:
        serve()
    else:
        raise SystemExit(main())
