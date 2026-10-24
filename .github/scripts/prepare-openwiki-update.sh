#!/usr/bin/env bash
# Run from the repository root after OpenWiki, with its step outcome as $1.
set -euo pipefail

outcome=${1:?OpenWiki outcome is required}
case "$outcome" in
  success|failure) ;;
  *) echo "Unsupported OpenWiki outcome: $outcome" >&2; exit 1 ;;
esac

rm -f -- openwiki/.run.json

# A failed attempt must not replace the last successful documentation baseline.
if [[ "$outcome" != success ]]; then
  if git cat-file -e HEAD:openwiki/.last-update.json 2>/dev/null; then
    git restore --source=HEAD --staged --worktree -- openwiki/.last-update.json
  else
    rm -f -- openwiki/.last-update.json
  fi
fi

paths=(openwiki AGENTS.md .github/workflows/openwiki-update.yml)
if [[ -e CLAUDE.md ]]; then paths+=(CLAUDE.md); fi
git add -A -- "${paths[@]}"
(IFS=,; echo "list=${paths[*]}") >> "${GITHUB_OUTPUT:?}"

# Include additions, edits, and deletions, but require an actual wiki page.
# Claims, manifests, timestamps, and agent instructions alone do not qualify.
if git diff --cached --quiet -- ':(glob)openwiki/**/*.md'; then
  # Discard metadata-only output too, including a successful no-page attempt.
  git restore --source=HEAD --staged --worktree -- "${paths[@]}"
  echo 'has-pages=false' >> "${GITHUB_OUTPUT:?}"
  echo '::notice title=OpenWiki update skipped::No wiki pages changed; preserving the documentation baseline and any existing update PR.'
else
  echo 'has-pages=true' >> "${GITHUB_OUTPUT:?}"
fi
