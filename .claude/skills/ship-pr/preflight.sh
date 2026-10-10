#!/usr/bin/env bash
# Mechanical pre-commit checks for ship-pr. Run from the repo root AFTER staging:
#   bash .claude/skills/ship-pr/preflight.sh
# Prints PASS / WARN / FAIL per check; exits 1 if anything FAILed.

fail=0
pass() { echo "PASS  $1"; }
warn() { echo "WARN  $1"; }
bad()  { echo "FAIL  $1"; fail=1; }

branch=$(git branch --show-current)
case "$branch" in
  main|develop|"") bad "on '$branch' — create a feature branch first" ;;
  *) pass "branch is $branch" ;;
esac

git fetch --prune -q origin
if git merge-base --is-ancestor origin/develop HEAD; then
  pass "branch contains current origin/develop"
else
  warn "branch is not built on current origin/develop — fine only if it is stacked on another PR; say which"
fi

staged=$(git diff --cached --name-only)
if [ -z "$staged" ]; then
  bad "nothing staged — git add the files by path"
else
  pass "staged: $(echo "$staged" | tr '\n' ' ')"
fi

forbidden=$(echo "$staged" | grep -E '(^|/)\.env$|settings\.local\.json$')
if [ -n "$forbidden" ]; then
  bad "never commit: $forbidden"
else
  pass "no .env or settings.local.json staged"
fi

unstaged=$(git status --porcelain | grep -E '^( M|\?\?)' | cut -c4-)
[ -n "$unstaged" ] && warn "left out of this commit: $(echo "$unstaged" | tr '\n' ' ')"

# Credential-shaped literals in added lines (GitGuardian flags these even when fake).
secrets=$(git diff --cached -U0 | grep -E '^\+[^+]' | grep -inE \
  -e "(password|passwd|secret|api_?key|token)[\"']?[[:space:]]*[:=][[:space:]]*[\"'][^\"'\$]{3,}[\"']" \
  -e '^\+[[:space:]]*[A-Z_]*PASSWORD:[[:space:]]*[^[:space:]$#]' \
  -e '[a-z+]+://[^/[:space:]:@]+:[^/[:space:]@]+@')
if [ -n "$secrets" ]; then
  bad "credential-shaped literal(s) in staged diff (GitGuardian will flag them):"
  echo "$secrets" | sed 's/^/        /'
else
  pass "no credential-shaped literals in staged diff"
fi

exit $fail
