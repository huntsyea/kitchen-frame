#!/usr/bin/env bash
# Run from the repository root after OpenWiki, with its step outcome as $1.
set -euo pipefail

outcome=${1:?OpenWiki outcome is required}
case "$outcome" in
  success|failure) ;;
  *) echo "Unsupported OpenWiki outcome: $outcome" >&2; exit 1 ;;
esac

# Match OpenWiki's ephemeral-CI example. Pages, Claims, and manifests remain;
# this checkout's active queue is not committed to the documentation branch.
rm -f -- openwiki/.run.json

paths=(openwiki AGENTS.md .github/workflows/openwiki-update.yml)
if [[ -e CLAUDE.md ]]; then paths+=(CLAUDE.md); fi
git add -A -- "${paths[@]}"
(IFS=,; echo "list=${paths[*]}") >> "${GITHUB_OUTPUT:?}"

status=$(python3 - <<'PY'
import json
from pathlib import Path
path = Path('openwiki/.last-update.json')
print(json.loads(path.read_text()).get('status', '') if path.exists() else '')
PY
)

# Interrupted metadata is meaningful when it accompanies durable output.
# Keep that state intact, including Claims/manifest-only changes. Only discard
# an unsuccessful attempt whose sole change is .last-update.json. A successful
# no-op deliberately refreshes that file and must still be publishable.
if [[ "$outcome" != success || "$status" != complete ]] &&
   git diff --cached --quiet -- "${paths[@]}" ':(exclude)openwiki/.last-update.json'; then
  git restore --source=HEAD --staged --worktree -- "${paths[@]}"
  echo 'has-changes=false' >> "$GITHUB_OUTPUT"
  echo '::notice title=OpenWiki update skipped::Only unsuccessful run metadata changed; preserving the prior wiki and any existing update PR.'
elif git diff --cached --quiet -- "${paths[@]}"; then
  echo 'has-changes=false' >> "$GITHUB_OUTPUT"
else
  echo 'has-changes=true' >> "$GITHUB_OUTPUT"
fi
