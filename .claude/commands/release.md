---
model: claude-sonnet-4-6
---

# release

Ship the current branch to `main` as a versioned GitHub release.

**Usage:** `/release` or `/release "v1.5.0 Beta 2"`

If a release title is provided as an argument, use it directly. Otherwise ask
the user for it before proceeding.

---

## Step 1 — Collect inputs

Ask the user (if not already provided):

1. **Release title** — human-readable, e.g. `v1.5.33 Beta 1` or
   `v1.5.0 — Survey Forms & Bug Fixes`. This becomes the GitHub release title.
2. **Pre-release type** — one of `stable`, `beta`, `alpha`, `rc`.
   Stable releases are not marked pre-release on GitHub.

Confirm both before continuing.

---

## Step 2 — Verify working tree

```bash
git status
git branch --show-current
```

The working tree must be clean (no uncommitted changes) and not on `main`.
If there are uncommitted changes, stop and tell the user to commit or stash
them first.

---

## Step 3 — Run the update-docs workflow

Complete **all steps** in the `/update-docs` skill now, plus one addition:

- Understand what changed (Step 1)
- Bump the patch version in `world_codes.py` and `fastapi/app.py` — `/update-docs`
  only does this when the schema changed (its Step 6a0); `/release` always cuts a
  new version, so do this bump now regardless of whether the schema changed.
- Identify and update affected docs (Steps 3–5)
- Check and update the JSON schema (Step 6) — if it changed, follow the full
  maintenance-release path (6a–6c), which will already include the version bump
  above in its commit; if it didn't change, fold the version bump into the
  Step 9 commit instead
- Update RELEASE-NOTES.md and docs/release-v1.4.0.md (Step 7)
- Update context files and session-history (Step 8)
- Commit (Step 9); push the branch

Record the new `APP_VERSION` (e.g. `1.5.34`) — you will need it for the tag.

---

## Step 4 — Determine the release tag

Read `APP_VERSION` from `src/traveller_gen/world_codes.py` after the bump.

Construct the tag based on the pre-release type supplied in Step 1:

| Type | Tag format | Example |
|---|---|---|
| `stable` | `vX.Y.Z` | `v1.5.34` |
| `beta` | `vX.Y.Z-beta1` | `v1.5.34-beta1` |
| `alpha` | `vX.Y.Z-alpha.1` | `v1.5.34-alpha.1` |
| `rc` | `vX.Y.Z-rc1` | `v1.5.34-rc1` |

If an existing tag of the same base already exists (e.g. `v1.5.34-beta1`),
increment the suffix counter (`-beta2`, `-beta3`, …).

```bash
git tag -l "vX.Y.Z*"    # check for collisions
```

---

## Step 5 — Merge to main

Create a pull request from the current branch into `main`, then merge it:

```bash
BRANCH=$(git branch --show-current)
gh pr create \
  --base main \
  --head "$BRANCH" \
  --title "<release title>" \
  --body "$(cat RELEASE-NOTES.md | head -60)"

# Confirm the PR number, then merge
gh pr merge <PR number> --merge --delete-branch=false
```

After merging, switch to `main` and pull:

```bash
git checkout main
git pull origin main
```

---

## Step 6 — Create the GitHub release

```bash
PRERELEASE_FLAG=""
if [ "<pre-release type>" != "stable" ]; then
  PRERELEASE_FLAG="--prerelease"
fi

gh release create <tag> \
  --title "<release title>" \
  --notes "$(cat RELEASE-NOTES.md | sed '/^---$/q' | head -80)" \
  $PRERELEASE_FLAG \
  --repo Elured-code/traveller-world-gen
```

The `release: types: [created]` trigger fires the `build-binaries` workflow
automatically. The merge to `main` in Step 5 will have already triggered
`azure-deploy`, `docker-publish`, `typecheck`, and `dependency-audit`.

Note the tag name — you will need it if a re-release is required.

---

## Step 7 — Monitor CI

List all workflow runs triggered by the merge and the release:

```bash
# Give GitHub ~15 seconds to register the new runs, then list
gh run list --repo Elured-code/traveller-world-gen --limit 15
```

Identify all in-progress runs. For each run, wait for completion:

```bash
gh run watch <run-id> --repo Elured-code/traveller-world-gen
```

Run watches in sequence (build-binaries has multiple parallel jobs — check
each platform). You can watch multiple runs concurrently by launching each
`gh run watch` call, but wait for all before proceeding to Step 8.

The expected workflows triggered per release are:

| Workflow | Trigger | Typical duration |
|---|---|---|
| `typecheck` | push to main | ~2 min |
| `dependency-audit` | push to main | ~1 min |
| `azure-deploy` | push to main | ~3 min |
| `docker-publish` | push to main | ~4 min |
| `build-binaries` | release created | ~10 min |

---

## Step 8 — Evaluate results

Once all runs complete, list their final statuses:

```bash
gh run list --repo Elured-code/traveller-world-gen --limit 15
```

**If all workflows succeed:** the release is complete. Report the release URL
to the user:

```bash
gh release view <tag> --repo Elured-code/traveller-world-gen --web
```

**If any workflow failed:** proceed to Step 9.

---

## Step 9 — Fix failures and re-release

For each failed workflow:

### 9a — Diagnose

```bash
gh run view <run-id> --repo Elured-code/traveller-world-gen --log-failed
```

Read the failure output carefully. Common failures and their fixes:

| Failure | Likely cause | Action |
|---|---|---|
| `build-binaries` — PyInstaller error | Missing module in spec `datas` or `hiddenimports` | Fix the `.spec` file |
| `build-binaries` — test failure | Broken import or packaging issue | Fix the source |
| `typecheck` — pyright error | Type annotation broken by recent change | Fix the annotation |
| `dependency-audit` — CVE | New vulnerability in a dependency | Pin or upgrade the dep |
| `azure-deploy` — publish failure | Azure secret expired or wrong app name | Inform user — needs manual intervention |
| `docker-publish` — build failure | Dockerfile or requirements issue | Fix the relevant file |

### 9b — Fix on main

Check out `main` (you should already be there) and apply the fix:

```bash
git checkout main
# ... make the fix ...
git add <files>
git commit -m "fix: <description of fix>"
git push origin main
```

Do **not** bump the version again — the version was already bumped in Step 3.

### 9c — Delete the failed release and tag

```bash
gh release delete <tag> --repo Elured-code/traveller-world-gen --yes
git tag -d <tag>
git push origin --delete <tag>
```

### 9d — Re-release

Go back to **Step 6** with the same tag and release title. The `release: [created]`
event will re-trigger `build-binaries` with the fixed code on `main`.

Then repeat Steps 7–8 until all workflows pass.

---

## Step 10 — Final report

When everything is green, report to the user:

- Release URL
- Tag name and version string (including build number from CI)
- Which workflows passed
- Any issues encountered and how they were resolved
