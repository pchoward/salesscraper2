#!/usr/bin/env bash
# Put one PR's screenshots on the ci-previews branch so the PR comment can
# show them inline (the repository is public, so raw URLs render in the
# GitHub app). The branch is a single commit, force-pushed each time, holding
# only open PRs' latest screenshots: it never grows, and it is never merged
# or served by Pages.
#
#   ci/publish_screenshots.sh SHOTS_DIR PR_NUMBER HEAD_SHA
# Needs GH_TOKEN and REPO. Writes base=<raw URL prefix> to $GITHUB_OUTPUT.
set -euo pipefail
shots="$1"
number="$2"
sha="$3"
branch="ci-previews"
short="${sha:0:7}"

if ! compgen -G "$shots/*.png" >/dev/null; then
  echo "No screenshots to publish."
  exit 0
fi

work="$(mktemp -d)"
auth="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)"
git_() { git -C "$work" -c http.extraheader="$auth" "$@"; }
git_ init -q
git_ remote add origin "https://github.com/${REPO}.git"
if git_ fetch -q --depth 1 origin "$branch" 2>/dev/null; then
  git_ checkout -q FETCH_HEAD
fi

# Drop screenshots of PRs that are no longer open.
open_prs="$(gh api --paginate "repos/${REPO}/pulls?state=open&per_page=100" --jq '.[].number')"
for dir in "$work"/pr-*; do
  [ -d "$dir" ] || continue
  grep -qx "${dir##*/pr-}" <<<"$open_prs" || rm -rf "$dir"
done

rm -rf "$work/pr-$number"
mkdir -p "$work/pr-$number/$short"
cp "$shots"/*.png "$work/pr-$number/$short/"
printf '%s\n' \
  "Screenshots for open pull requests, written by the \"CI - Publish PR Preview\" workflow." \
  "Rewritten as a single commit on every run; never merged into main and not part of the site." \
  > "$work/README.md"

git_ checkout -q --orphan snapshot
git_ add -A
git_ -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
  commit -q -m "PR preview screenshots $(date -u '+%Y-%m-%d %H:%M')"
git_ push -q --force origin "snapshot:refs/heads/$branch"
# Link through the branch, not this commit: the next run replaces the
# commit, but keeps every open PR's folder. The path names the PR's head
# commit, so a new push gets new URLs (no stale cached images).
echo "base=https://raw.githubusercontent.com/${REPO}/${branch}/pr-${number}/${short}" >> "${GITHUB_OUTPUT:-/dev/null}"
echo "Published screenshots for PR #$number on $branch."
