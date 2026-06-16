---
model: claude-haiku-4-5-20251001
---

# update-docs

Update all project documentation to reflect the most recent code changes, then
commit. Run this after any session that modifies source code.

If a session number is provided as an argument (e.g. `/update-docs 83`), use it
as the current session number. Otherwise infer the session number from the last
entry in `context/session-history.md`.

---

## Step 1 — Understand what changed

Run these commands to establish what changed since the last commit:

```bash
git log --oneline -5
git diff HEAD~1 HEAD --stat
```

Then read the full diff of every modified **source** file (`.py`, `.html`,
`.json`) so you know exactly what was added, changed, or removed.

---

## Step 2 — Identify which docs need updating

Use this routing table (mirrors the CLAUDE.md routing table):

| Modified source file | Docs / context files to update |
|---|---|
| `traveller_world_physical.py` | `docs/traveller_world_physical_explained.md`, `context/system-world.md` |
| `traveller_world_detail.py` | `docs/traveller_world_detail_explained.md`, `context/detail-moon.md` |
| `traveller_world_gen.py` | `docs/traveller_world_gen_explained.md` |
| `tables.py` | `docs/tables_explained.md` |
| `traveller_system_gen.py` | `docs/traveller_system_gen_explained.md`, `context/system-world.md` |
| `traveller_stellar_gen.py` | `docs/traveller_stellar_gen_explained.md`, `context/stellar-orbit.md` |
| `traveller_orbit_gen.py` | `docs/traveller_orbit_gen_explained.md`, `context/stellar-orbit.md` |
| `traveller_moon_gen.py` | `docs/traveller_moon_gen_explained.md`, `context/detail-moon.md` |
| `traveller_belt_physical.py` | `docs/traveller_belt_physical_explained.md`, `context/detail-moon.md` |
| `traveller_hydro_detail.py` | `docs/traveller_hydro_detail_explained.md`, `context/system-world.md` |
| `traveller_map_fetch.py` | `docs/traveller_map_fetch_explained.md`, `context/map-fetch.md` |
| `system_map.py` | `docs/system_map_explained.md`, `context/system-map.md` |
| `function_app.py` | `context/api-layer.md` |
| `shared/helpers.py` | `context/api-layer.md` |
| `gen-ui/app.py` | `context/gen-ui.md` |
| `traveller_world_schema.json` | `docs/release-v1.4.0.md` (JSON schema table) |
| Any data-structure change | `context/data-structures.md` |

Always update regardless of what changed:
- `context/session-history.md` — add one row for this session
- `RELEASE-NOTES.md` — append to the current draft section
- `docs/release-v1.4.0.md` — update test count and feature list
- `v1.4-new-features.txt` — add any user-facing features (see format below)
- `CLAUDE.md` — update `**Last updated:**` line and session number

---

## Step 3 — Update the explained docs

For each `docs/*_explained.md` that needs updating:

1. Read the current file.
2. Edit only the sections that describe changed behaviour — do not rewrite
   content that is still accurate.
3. If a new public function was added, add it to the **Key methods** table.
4. If a new field was added to a dataclass, add it to the code snippet in the
   relevant section.
5. If the pipeline changed, update the pipeline diagram.
6. Keep the beginner-friendly tone — these docs explain the *why*, not just the
   *what*.

---

## Step 4 — Update v1.4-new-features.txt

This file is the user-facing "what's new" list for non-technical readers. It
lives in the project root alongside `v1.3-new-features.txt`.

**Format rules:**
- One entry per user-visible change (new feature, changed display, removed
  display element, or notable bug fix).
- Entry heading in ALL CAPS, followed by a blank line and plain-English
  paragraphs. No bullet points inside a paragraph; use dashes (`-`) for lists.
- Present tense, no jargon. Assume the reader has not seen the code.
- Append new entries **above** the BUG FIXES section.
- Add bug fixes inside the BUG FIXES section.
- Do NOT remove existing entries.

**What belongs here:**
- New UI rows or cards in the world card or system HTML
- New checkboxes or controls in gen-ui
- Behaviour changes visible to the user (e.g. a temperature now includes
  seismic heating; a display field was removed)

**What does NOT belong here:**
- Internal refactors with no visible effect
- Test additions
- Context/doc-only changes

---

## Step 5 — Check and update traveller_world_schema.json

Read `traveller_world_schema.json` and compare it against the current source
code. Update it if any of the following changed:

- A field was **added** to `World`, `WorldDetail`, `WorldPhysical`,
  `BeltPhysical`, `Moon`, `OrbitSlot`, `Star`, or `SystemOrbits` and is emitted
  by `to_dict()` but not yet in the schema.
- A field was **removed** from `to_dict()` — remove it from the schema too.
- A field's **type or constraints** changed (e.g. an `int` became `Optional[int]`,
  a minimum value changed).

**Do not add** fields that are only used internally and never appear in JSON
output. Only properties emitted by `to_dict()` / `to_json()` belong in the schema.

### If the schema changed — create a maintenance release

When `traveller_world_schema.json` is modified, a maintenance release is
required (schema changes are a contract change for API consumers).

**5a. Determine the new version.**

Read the current `APP_VERSION` from `world_codes.py` (line ~81). Increment the
**patch** digit: `1.4.0` → `1.4.1`, `1.4.1` → `1.4.2`, etc.

**5b. Bump `APP_VERSION` in `world_codes.py`.**

Edit the single `APP_VERSION = "X.Y.Z"` line with the new version string.

**5c. Create `docs/release-vX.Y.Z.md`.**

Copy the structure from the previous maintenance release file (e.g.
`docs/release-v1.4.0.md`) and write a short release note listing:
- The schema fields added, removed, or changed
- The test count (from `pytest tests/ -q`)
- A "Schema changes" table in the same format used in `docs/release-v1.4.0.md`

**5d. Commit the version bump as a separate commit** (this is the only case
where `/update-docs` commits source code):

```bash
git add world_codes.py traveller_world_schema.json docs/release-vX.Y.Z.md
git commit -m "chore: bump version to vX.Y.Z — schema update"
```

**5e. Tag and publish the release:**

```bash
git tag vX.Y.Z
git push origin v1.4.0       # push the branch
git push origin vX.Y.Z       # push the tag
gh release create vX.Y.Z \
    --title "vX.Y.Z — Schema update" \
    --notes "$(cat docs/release-vX.Y.Z.md)" \
    --repo Elured-code/traveller-world-gen
```

After completing steps 5a–5e, continue with Step 6 (the docs commit will
include the updated `docs/release-vX.Y.Z.md` if it was not already staged).
If the schema did **not** change, skip 5a–5e entirely.

---

## Step 6 — Update RELEASE-NOTES.md and docs/release-v1.4.0.md

`RELEASE-NOTES.md` is the AI-context release log (detailed, technical).
`docs/release-v1.4.0.md` is the human-facing release document.

For each change:
1. Add a `## Feature Name (Session N)` section to the **top** of the draft area
   in `RELEASE-NOTES.md` (below the header block, above any existing draft
   sections).
2. Update the test count in both files to match the current passing total
   (`pytest tests/ -q` last line).
3. In `docs/release-v1.4.0.md`, add any new JSON schema fields to the schema
   table and update the test coverage table.

---

## Step 7 — Update context files

For each context file that needs updating:

- `context/data-structures.md` — add/remove/rename fields as they changed.
- `context/session-history.md` — add one row: `| Session N | YYYY-MM-DD | one-line description |`
- Module-specific context files — update public function signatures and
  behavioural notes that changed.

---

## Step 8 — Commit

Stage only documentation and context files — never source code:

```bash
git add CLAUDE.md RELEASE-NOTES.md v1.4-new-features.txt
git add context/*.md
git add docs/*.md
git add .claude/commands/*.md        # if the command file itself was updated
git add traveller_world_schema.json  # if the schema was updated in Step 5
```

Commit message format:
```
docs: update explained guides, context, and new-features for session N
```

If multiple sessions are covered: `sessions N–M`.

Run `git push origin v1.4.0` after committing.
