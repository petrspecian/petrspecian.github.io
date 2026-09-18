"""Minimal BibTeX reader for this site.

Deliberately dependency-free: the site must build on a machine with nothing
but Python 3 and Quarto. Handles the subset of BibTeX used in bib/publications.bib
(braced values, no @string, no crossref, no concatenation).
"""

import re


def _strip_braces(v):
    v = v.strip()
    while v.startswith("{") and v.endswith("}"):
        v = v[1:-1].strip()
    if v.startswith('"') and v.endswith('"'):
        v = v[1:-1].strip()
    return v


LATEX = {
    r"\ldots": "…",
    r"\&": "&",
    r"\%": "%",
    r"\_": "_",
    r"--": "–",
    r"~": " ",
}


def _detex(v):
    for k, r in LATEX.items():
        v = v.replace(k, r)
    return re.sub(r"\s+", " ", v).strip()


def parse(path):
    """Return a list of dicts, one per entry, in file order."""
    text = open(path, encoding="utf-8").read()
    # drop comment lines
    text = "\n".join(l for l in text.split("\n") if not l.lstrip().startswith("%"))

    entries = []
    for m in re.finditer(r"@(\w+)\s*\{", text):
        etype = m.group(1).lower()
        start = m.end()
        depth = 1
        i = start
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        body = text[start:i - 1]

        key, _, rest = body.partition(",")
        entry = {"_type": etype, "_key": key.strip()}

        # split fields on top-level commas
        fields, depth, buf = [], 0, ""
        for ch in rest:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if ch == "," and depth == 0:
                fields.append(buf)
                buf = ""
            else:
                buf += ch
        fields.append(buf)

        for f in fields:
            if "=" not in f:
                continue
            k, _, v = f.partition("=")
            entry[k.strip().lower()] = _detex(_strip_braces(v))
        entries.append(entry)
    return entries


def authors(entry):
    """['Špecián, Petr', ...] -> ['Petr Špecián', ...]"""
    raw = entry.get("author", "")
    out = []
    for a in raw.split(" and "):
        a = a.strip()
        if "," in a:
            family, _, given = a.partition(",")
            out.append(f"{given.strip()} {family.strip()}".strip())
        else:
            out.append(a)
    return out


def author_string(entry, sep=", ", last=" and "):
    a = authors(entry)
    if not a:
        return ""
    if len(a) == 1:
        return a[0]
    return sep.join(a[:-1]) + last + a[-1]


def citation(entry):
    """Chicago-ish author-date string, plain text."""
    names = []
    for i, a in enumerate(authors(entry)):
        parts = a.rsplit(" ", 1)
        names.append(f"{parts[-1]}, {parts[0]}" if i == 0 and len(parts) > 1 else a)
    who = ", and ".join(names) if len(names) > 1 else (names[0] if names else "")

    year = entry.get("year", "n.d.")
    title = entry.get("title", "")
    if entry.get("titletrans"):
        title = f"{title} [{entry['titletrans']}]"

    # don't double terminal punctuation on titles ending in … ? !
    tp = "" if title.rstrip().endswith(("…", "?", "!")) else "."

    bits = [f"{who}. {year}."]
    t = entry["_type"]
    if t == "book":
        sub = f": {entry['subtitle']}" if entry.get("subtitle") else ""
        bits.append(f"*{title}{sub}*.")
        if entry.get("series"):
            bits.append(f"{entry['series']}.")
        addr = f"{entry['address']}: " if entry.get("address") else ""
        bits.append(f"{addr}{entry.get('publisher','')}.")
    elif t == "article":
        bits.append(f'"{title}{tp}"')
        loc = f"*{entry.get('journal','')}*"
        if entry.get("volume"):
            loc += f" {entry['volume']}"
        if entry.get("number"):
            loc += f"({entry['number']})"
        if entry.get("pages"):
            loc += f": {entry['pages']}"
        bits.append(loc + ".")
    elif t == "incollection":
        bits.append(f'"{title}{tp}"')
        bits.append(f"In *{entry.get('booktitle','')}*,")
        if entry.get("pages"):
            bits.append(f"{entry['pages']}.")
        addr = f"{entry['address']}: " if entry.get("address") else ""
        bits.append(f"{addr}{entry.get('publisher','')}.")
    else:
        bits.append(f'"{title}{tp}"')
        if entry.get("howpublished"):
            bits.append(f"{entry['howpublished']}.")
        if entry.get("archiveprefix"):
            bits.append(f"{entry['archiveprefix']}:{entry.get('eprint','')}.")

    s = " ".join(b for b in bits if b.strip())
    if entry.get("onlineyear"):
        s += f" Published online {entry['onlineyear']}."
    return re.sub(r"\s+", " ", s).strip()


def link(entry):
    if entry.get("doi"):
        return f"https://doi.org/{entry['doi']}"
    if entry.get("containerdoi"):
        # DOI of the containing volume, not of this chapter
        return f"https://doi.org/{entry['containerdoi']}"
    return entry.get("url", "")


def link_label(entry):
    if entry.get("doi"):
        return "DOI"
    if entry.get("containerdoi"):
        return "Volume DOI"
    return "Read"
