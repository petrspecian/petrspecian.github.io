#!/usr/bin/env python3
"""Emit redirect stubs into _site for every legacy Google Sites URL.

Run after `quarto render`. Each stub carries a canonical link plus a meta
refresh, which is the best a static host can do without server rules. If the
site ever moves to a host that supports real 301s, delete this and use those
instead; the mapping below is the source either way.
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "_site")
BASE = "https://petrspecian.com"

# legacy path -> new path. See REDIRECTS.md for the reasoning.
MAP = {
    "home": "/",
    "news": "/talks.html",
    "publications": "/publications.html",
    "events-and-talks": "/talks.html",
    "research-projects": "/research.html",
    "teaching": "/teaching.html",
    "fellowships": "/about.html#research-fellowships",
    "contact": "/contact.html",
    # institutional-transformation.ai paths, if that domain is served from here
    "projects": "/research.html#ai-institutional-transformation",
    "team": "/about.html",
}

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Moved: Petr Špecián</title>
<link rel="canonical" href="{base}{target}">
<meta name="robots" content="noindex, follow">
<meta http-equiv="refresh" content="0; url={target}">
</head>
<body>
<p>This page has moved to <a href="{target}">{base}{target}</a>.</p>
</body>
</html>
"""


def main():
    if not os.path.isdir(SITE):
        raise SystemExit("no _site/; run quarto render first")
    n = 0
    for old, new in MAP.items():
        # skip if a real page already occupies that name
        if os.path.exists(os.path.join(SITE, old + ".html")):
            continue
        d = os.path.join(SITE, old)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(TEMPLATE.format(base=BASE, target=new))
        n += 1
    print(f"{n} redirect stub(s) written")


if __name__ == "__main__":
    main()
