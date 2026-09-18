#!/usr/bin/env python3
"""Post-render step. Builds the machine-readable layer from the pages that actually rendered.

  1. normalises sitemap.xml (homepage as '/', no 404)
  2. writes the legacy redirect stubs (scripts/make_redirects.py)
  3. converts every rendered page to Markdown under _site/markdown/ and points each
     page at its Markdown twin with <link rel="alternate" type="text/markdown">
  4. stamps the build date into the ProfilePage schema and markdown/profile.md
  5. writes llms.txt (index) and llms-full.txt (every page's Markdown in one file)

Everything is derived from _site/, so the advertised URLs are always URLs that exist.
"""

import datetime
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "_site")
BASE = "https://petrspecian.com"
TODAY = datetime.date.today().isoformat()

PAGES = [
    ("index.html", "home", "Home", "Positioning, current work, and recent activity."),
    ("about.html", "about", "About", "Biography, roles, education, affiliations, and persistent identifiers."),
    ("research.html", "research", "Research", "Research programme and funded projects: AI institutional transformation, LLMs and democracy, expertise, behavioral political economy."),
    ("publications.html", "publications-page", "Publications", "Books, journal articles, chapters, preprints, and public writing, with abstracts and open-access full texts."),
    ("teaching.html", "teaching", "Teaching", "Courses currently taught, courses previously taught, teaching mobilities, and thesis supervision."),
    ("talks.html", "talks", "Talks and Media", "Recorded talks, keynotes, invited lectures, conference talks 2017 to the present, interviews, organized events."),
    ("writing.html", "writing", "Writing", "Essays and public writing."),
    ("contact.html", "contact", "Contact", "Contact details and professional profiles."),
]

# pages whose head already carries a curated text/markdown alternate; the generic
# page twin is still generated and listed, but the curated one stays primary
CURATED = {"index.html", "about.html", "publications.html"}

EXTERNAL = [
    ("https://orcid.org/0000-0003-2702-0354", "ORCID"),
    ("https://fsv.cuni.cz/en/contacts/people/22729867", "Charles University profile"),
    ("https://scholar.google.cz/citations?user=iYTXP5oAAAAJ", "Google Scholar"),
    ("https://www.scopus.com/authid/detail.uri?authorId=55200307800", "Scopus"),
    ("https://philpeople.org/profiles/petr-specian", "PhilPeople"),
]


def read(p):
    return open(p, encoding="utf-8").read()


def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


# ---------------------------------------------------------------- sitemap

def normalise_sitemap():
    """Quarto emits <loc>.../index.html</loc> while the homepage canonical is
    '/'. Make the two agree on '/' rather than leaving crawlers two URLs for one page."""
    p = os.path.join(SITE, "sitemap.xml")
    if not os.path.exists(p):
        return
    s = read(p)
    fixed = s.replace(f"<loc>{BASE}/index.html</loc>", f"<loc>{BASE}/</loc>")
    fixed = re.sub(r"\s*<url>\s*<loc>[^<]*/404\.html</loc>.*?</url>", "", fixed, flags=re.S)
    if fixed != s:
        write(p, fixed)
        print("sitemap.xml: homepage normalised to /, 404 removed")


# ---------------------------------------------------------------- markdown twins

def html_to_markdown(html, title, canonical):
    """Main content of a rendered page -> GitHub-flavoured Markdown, via the pandoc
    that ships with Quarto. Raw HTML is dropped, so decorative SVG and layout divs
    vanish and only the prose, headings, lists and links survive."""
    m = re.search(r"<main[^>]*>(.*?)</main>", html, re.S)
    body = m.group(1) if m else html
    body = re.sub(r"<svg.*?</svg>", "", body, flags=re.S)
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", body, flags=re.S)
    # the hidden description block is metadata, not copy
    body = re.sub(r'<(p|div) class="description">.*?</\1>', "", body, flags=re.S)
    # chip rows (keywords, project meta) -> one readable line
    def chips(m):
        items = re.findall(r'<span class="chip">(.*?)</span>', m.group(0), re.S)
        return "<p>" + " · ".join(i.strip() for i in items) + "</p>"
    body = re.sub(r'<p class="(?:chip-row|project-meta)">.*?</p>', chips, body, flags=re.S)
    r = subprocess.run(["quarto", "pandoc", "-f", "html", "-t", "gfm-raw_html", "--wrap=none"],
                       input=body, capture_output=True, text=True, check=True)
    md = r.stdout.strip()
    # relative links -> absolute, so the file makes sense away from the site
    md = re.sub(r"\]\((?!https?://|mailto:|#)(\.\./)?([^)]+)\)", lambda mm: f"]({BASE}/{mm.group(2)})", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    head = f"<!-- {canonical} · Markdown twin of the HTML page, generated {TODAY} -->\n\n"
    if not md.lstrip().startswith("#"):
        head += f"# {title}\n\n"
    return head + md + "\n"


def inject_alternate(html_path, md_url):
    html = read(html_path)
    if 'type="text/markdown"' in html:
        return False
    tag = f'<link rel="alternate" type="text/markdown" href="{md_url}" title="This page in Markdown">'
    new = html.replace("</head>", tag + "\n</head>", 1)
    if new != html:
        write(html_path, new)
        return True
    return False


def build_markdown_layer():
    """Returns [(title, html_url, md_url, description)] for core pages and works."""
    out = []
    for rel, mdname, title, desc in PAGES:
        p = os.path.join(SITE, rel)
        if not os.path.exists(p):
            print("  WARNING: not rendered:", rel)
            continue
        html = read(p)
        canonical = f"{BASE}/" if rel == "index.html" else f"{BASE}/{rel}"
        md_url = f"{BASE}/markdown/{mdname}.md"
        write(os.path.join(SITE, "markdown", f"{mdname}.md"), html_to_markdown(html, title, canonical))
        if rel not in CURATED:
            inject_alternate(p, md_url)
        out.append((title, canonical, md_url, desc))

    pubdir = os.path.join(SITE, "publications")
    works = []
    if os.path.isdir(pubdir):
        for f in sorted(os.listdir(pubdir)):
            if not f.endswith(".html"):
                continue
            p = os.path.join(pubdir, f)
            html = read(p)
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            t = re.sub(r"\s+", " ", m.group(1)).split("–")[0].strip() if m else f
            d = re.search(r'<meta name="description" content="(.*?)"', html)
            desc = d.group(1) if d else ""
            slug = f[:-5]
            canonical = f"{BASE}/publications/{f}"
            md_url = f"{BASE}/markdown/publications/{slug}.md"
            write(os.path.join(SITE, "markdown", "publications", f"{slug}.md"),
                  html_to_markdown(html, t, canonical))
            inject_alternate(p, md_url)
            works.append((t, canonical, md_url, desc))
    return out, works


# ---------------------------------------------------------------- stamps

def stamp_dates():
    n = 0
    for dirpath, _, files in os.walk(SITE):
        if "site_libs" in dirpath:
            continue
        for f in files:
            if f.endswith(".html"):
                p = os.path.join(dirpath, f)
                s = read(p)
                if "__BUILD_DATE__" in s:
                    write(p, s.replace("__BUILD_DATE__", TODAY))
                    n += 1
    prof = os.path.join(SITE, "markdown", "profile.md")
    if os.path.exists(prof):
        s = read(prof)
        write(prof, re.sub(r"Last updated: \d{4}-\d{2}-\d{2}", f"Last updated: {TODAY}", s))
    print(f"build date stamped into {n} page(s) and profile.md")


# ---------------------------------------------------------------- llms.txt

def write_llms(pages, works):
    L = ["# Petr Špecián", "",
         "> Official website of Petr Špecián, Assistant Professor at the Faculty of Social "
         "Sciences, Charles University in Prague. Research on generative AI, democracy, "
         "expertise, institutional change, behavioral political economy, and higher education.",
         "",
         f"Authoritative identity: {BASE}/markdown/profile.md  ",
         f"Everything on this site in one Markdown file: {BASE}/llms-full.txt  ",
         "Every HTML page links its own Markdown twin via <link rel=\"alternate\" type=\"text/markdown\">.",
         "",
         "## Core pages", ""]
    for title, html_url, md_url, desc in pages:
        L.append(f"- [{title}]({html_url}) · [Markdown]({md_url}): {desc}")

    L += ["", "## Individual works (abstract, citation, full-text links)", ""]
    for title, html_url, md_url, desc in works:
        L.append(f"- [{title}]({html_url}) · [Markdown]({md_url})" + (f": {desc}" if desc else ""))

    L += ["", "## Machine-readable resources", ""]
    for rel, title in [("markdown/profile.md", "Profile in Markdown (identity, affiliation, identifiers, disambiguation)"),
                       ("markdown/publications.md", "Publication list in Markdown"),
                       ("bib/publications.bib", "Publications in BibTeX"),
                       ("llms-full.txt", "Full site text in one file")]:
        if os.path.exists(os.path.join(SITE, rel)) or rel == "llms-full.txt":
            L.append(f"- [{title}]({BASE}/{rel})")

    L += ["", "## External authority records", ""]
    for url, title in EXTERNAL:
        L.append(f"- [{title}]({url})")
    L.append("")
    write(os.path.join(SITE, "llms.txt"), "\n".join(L))
    print(f"llms.txt written ({len(pages)} core pages, {len(works)} works)")


def write_llms_full(pages, works):
    parts = []
    prof = os.path.join(SITE, "markdown", "profile.md")
    if os.path.exists(prof):
        parts.append(read(prof).strip())
    for _, _, md_url, _ in pages + works:
        p = os.path.join(SITE, md_url[len(BASE) + 1:])
        if os.path.exists(p):
            parts.append(read(p).strip())
    pubs = os.path.join(SITE, "markdown", "publications.md")
    if os.path.exists(pubs):
        parts.append(read(pubs).strip())
    body = (f"# Petr Špecián · full site text\n\nGenerated {TODAY} from {BASE}. "
            f"Index of sections: {BASE}/llms.txt\n\n---\n\n" + "\n\n---\n\n".join(parts) + "\n")
    write(os.path.join(SITE, "llms-full.txt"), body)
    print(f"llms-full.txt written ({len(body)//1024} KB)")


def main():
    if not os.path.isdir(SITE):
        raise SystemExit("no _site/ yet; run quarto render first")
    normalise_sitemap()
    subprocess.run(["python3", os.path.join(ROOT, "scripts", "make_redirects.py")], check=True)
    pages, works = build_markdown_layer()
    stamp_dates()
    write_llms(pages, works)
    write_llms_full(pages, works)


if __name__ == "__main__":
    main()
