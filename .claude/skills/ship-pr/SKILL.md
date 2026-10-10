---
name: ship-pr
description: Commit checked work and open a pull request to develop — branch/base check, tests, secret pre-check, docs, Conventional Commit, push, gh pr create, and confirming CI is green. Only when Felipe types /ship-pr after he has checked the work.
disable-model-invocation: true
---

# Shipping a PR

Precondition: Felipe has checked the work and said OK. If he hasn't, stop and hand it over for his check instead. Never merge a PR — merging is his.

Each step ends with a check. Stop at the first one that fails and tell him why.

## 1. Stage by path

`git status`, then `git add <path> ...` for exactly the files this change owns. Never `git add .` / `-A`: the tree may hold another session's work or personal files.

## 2. Preflight

```bash
bash .claude/skills/ship-pr/preflight.sh
```

Expected: no `FAIL` lines. It checks the branch isn't `main`/`develop`, the base is current `origin/develop` (a `WARN` is fine for a stacked PR — say which PR it stacks on), nothing like `.env` or `settings.local.json` is staged, and no credential-shaped literals are in the diff. A flagged literal must be rewritten (blank value, trust auth, `make_url`, assembled at runtime) — GitGuardian scans every commit, and a later fix commit does not clear it.

## 3. Tests

```bash
docker compose exec backend pytest
```

Expected: all pass. Also confirm the PR adds tests for what it changes, and every new route is in `tests/test_auth.py`'s protected-routes list.

## 4. Docs follow the code

- CLAUDE.md, if the architecture, a route, the schema or the ETL changed.
- `.env.example`, if a `Settings` field was added.

Stage any doc changes by path and re-run preflight.

## 5. Commit

Conventional Commits (`feat:`, `fix:`, `chore:`, `test:`, `refactor:`), subject in the imperative, body explaining *why*. End with the attribution trailer from the current system reminder.

## 6. Push and open the PR

```bash
git push -u origin <branch>
gh pr create --base develop --head <branch> --title "<commit subject>" --body "..."
```

Always pass `--head` — without it `gh` can resolve the wrong branch. Use `--base <other-branch>` only for a stacked PR. Body sections: **What**, **Why**, **Notable** (decisions and trade-offs), **Verification** (what was run, test count), then the PR attribution footer.

## 7. Hand over

Paste the full PR URL, then:

```bash
gh pr checks <number> --watch
```

Expected: every check passes, CI and GitGuardian included. Report the result. Update the roadmap memory with the PR number.
