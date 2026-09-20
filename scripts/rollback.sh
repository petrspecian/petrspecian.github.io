#!/usr/bin/env bash
# Roll the live site back to its previous state.
#
#   ./scripts/rollback.sh            undo the most recent deploy
#   ./scripts/rollback.sh <commit>   undo one specific commit
#   ./scripts/rollback.sh --list     show recent deploys and safety tags
#
# Works by reverting, never by rewriting history, so nothing is lost and the
# revert itself can be reverted. Live again in about 20 seconds.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "${1:-}" = "--list" ]; then
  echo "Recent deploys:"; git --no-pager log --oneline -12
  echo; echo "Safety tags (state BEFORE each automatic push):"
  git --no-pager tag -l 'predeploy-*' --sort=-creatordate | head -12
  exit 0
fi

TARGET="${1:-HEAD}"
echo "Reverting: $(git --no-pager log --oneline -1 "$TARGET")"
read -r -p "Proceed? [y/N] " a; [ "$a" = "y" ] || { echo "Cancelled."; exit 1; }
git revert --no-edit "$TARGET"
git push origin main
echo "Pushed. GitHub redeploys in ~20 s; then hard-reload the page."
