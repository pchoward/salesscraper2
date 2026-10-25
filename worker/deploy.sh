#!/usr/bin/env bash
# Deploy the alerts Worker from an up-to-date main, and stamp the commit so
# GET /v1/health (and the "Alerts Worker drift" workflow) can tell which code
# is live. Run from anywhere: ./worker/deploy.sh
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f wrangler.toml ]; then
  echo "worker/wrangler.toml is missing (copy wrangler.toml.example and fill it in)." >&2
  exit 1
fi
git fetch -q origin main
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "This checkout is not at origin/main. Run: git checkout main && git pull" >&2
  exit 1
fi
if ! git diff --quiet HEAD -- . || [ -n "$(git ls-files --others --exclude-standard -- .)" ]; then
  echo "worker/ has uncommitted changes; deploy only committed code." >&2
  exit 1
fi

commit="$(git rev-parse --short=12 HEAD)"
npx --yes wrangler@4 d1 migrations apply skatedeals-alerts --remote
npx --yes wrangler@4 deploy --var "GIT_COMMIT:${commit}"
echo "Deployed ${commit}. Check: curl -s \"\$(grep '^PUBLIC_API_URL' wrangler.toml | cut -d'\"' -f2)/v1/health\""
