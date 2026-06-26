# Git Best Practices

Guide for working on **azure-ai-foudry-web-api** — branch strategy, daily commands, pull requests, and merging into `dev` and `main`.

---

## 1. Branch model

This repo uses a **feature-branch workflow**:

```text
main          ← production-ready, deployable
  ↑
dev           ← integration branch (optional but recommended)
  ↑
feature/*     ← your work (e.g. feature-fabric-data-agent)
```

| Branch | Purpose | Who merges here |
|--------|---------|-----------------|
| `feature/*` | One feature or fix per branch | You (via PR) |
| `dev` | Combined, tested work before production | Team lead / after PR review |
| `main` | Stable release line | After `dev` is verified (or direct from feature for small teams) |

**Current state:** the remote default branch is `main`. There is no `dev` branch yet — see [§8 Create a `dev` branch](#8-create-a-dev-branch-first-time) if you want one.

**Naming conventions**

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/<short-description>` | `feature-fabric-data-agent` |
| Bug fix | `fix/<short-description>` | `fix-fabric-timeout` |
| Docs / infra | `docs/...` or `infra/...` | `docs/git-practices` |

Use lowercase and hyphens. Keep names short but meaningful.

---

## 2. Daily workflow (feature branch)

### Start from latest `main` (or `dev`)

```bash
# Update local main
git checkout main
git pull origin main

# Create a new feature branch
git checkout -b feature/my-new-feature

# Or continue existing branch and sync with main
git checkout feature-fabric-data-agent
git fetch origin
git merge origin/main
# alternative: git rebase origin/main
```

### Work, stage, and commit

```bash
# See what changed
git status
git diff

# Stage only source/docs/tests — NOT __pycache__ or .env
git add src/ tests/ config/ Fabric-flow.md README.md

# Commit with a clear message (why, not just what)
git commit -m "$(cat <<'EOF'
Add Fabric error HTTP mapping and update docs.

Map not-found reasons to 400/404/502 and format mismatches to 422.
EOF
)"
```

### Push and open a PR

```bash
git push -u origin feature/my-new-feature

# Open PR in browser (GitHub CLI)
gh pr create --base dev --head feature/my-new-feature \
  --title "Add Fabric error HTTP mapping" \
  --body "$(cat <<'EOF'
## Summary
- Map Fabric errors to 400/404/422/502
- Document error responses in Fabric-flow.md

## Test plan
- [ ] uv run pytest -v
- [ ] Manual curl to /api/fabric/chat
EOF
)"
```

Use `--base main` instead of `--base dev` if you do not have a `dev` branch yet.

---

## 3. Commit best practices

### Do

- **One logical change per commit** — easy to review and revert.
- **Write messages in imperative mood:** “Add …”, “Fix …”, “Update …”.
- **First line ≤ 72 characters** — summary; optional body explains *why*.
- **Run tests before push:**

  ```bash
  uv run pytest -v
  ```

- **Stage intentionally** — review `git diff --cached` before commit.

### Do not

- Commit secrets (`.env`, API keys, tokens, `terraform.tfvars` with real values).
- Commit `__pycache__/`, `*.pyc`, `.venv/`, or local IDE junk.
- Commit broken code to `main` or `dev`.
- Use `git push --force` on `main` or `dev` (see [§7 Recovery](#7-recovery-and-conflicts)).

### Good commit message example

```text
Refine Fabric error HTTP mapping and document responses.

Map agent_unresolved to 400, unknown prompt/agent to 404,
upstream Fabric 404 to 502, and format mismatch to 422.
```

### Files to always exclude

Add these to `.gitignore` if not already present:

```gitignore
__pycache__/
*.py[cod]
.venv/
.env
*.tfvars
.pytest_cache/
```

If `__pycache__` was committed earlier, remove from tracking once:

```bash
git rm -r --cached src/__pycache__ tests/__pycache__
git commit -m "Stop tracking Python bytecode caches"
```

---

## 4. Pull request process

### Before opening a PR

1. Rebase or merge latest base branch (`dev` or `main`).
2. All tests pass locally.
3. No debug prints or commented-out code.
4. Docs updated if behavior changed (`Fabric-flow.md`, `README.md`, etc.).

### PR checklist

```markdown
## Summary
- What changed and why

## Test plan
- [ ] uv run pytest -v
- [ ] Manual API test (if applicable)
- [ ] Terraform validate (if infra changed)

## Notes
- Breaking changes, env vars, migration steps
```

### Review flow

```text
feature/my-branch  →  PR  →  dev  →  PR  →  main
                         ↑              ↑
                    code review    release / deploy
```

For a **small team or solo project**, it is acceptable to merge `feature/*` → `main` directly via PR, skipping `dev`.

---

## 5. Merge feature → `dev`

### Option A — Merge commit (recommended for shared branches)

Preserves full history; safe for `dev`.

```bash
git checkout dev
git pull origin dev

git merge --no-ff feature/my-new-feature -m "Merge feature/my-new-feature into dev"

git push origin dev
```

Or merge via **GitHub PR** (preferred): use “Create a merge commit” or “Squash and merge” depending on team preference.

| Merge type | When to use |
|------------|-------------|
| **Squash and merge** | One clean commit on `dev`; good for noisy feature history |
| **Merge commit** | Keep full branch history on `dev` |
| **Rebase and merge** | Linear history; use only if team agrees |

### Option B — Squash on GitHub

1. Open PR: `feature/my-new-feature` → `dev`
2. Click **Squash and merge**
3. Edit squash commit message
4. Delete feature branch after merge (GitHub option)

---

## 6. Merge `dev` → `main` (release)

When `dev` is tested and ready for production:

```bash
git checkout main
git pull origin main

git merge --no-ff dev -m "Release: merge dev into main"

git push origin main

# Tag releases (optional)
git tag -a v1.2.0 -m "Fabric error handling and routing"
git push origin v1.2.0
```

### Release checklist

- [ ] All CI checks green on `dev`
- [ ] `uv run pytest -v` passes
- [ ] Env vars / infra documented
- [ ] No open blockers on linked issues
- [ ] Deploy from `main` (Azure Web App, etc.)

### Hotfix (urgent fix on production)

Branch from `main`, not `dev`:

```bash
git checkout main
git pull origin main
git checkout -b fix/critical-bug

# fix, commit, push
git push -u origin fix/critical-bug

# PR: fix/critical-bug → main
# Then back-merge main into dev so dev stays in sync:
git checkout dev
git merge origin/main
git push origin dev
```

---

## 7. Recovery and conflicts

### Update feature branch with latest `main`

```bash
git checkout feature/my-new-feature
git fetch origin
git merge origin/main
# fix conflicts, then:
git add .
git commit -m "Merge main into feature/my-new-feature"
git push
```

### Rebase (linear history — use only on your feature branch)

```bash
git checkout feature/my-new-feature
git fetch origin
git rebase origin/main

# if conflicts:
#   fix files → git add . → git rebase --continue

git push --force-with-lease origin feature/my-new-feature
```

Use `--force-with-lease`, never bare `--force`, on feature branches only.

### Undo last commit (not pushed)

```bash
git reset --soft HEAD~1   # keep changes staged
git reset --hard HEAD~1   # discard changes (destructive)
```

### Discard local uncommitted changes

```bash
git restore path/to/file
git restore .              # all files (careful)
```

---

## 8. Create a `dev` branch (first time)

If you only have `main` today and want a `dev` integration branch:

```bash
git checkout main
git pull origin main

git checkout -b dev
git push -u origin dev
```

On GitHub: **Settings → Branches → Branch protection rules**

- Protect `main`: require PR, require status checks, no direct push.
- Optionally protect `dev`: require PR for merges from features.

Then use this flow:

```text
feature/*  →  PR  →  dev  →  PR  →  main
```

---

## 9. Useful commands reference

| Task | Command |
|------|---------|
| Current branch | `git branch --show-current` |
| All branches | `git branch -a` |
| Short log | `git log --oneline -10` |
| Diff vs main | `git diff main...HEAD` |
| Commits on branch | `git log main..HEAD --oneline` |
| Staged diff | `git diff --cached` |
| Unstage file | `git restore --staged path/to/file` |
| Remote URL | `git remote -v` |
| Fetch all | `git fetch origin` |
| PR status | `gh pr status` |
| List open PRs | `gh pr list` |
| Merge PR (CLI) | `gh pr merge <number> --squash` |

---

## 10. This project — quick reference

**Repository:** `https://github.com/swarnenducs/azure-ai-foudry-web-api.git`  
**Default branch:** `main`  
**Active feature branch:** `feature-fabric-data-agent`

### Typical flow for Fabric work

```bash
git checkout feature-fabric-data-agent
git pull origin feature-fabric-data-agent

# after changes + tests
git add src/ tests/ Fabric-flow.md README.md test-fabric.md
git commit -m "Describe your change"
git push origin feature-fabric-data-agent

gh pr create --base main --head feature-fabric-data-agent \
  --title "Fabric Data Agent integration" \
  --body "See Fabric-flow.md for architecture and test-fabric.md for tests."
```

### Pre-commit checklist (this repo)

```bash
uv run pytest -v
git status                    # no .env, no __pycache__
git diff --cached             # review staged files
git commit -m "Your message"
git push
```

---

## 11. Related docs

- [README.md](README.md) — setup and API overview
- [Fabric-flow.md](Fabric-flow.md) — Fabric architecture
- [test-fabric.md](test-fabric.md) — testing guide
- [infra/README.md](infra/README.md) — Terraform deploy
