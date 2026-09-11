"""Run job_scan's `design_review.py` against THIS page instead of Yehudi OS.

WHY THIS FILE EXISTS. Across four staff-design reviews of myportfolioos.com the reviewer
closed every report with the same line: `design_review.py` has never run against this page,
so `test_site.py` and `tests.html` are the only deterministic coverage the site has. That
was true, and the reason was three module-level constants — not a design decision:

    PAGE      hardcoded to ~/…/life_ops/yehudi_os.html
    RENDERERS ["yehudi_os.py", "life_ops_render.py", "render.py"]
    SIZES     job_scan/.design_sizes.json

None of the rules care where the HTML came from. So this rebinds the three and calls the
same `check()` and `smoke()`. `design_review.py` is not edited — it stays the Yehudi OS
tool it was written to be, and its self-test keeps passing.

WHAT IT CAN AND CANNOT TELL YOU — read this before trusting a clean run.

Ten rules exist. Several are about Yehudi OS's own card vocabulary — `FACE_CAPS` on the
classes `gtitle` / `gstate` / `nwhy` / `gnext` / `ntitle`, and a literal check for a missing
`BUILD QUEUE` heading. This page has none of those classes, so those rules pass by being
irrelevant, not by being satisfied. A clean run here is a WEAKER signal than a clean run on
Yehudi OS, and reporting it as equivalent would be exactly the laundering the module's own
docstring warns about.

What genuinely transfers: the BROKEN patterns (an unrendered `{{ }}`, a Python `None` or
`nan` printed as text, a renderer announcing its own failure), the smoke tests, duplicate
selectors, the oklch contrast note, and page-weight creep against a site-local baseline.

SIZES is deliberately site-local. Sharing job_scan's baseline would have two unrelated pages
overwriting each other's size history, and the weight rule would fire on noise forever.

Run: python3 design_review_site.py            # rules + render
     python3 design_review_site.py --json     # machine-readable findings
     python3 design_review_site.py --no-render
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
JOB_SCAN = os.path.expanduser("~/life_ops/job_scan")

if not os.path.isdir(JOB_SCAN):
    print(f"design_review_site: {JOB_SCAN} not found — nothing to borrow")
    raise SystemExit(2)

sys.path.insert(0, JOB_SCAN)
import design_review as dr           # noqa: E402

# Rebind the three constants. Everything else in the module is page-agnostic.
dr.PAGE = os.path.join(HERE, "index.html")
dr.SIZES = os.path.join(HERE, ".design_sizes.json")
dr.RENDERERS = []                    # no Python renderer — this page is hand-written HTML
dr.SHOTS = os.path.join(HERE, ".design_shots")


def effective_document(html):
    """Inline every local stylesheet and script, then hand THAT to the rules.

    Yehudi OS is one self-contained file, so every rule in design_review.py searches the
    HTML string for its evidence. This page keeps CSS and JS in separate files, and the
    rules cannot see them. The first run made that concrete: it reported

        FAIL [focus-visible] .reset is interactive and has no :focus-visible

    which is false — `:focus-visible` is defined in landing.css and applies to every
    element on the page. The rule was not wrong about what it checked; it was handed half
    a document. Rather than declare the finding a false positive and move on, give the
    rules the same shape of input they were written against. Duplicate-selector and
    oklch-contrast start working for the same reason.
    """
    import re as _re

    def inline_css(m):
        href = m.group(1)
        if href.startswith(("http://", "https://", "//")):
            return m.group(0)              # Google Fonts stays a link
        body = dr._read(os.path.join(HERE, href.lstrip("/")))
        return f"<style data-inlined-from=\"{href}\">\n{body}\n</style>" if body else m.group(0)

    def inline_js(m):
        src = m.group(1)
        if src.startswith(("http://", "https://", "//")):
            return m.group(0)
        body = dr._read(os.path.join(HERE, src.lstrip("/")))
        return f"<script data-inlined-from=\"{src}\">\n{body}\n</script>" if body else m.group(0)

    html = _re.sub(r'<link[^>]+rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\'][^>]*>',
                   inline_css, html)
    html = _re.sub(r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']stylesheet["\'][^>]*>',
                   inline_css, html)
    html = _re.sub(r'<script[^>]+src=["\']([^"\']+)["\'][^>]*>\s*</script>', inline_js, html)
    return html


def main(argv):
    raw = dr._read(dr.PAGE)
    if not raw:
        print("DESIGN REVIEW: page not readable —", dr.PAGE)
        return 1
    html = effective_document(raw)
    if "--raw" in argv:
        html = raw

    # `check(html, mods)` iterates mods; an empty dict means the renderer-source rules
    # simply do not run, which is correct here rather than a gap to paper over.
    found = dr.check(html, {})
    if "--no-smoke" not in argv:
        found += dr.smoke(html)

    if "--json" in argv:
        print(json.dumps([{"severity": s, "rule": r, "finding": f} for s, r, f in found],
                         indent=1))
        return 0

    fails = [x for x in found if x[0] == "FAIL"]
    print(f"DESIGN REVIEW (myportfolioos.com) — {len(found)} finding(s), "
          f"{len(fails)} blocking\n")
    for sev, rule, note in found:
        print(f"  {sev:4} [{rule}] {note}")
    if not found:
        print("  (no findings)")

    print("\n  SCOPE. The rules keyed to Yehudi OS card classes (gtitle/gstate/nwhy/gnext/"
          "\n  ntitle, BUILD QUEUE) cannot match this page. They passed by not applying. A clean"
          "\n  run here is weaker evidence than a clean run on Yehudi OS."
          "\n  CSS and JS are inlined before the rules run, because they all search one string."
          "\n  --raw skips that, which is how the focus-visible false positive reproduces.")

    if "--no-render" not in argv:
        for p in dr.render():
            print(f"\n  RENDERED → {p}")

    print("\n  Judgment pass is NOT covered here — .claude/agents/staff-designer.md is."
          "\n  Open the render above and LOOK at it.")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
