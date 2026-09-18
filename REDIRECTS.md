# Redirect map

Every URL that currently exists on either Google Sites, mapped to its destination.
Blanket redirects to the homepage would throw away the inbound links that already
exist, so each path is mapped individually.

## petr-specian.com (Google Sites → new site)

| Old path | New path | Note |
|---|---|---|
| `/` | `/` | |
| `/home` | `/` | Google Sites duplicate of the homepage |
| `/news` | `/talks.html` | News was mostly talks and publication announcements |
| `/publications` | `/publications.html` | |
| `/events-and-talks` | `/talks.html` | |
| `/research-projects` | `/research.html` | |
| `/teaching` | `/teaching.html` | |
| `/fellowships` | `/about.html#research-fellowships` | Folded into About |
| `/contact` | `/contact.html` | |

## institutional-transformation.ai (both apex and www)

The research group's FHS-era team dispersed and the group is being rebuilt.
Its content now lives inside the Research section rather than as a subsite.

| Old path | New path |
|---|---|
| `/` | `/research.html#ai-institutional-transformation` |
| `/home` | `/research.html#ai-institutional-transformation` |
| `/projects` | `/research.html#ai-institutional-transformation` |
| `/publications` | `/publications.html` |
| `/news` | `/talks.html` |
| `/team` | `/about.html` |
| `/contact` | `/contact.html` |

**Do not** redirect `/team` to a new team page. The old roster listed seven
people, largely FHS-based, who are no longer the active group.

## How to implement

Google Sites cannot issue 301s. Two options, in order of preference.

**1. Move the domain to the new host (preferred).** Point `petr-specian.com`
DNS at GitHub Pages, then serve the redirects from the new site. Add a small
HTML file at each old path containing a canonical link and a meta refresh:

```html
<link rel="canonical" href="https://www.petr-specian.com/talks.html">
<meta http-equiv="refresh" content="0; url=/talks.html">
```

`scripts/make_redirects.py` generates these from the tables above.

**2. Keep Google Sites alive temporarily** and edit each page down to a single
"this page has moved" line pointing at the new URL. Worse for ranking, but it
works during a phased cutover.

For `institutional-transformation.ai`, the cleanest route is a redirect rule at
the DNS/registrar level (Namecheap supports URL redirect records) or, once the
apex record exists, a tiny static site that serves the mapping above. Both apex
and `www` must redirect. The apex previously had no A record at all and returned
NXDOMAIN; that was fixed on 2026-07-27.

## Post-cutover checks

- [ ] Every old URL returns 301 (not 302, not 200 with a meta refresh only)
- [ ] `petr-specian.com` apex still 301s to `www`, or pick one and be consistent
- [ ] Both apex and `www` of `institutional-transformation.ai` redirect
- [ ] Google Search Console: submit the new sitemap, watch coverage for two weeks
- [ ] Update the URL in the ORCID record if the canonical host changes
