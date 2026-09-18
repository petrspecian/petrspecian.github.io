#!/usr/bin/env python3
"""Pre-publish checks for the rendered site.

Every check here exists because the audit of 2026-07-27 found the corresponding
defect on the live Google Sites build, in Sol's Quarto prototype, or both.

    python3 scripts/check_site.py            structural checks only, offline
    python3 scripts/check_site.py --network  also verify DOIs and external links

Exit code 1 if any ERROR is found. Warnings do not fail the build.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bibparse  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "_site")
BIB = os.path.join(ROOT, "bib", "publications.bib")
BASE = "https://petrspecian.com"
UA = "petrspecian.com site check (mailto:petr.specian@fsv.cuni.cz)"

errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def is_redirect_stub(path):
    """Redirect stubs are noindex by design; they are not pages."""
    head = open(path, encoding="utf-8").read(600)
    return 'name="robots"' in head and "noindex" in head


def html_files(include_stubs=False):
    for dirpath, _, files in os.walk(SITE):
        if "site_libs" in dirpath:
            continue
        for f in files:
            if not f.endswith(".html"):
                continue
            p = os.path.join(dirpath, f)
            if not include_stubs and is_redirect_stub(p):
                continue
            yield p


def rel(p):
    return os.path.relpath(p, SITE)


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


# ------------------------------------------------------------ 1. accessibility

def check_images():
    """Old site: images with empty alt. Sol's prototype: no alt attribute at all,
    and the intended alt text leaking out as a visible <figcaption>."""
    for p in html_files():
        html = open(p, encoding="utf-8").read()
        for tag in re.findall(r"<img[^>]*>", html):
            if "alt=" not in tag:
                err(f"{rel(p)}: <img> with no alt attribute -> {tag[:80]}")
            elif re.search(r'alt=(""|\'\')', tag):
                src = re.search(r'src="([^"]*)"', tag)
                warn(f"{rel(p)}: empty alt (fine only if decorative) -> {src.group(1) if src else tag[:60]}")
        for fc in re.findall(r"<figcaption[^>]*>(.*?)</figcaption>", html, re.S):
            text = re.sub(r"<[^>]+>", "", fc).strip()
            if re.match(r"^(Portrait|Photo|Cover|Image) of ", text, re.I):
                err(f"{rel(p)}: alt text is rendering as a visible caption -> {text[:60]!r}")


# ------------------------------------------------------------ 2. structure

def check_headings():
    for p in html_files():
        html = open(p, encoding="utf-8").read()
        body = html.split("<body", 1)[-1]
        n = len(re.findall(r"<h1[\s>]", body))
        if n == 0:
            warn(f"{rel(p)}: no <h1>")
        elif n > 1:
            err(f"{rel(p)}: {n} <h1> elements, expected 1")


def check_metadata():
    for p in html_files():
        html = open(p, encoding="utf-8").read()
        if not re.search(r'<meta name="description" content="[^"]{20,}"', html):
            warn(f"{rel(p)}: missing or very short meta description")
        if not re.search(r'<link rel="canonical"', html):
            err(f"{rel(p)}: no canonical link")
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        if not m or len(m.group(1).strip()) < 5:
            err(f"{rel(p)}: missing or trivial <title>")
        elif re.match(r"^\s*(Untitled|Home)\s*$", m.group(1).strip()):
            warn(f"{rel(p)}: generic title {m.group(1).strip()!r}")


def check_url_shape():
    """Old prototype used three conventions at once: canonical .html,
    llms.txt extensionless, sitemap /index.html against a '/' canonical."""
    sm = os.path.join(SITE, "sitemap.xml")
    llms = os.path.join(SITE, "llms.txt")
    if not os.path.exists(sm):
        err("sitemap.xml not generated")
        return
    sitemap_urls = set(re.findall(r"<loc>(.*?)</loc>", open(sm, encoding="utf-8").read()))

    canon = set()
    for p in html_files():
        m = re.search(r'<link rel="canonical" href="([^"]+)"', open(p, encoding="utf-8").read())
        if m:
            canon.add(m.group(1))

    for c in sorted(canon - sitemap_urls):
        if c.endswith("/404.html"):
            continue  # deliberately stripped from the sitemap by postprocess.py
        err(f"canonical URL not in sitemap: {c}")

    if os.path.exists(llms):
        for u in set(re.findall(rf"\({re.escape(BASE)}(/[^)]*)\)", open(llms, encoding="utf-8").read())):
            if u.endswith((".md", ".bib", ".txt")):
                target = os.path.join(SITE, u.lstrip("/"))
                if not os.path.exists(target):
                    err(f"llms.txt points at a missing file: {u}")
                continue
            if not u.endswith(".html") and u != "/":
                err(f"llms.txt uses a URL shape the site does not serve: {u}")


def check_internal_links():
    """Includes redirect stubs: their targets must exist or the redirect dead-ends."""
    for p in html_files(include_stubs=True):
        html = open(p, encoding="utf-8").read()
        hrefs = re.findall(r'href="([^"]+)"', html)
        hrefs += re.findall(r'content="0;\s*url=([^"]+)"', html)  # meta refresh targets
        for href in hrefs:
            if href.startswith(("http://", "https://", "#", "mailto:", "data:")):
                continue
            target = href.split("#")[0].split("?")[0]
            if not target:
                continue
            # root-relative resolves from the site root, not the file's directory
            base = SITE if target.startswith("/") else os.path.dirname(p)
            full = os.path.normpath(os.path.join(base, target.lstrip("/")))
            if not os.path.exists(full):
                err(f"{rel(p)}: broken internal link -> {href}")


def check_house_style():
    """Petr does not use em dashes. The prototype shipped nine."""
    for p in html_files():
        html = open(p, encoding="utf-8").read()
        body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html.split("<body", 1)[-1], flags=re.S)
        text = re.sub(r"<[^>]+>", " ", body)
        # the title separator Quarto puts in <title> is legitimate
        hits = [m for m in re.finditer(r"[^\s]{6,}\s*—\s*[^\s]{6,}", text)]
        if hits:
            warn(f"{rel(p)}: {len(hits)} em dash(es) in body copy")


def check_viewport_math():
    """Guard against the 2026-07-28 hero collapse: padding or width derived
    from 100vw on an element that is NOT full-bleed. At wide viewports the
    viewport-derived padding exceeded the container and starved the grid."""
    css = os.path.join(ROOT, "styles.css")
    if not os.path.exists(css):
        return
    src = open(css, encoding="utf-8").read()
    # blank out comments while preserving line numbers, so prose about the bug
    # does not trip the check on the bug
    src = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src, flags=re.S)
    for i, line in enumerate(src.split("\n"), 1):
        if "100vw" in line:
            err(f"styles.css:{i}: 100vw arithmetic in a layout rule. "
                f"Use max-width plus auto margins instead -> {line.strip()[:70]}")


def check_assets():
    limit = 400 * 1024
    for dirpath, _, files in os.walk(os.path.join(SITE, "assets")):
        for f in files:
            p = os.path.join(dirpath, f)
            size = os.path.getsize(p)
            if size > limit:
                err(f"assets/{f}: {size/1024:.0f} KB exceeds the {limit/1024:.0f} KB budget")


# ------------------------------------------------------------ 4. machine layer

def check_machine_layer():
    """The GEO layer: every page has a Markdown twin, every JSON-LD block parses,
    llms.txt and llms-full.txt exist and point at files that exist."""
    for p in html_files():
        html = open(p, encoding="utf-8").read()
        if rel(p) != "404.html" and 'type="text/markdown"' not in html:
            err(f"{rel(p)}: no <link rel=\"alternate\" type=\"text/markdown\"> twin")
        for m in re.finditer(r'<link rel="alternate" type="text/markdown" href="([^"]+)"', html):
            target = os.path.join(SITE, m.group(1).replace(BASE + "/", ""))
            if not os.path.exists(target):
                err(f"{rel(p)}: markdown alternate points at a missing file -> {m.group(1)}")
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            try:
                data = json.loads(block)
            except json.JSONDecodeError as ex:
                err(f"{rel(p)}: JSON-LD does not parse ({ex})")
                continue
            if "__BUILD_DATE__" in block:
                err(f"{rel(p)}: build date placeholder not stamped")
            nodes = data.get("@graph", [data])
            for n in nodes:
                if n.get("@type") in ("ScholarlyArticle", "Book", "Chapter", "Article") and not n.get("author"):
                    err(f"{rel(p)}: JSON-LD work without author -> {n.get('name','?')[:50]}")
    for f in ("llms.txt", "llms-full.txt", "markdown/profile.md", "markdown/publications.md"):
        if not os.path.exists(os.path.join(SITE, f)):
            err(f"{f} missing")
    full = os.path.join(SITE, "llms-full.txt")
    if os.path.exists(full) and os.path.getsize(full) < 20_000:
        warn(f"llms-full.txt is only {os.path.getsize(full)//1024} KB; did the markdown export run?")
    # nothing addressed to machines may leak into human-visible copy
    for p in html_files():
        html = open(p, encoding="utf-8").read()
        body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html.split("<body", 1)[-1], flags=re.S)
        text = re.sub(r"<[^>]+>", " ", body)
        for term in ("llms.txt", "JSON-LD", "sitemap.xml", "schema.org"):
            if term in text:
                err(f"{rel(p)}: plumbing term {term!r} visible in body copy")


# ------------------------------------------------------------ 3. citations

def check_bibliography(network=False):
    entries = bibparse.parse(BIB)
    seen = {}
    for e in entries:
        k = e["_key"]
        if k in seen:
            err(f"bib: duplicate key {k}")
        seen[k] = e
        if not e.get("year"):
            err(f"bib: {k} has no year")
        if e["_type"] == "article" and not (e.get("doi") or e.get("url")):
            warn(f"bib: {k} has neither DOI nor URL")

    if not network:
        return

    for e in entries:
        doi = e.get("doi")
        if not doi or doi.startswith("10.48550"):
            continue
        try:
            m = get_json(f"https://api.crossref.org/works/{doi}")["message"]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as ex:
            err(f"bib: {e['_key']} DOI {doi} did not resolve at Crossref ({ex})")
            continue

        # THE check. The live site cited 10.18267/j.aip.27, a working DOI
        # belonging to an entirely different 2013 paper.
        # Bilingual entries may be registered under either the original or the
        # translated title, so accept a match against either.
        got = (m.get("title") or [""])[0]
        norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
        candidates = [e["title"]]
        if e.get("titletrans"):
            candidates.append(e["titletrans"])
            # registries often drop a leading article from translated titles
            candidates.append(re.sub(r"^(An?|The)\s+", "", e["titletrans"]))
        if not any(norm(got)[:40] == norm(c)[:40] for c in candidates):
            err(f"bib: {e['_key']} DOI {doi} resolves to a DIFFERENT work.\n"
                f"      cited: {e['title']}\n"
                f"      DOI  : {got}")
            continue

        for field, api in (("volume", "volume"), ("number", "issue"), ("pages", "page")):
            live = m.get(api)
            if not live:
                continue
            ours = (e.get(field) or "").replace("–", "-")
            if ours and ours != str(live).replace("–", "-"):
                warn(f"bib: {e['_key']} {field}={ours!r} but Crossref says {live!r}")
            elif not ours:
                warn(f"bib: {e['_key']} missing {field}; Crossref has {live!r}")

        printed = (m.get("published-print") or {}).get("date-parts", [[None]])[0][0]
        if printed and str(printed) != e.get("year"):
            warn(f"bib: {e['_key']} year={e.get('year')} but Crossref print year is {printed}")


def check_external_links():
    urls = set()
    for p in html_files():
        for href in re.findall(r'href="(https?://[^"]+)"', open(p, encoding="utf-8").read()):
            urls.add(href.rstrip("."))
    for u in sorted(urls):
        if u.startswith(BASE):
            continue  # own canonical/self links; covered by check_internal_links
        req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": UA})
        try:
            urllib.request.urlopen(req, timeout=20)
        except urllib.error.HTTPError as ex:
            if ex.code in (403, 405, 999):
                continue  # bot-hostile but present
            warn(f"external link {u} -> HTTP {ex.code}")
        except Exception as ex:
            warn(f"external link {u} -> {type(ex).__name__}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", action="store_true", help="also check DOIs and external links")
    a = ap.parse_args()

    if not os.path.isdir(SITE):
        raise SystemExit("no _site/; run quarto render first")

    check_images()
    check_headings()
    check_metadata()
    check_url_shape()
    check_internal_links()
    check_house_style()
    check_viewport_math()
    check_assets()
    check_machine_layer()
    check_bibliography(network=a.network)
    if a.network:
        check_external_links()

    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
