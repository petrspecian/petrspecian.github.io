#!/usr/bin/env bash
# Build the site end to end. Requires quarto on PATH and python3.
#   ./build.sh            build + structural checks
#   ./build.sh --network  also verify every DOI against Crossref
set -euo pipefail
cd "$(dirname "$0")"

command -v quarto >/dev/null || {
  echo "quarto not found. Install with: brew install --cask quarto"
  echo "(needs your password; it runs a system installer)"
  exit 1
}

echo "==> regenerating publication pages from bib/publications.bib"
python3 scripts/generate_publications.py

echo "==> rendering"
quarto render

echo "==> checking"
python3 scripts/check_site.py "$@"
