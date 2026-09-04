# Neoffice fork markers — manifest

Every change we make to code we did not write carries a `//// Neoffice` comment
that says **why** (see `CLAUDE.md`, rule "mark every change to code that is not
ours"). At the next upstream merge, `grep -rn "////"` must give the complete map
of our intent versus theirs.

Some changes cannot carry a comment: a JSON DocType, an image, a `.po`, a
generated bundle, a symlink, an attribute in the middle of a multi-line opening
tag. **This file is their marker.** `scripts/fork_markers.py` (from
`bvisible/neoffice-ci`) treats a non-commentable file as marked once this
manifest names its full path.

---

## wiki

`bvisible/wiki`, branch `version-15` · upstream `frappe/wiki`.

### The base, and how it was established

Do not trust the branch name: this fork does **not** descend from
`upstream/master`, and its merge-base with `upstream/develop` is not where our
divergence starts either. What actually happened:

| Fact | Value |
| --- | --- |
| **BASE** | `0a6025159289bcdaae26d727ada34764370ac765` — *"Merge pull request #730 from frappe/develop"*, 2026-07-28 |
| Where BASE lives | tip-of-the-line we merged: contained in `upstream/version-3` **and** in `origin/version-15` (`git merge-base --is-ancestor` says yes for both) |
| Why it is the true base | its tree (`5802a89b…`) is **byte-identical** to `upstream/develop`'s `df34ebf388` — the merge took upstream's tree wholesale, so `BASE..HEAD` is exactly our post-merge divergence |
| `upstream/master` | stale v2 line (tip `2372f85`, 2025-12-18); merge-base with us is `0432467`, 2025-11-24 — **not** our base |
| `upstream/develop` | tip `67fef5e` (2026-09-04); merge-base with us is `df34ebf388` = BASE's tree |
| `upstream/version-3` | tip `3ce7fe9` (2026-09-02), **36 commits ahead of BASE** — this is what the next merge brings |

The August 2026 "wiki v3" merge is commit `11c5340` (*merge: frappe/wiki v3.0.0
into version-15*), 493 upstream commits.

### Attribution — proof, not assumption

* `git rev-list origin/version-15 ^BASE` = **92 commits** (9 of them merges).
* **65** of those 92 are reachable from no upstream ref → genuinely ours
  (`git rev-list … --not --remotes=upstream`).
* The other **27** are upstream's, dated 2025-09-18 → 2025-11-24, all from the
  old `master` (v2) line, pulled into this branch by a later merge of
  `upstream/master`. They are divergence **from `version-3`'s point of view**
  and will conflict, so they are marked as such rather than claimed:
  `wiki/wiki/doctype/wiki_page/sqlite_search.py` (upstream `4885211`, *"fix: add
  retry logic to search"*) is the one that survived into a code hunk.
* `(cherry picked from commit …)`: **0** occurrences — nothing here is a
  backport.
* Authors of the 92: Jérémy Christillin 56 (+1), Rucha Mahabal 22,
  github-actions[bot] 4, neoservice 3, 18alantom / Rushabh Mehta / Sidhanth
  Rathod / Vishwajeet Singh Thakur / siduck / Daniel 1 each.
* `git blame` (without `-w`) was run on every unmarked hunk to source its
  reason; hunks whose blame lands on the merge commit `11c5340` are
  conflict-resolution lines and say so.

### Counts

| | code hunks | marked | unmarked | non-commentable files |
| --- | --- | --- | --- | --- |
| **Before** (HEAD = `aeeba48`) | 168 | 85 | 83 | 7 |
| **After** | 168 | 154 | 14 | 7 (named below) |

The 85 pre-existing markers came with the v3 merge and the fixes that followed
it; they were kept verbatim. The 14 that remain are listed below — every one of
them is a place where a comment cannot physically go.

---

### Non-commentable files — this manifest is their marker

#### `wiki/wiki/doctype/wiki_space/wiki_space.json`

* **Added field `public_read`** (Check, default `0`, in the *Access control*
  section): *"Readable without an account"*. Requires
  `Wiki Settings.enable_public_wiki`; ticking it adds the Guest role to the
  space's role table, unticking removes it. This is the switch that makes a
  client wiki public — **the single most important divergence in this file**.
* **`field_order` re-shuffled** (general/navbar/logo/access-control blocks
  reordered, `main_revision` moved). This is desk form-builder drift, not a
  decision: at the next merge, take upstream's order and re-insert `public_read`
  after `access_control_section`.
* Trailing newline added at EOF (upstream ships none).

#### `wiki/wiki/doctype/wiki_settings/wiki_settings.json`

* **Added section `public_access_section`** + **added field `enable_public_wiki`**
  (Check, default `0`): *"Allow access without an account"*. Off by default —
  a fresh instance's wiki is private until someone says otherwise. It is the
  master switch above `Wiki Space.public_read`.
* **`field_order` re-shuffled** (`javascript` / `section_break_mmtu` /
  `feedback_tab` / `feedback_submission_limit` moved). Drift again — take
  upstream's order and re-insert the two new entries.

#### `wiki/wiki/doctype/wiki_group_item/wiki_group_item.json`

* **Added fields `published` and `allow_guest`** (Check, `default 0`,
  `fetch_from` `wiki_page.published` / `wiki_page.allow_guest`,
  `fetch_if_empty 1`, `in_list_view 1`). They surface the two flags in the *Wiki
  Sidebars* grid so a manager can publish or open a whole space from one screen.
  The write-back is `wiki/wiki/doctype/wiki_space/wiki_space.js` (marked there).
* `modified` bumped to 2026-02-23.

#### `wiki/wiki/doctype/wiki_page/wiki_page.json`

* `in_list_view: 1` added on **`published`** and on **`allow_guest`** — the two
  flags the sidebar grid needs.
* `make_attachments_public: 1`, `search_fields: "title"`, `row_format:
  "Dynamic"`, `modified` bumped: **framework re-serialisation**, not ours. Take
  upstream's values at the merge.
* Trailing newline added at EOF.

> **Merge advice for the four DocTypes above**: `public_read`,
> `enable_public_wiki`, `published` and `allow_guest` are field *additions* to
> core DocTypes. They belong in a fixture of Custom Fields (the way
> `neoffice_custom_fields` does it for erpnext), not in the upstream JSON —
> every upstream field edit conflicts with them today. Until that move, restore
> them by hand after each merge and check `field_order`.

#### `package.json`

* `"build"` is **gated**: it skips when `wiki/public/frontend/assets` already
  exists, unless `FORCE_REBUILD=1`. Instances have 4 GB of RAM and a real
  `yarn build` OOM-kills them; they pull the artifacts instead.
* Upstream's `"build"` is kept verbatim as **`"build:force"`**.
* `"_comment_neoffice"` is a dummy key holding the `////` marker, because JSON
  has no comments.

#### `neoffice-divergence.json`

Added file, generated. Inventory of every `//// Neoffice` marker block in the
tree; `scripts/neoffice-divergence.py` (also added, marked in its docstring)
fails CI when one disappears. Re-bless with
`python3 scripts/neoffice-divergence.py --update`. Nothing upstream to merge.

#### `wiki/locale/fr.po`, `wiki/locale/main.pot`

Added files: the French catalogue of the app and the reader (≈780 messages) and
the POT it is generated from. Upstream ships no `locale/` for this app. The tool
skips `locale/`; at a merge, regenerate the POT and re-run
`bench update-po-files` rather than resolving conflicts by hand.

---

### Committed build artifacts — mark the source, never the artifact

This fork uses **commit-the-build**: the instances pull compiled assets and never
run `yarn build`. The decision itself is marked at its source — `.gitignore`
(the lines that un-ignore them) and `package.json` (the gate). The artifacts
below carry no marker on purpose; a marker in them would be wiped by the next
build and silently turn the check red.

| Artifact | Built from |
| --- | --- |
| `wiki/public/frontend/**` (682 files: js, css, maps, fonts) | `frontend/` via vite, by `.github/workflows/build-frontend.yml` |
| `wiki/www/wiki-app.html` | same |
| `wiki/public/css/tailwind.css` | `wiki/public/css/main.css` via `yarn tailwind:build` |
| `wiki/public/css/frappe-ui-tokens.css`, `frappe-ui-prose.css`, `frappe-ui-code.css` | `scripts/generate-public-theme.mjs` / `-prose` / `-lucide`, via `yarn theme:generate` |
| `wiki/public/js/wiki-highlight.bundle.js` | `frontend/src/public/highlight.js` via `frontend/vite.highlight.config.js` |

`wiki/public/css/neoffice-wiki.css` is **not** in this list: it is hand-written
reader CSS of ours, carries its own header marker, and is loaded by
`wiki/templates/wiki/layout.html` (marked there).

> `fork_markers.py` recognises `wiki/public/frontend/**` as built output but not
> `wiki/public/css/*.css` nor `wiki/public/js/*.bundle.js`, so those five stay
> flagged on a full-history run. That is a gap in the tool, not an unmarked
> change.

---

### Unreachable hunks — a comment cannot go there

A comment may never sit **between the attributes of a multi-line opening tag**.
For each hunk below, the marker is on the enclosing element instead, and the
hunk is named here.

| Hunk | Change | Marker lives on |
| --- | --- | --- |
| `wiki/templates/wiki/includes/header.html` — `title=` of the space-switcher button | English string wrapped in `_()` | the `<button type="button">` above |
| `wiki/templates/wiki/includes/feedback_widget.html` — `placeholder=` of the comment textarea | idem | the `<textarea>` above |
| `wiki/templates/wiki/includes/mobile_header.html` — `aria-label=` of the floating nav trigger | idem | the `<button @click="toggleSidebar()">` above |
| `frontend/src/components/tiptap-extensions/ImageNodeView.vue` — `:width` attribute of `<img>` | removed: the width now goes through `:style`, so a resized image scales instead of being letterboxed | the `<img>` tag |
| `frontend/src/components/tiptap-extensions/ImageNodeView.vue` — `:style` / `@click` of `<img>` | `@click` re-pointed from `selectNode` to `handleImageClick` (select in edit mode, lightbox in read mode) | the `<img>` tag |
| `frontend/src/pages/SpaceDetails.vue` — `:readonly` of both `<SpaceTreePanel>` | was `isGitSynced`, now `isReadOnly` (git-synced **or** reader) | each `<SpaceTreePanel>` tag |
| `frontend/src/pages/SpaceDetails.vue` — `:spaces` of both `<SpaceTreePanel>` | added: feeds the header space switcher | each `<SpaceTreePanel>` tag |

### Not markable at all

* `wiki/public/node_modules` — a **symlink**, retargeted from an upstream
  developer's absolute path (`/Users/mdhussain/Frappe/benches/…`) to the
  relative `../../node_modules`. A symlink cannot hold a comment.
  ⚠️ Upstream has since **untracked this symlink entirely**
  (`6c5b6dc`, *"fix: untrack broken wiki/public/node_modules symlink"*): at the
  next merge, take the deletion — our fix becomes moot.

### Whitespace-only divergence — take upstream at the merge

* `.gitignore`, last line: trailing newline added (upstream ends the file
  without one). Marked, but there is nothing of ours to keep.
* `wiki/wiki/doctype/wiki_page/wiki_page.json` and `wiki_space.json`: same,
  trailing newline at EOF.

---

### Added files (no upstream equivalent)

Each carries a header marker unless noted.

| File | Purpose |
| --- | --- |
| `frontend/src/components/NeoCockpitBridge.vue` | mounts the shared Neoffice chrome |
| `frontend/src/components/NeoCockpitWikiSidebar.vue` | wiki flavour of the cockpit sidebar, falls back to upstream's `Sidebar.vue` |
| `scripts/neoffice-divergence.py` | the divergence guard (docstring carries the marker) |
| `wiki/frappe_wiki/patches/init_public_read_from_guest_role.py` | seeds `public_read` from the existing Guest role |
| `wiki/frappe_wiki/patches/redirect_bare_wiki_route_to_app.py` | per-instance `/wiki` redirect |
| `wiki/frappe_wiki/doctype/wiki_revision_item/patches/add_revision_doc_key_index.py` | index on `(revision, doc_key)` |
| `wiki/public/css/neoffice-wiki.css` | reader styling (wider article, image sizes, captions) |
| `wiki/frappe_wiki/patches/__init__.py` | **empty on purpose, unmarked** — a package marker, nothing to explain |

### `.github/` — listed here, never marked

`fork_markers.py` skips `.github/` in both directions: it refuses added lines
there even when they are comments, so a header marker cannot be written. All
five workflow files are ours, with no upstream equivalent:

| Workflow | What it does |
| --- | --- |
| `build-frontend.yml` | builds the SPA on GitHub and commits the artifacts back (commit-the-build) |
| `fork-markers.yml` | this discipline, run on every push to `version-15` |
| `neoffice-divergence.yml` | runs `scripts/neoffice-divergence.py` on push and PR |
| `tests.yml` | fleet CI (wave 2) via `bvisible/neoffice-ci` |
| `upstream-preview.yml` | weekly bench on upstream `frappe`/`erpnext` (tracker #138) |

---

### What the next merge will fight over

`upstream/version-3` is 36 commits ahead of BASE. Files touched on **both**
sides (ours: 67 source files, theirs: 44):

| File | Upstream's change | Ours |
| --- | --- | --- |
| `frontend/src/composables/useTheme.js` | `a7a9aef` *prevent flash while switching theme* | **rewritten wholesale** (OS-following theme) — expect a full-file conflict |
| `wiki/utils.py` | `dcc5592` *assign Wiki User role without triggering nested User.save()* | our early return that refuses the role to Website Users (WI-00297) — same function |
| `wiki/public/node_modules` | `6c5b6dc` *untrack the symlink* | our relative retarget — take the deletion |
| `wiki/templates/wiki/layout.html`, `document.html` | `1132fc8` *reader column widths on wide screens* | `neo-wiki-article` class + our CSS `<link>` + brand `<title>` |
| `wiki/templates/wiki/includes/toc.html`, `sidebar.html`, `mobile_header.html` | `bbcc5b6` editor TOC, `6bbefb9` per-space tab flag | i18n wrapping |
| `frontend/src/pages/SpaceDetails.vue` | per-space tabs, breadcrumbs, draft layout | the whole reader branch (`isReader`, public endpoints) |
| `frontend/src/components/WikiDocumentPanel.vue` | idem | reader branch + PDF button |
| `wiki/api/__init__.py`, `wiki/frappe_wiki/doctype/wiki_document/wiki_document.py` | v3 fixes | `allow_guest`, published-only endpoints, PDF, OG guard |
| `wiki/wiki/doctype/wiki_space/wiki_space.json` | field changes | `public_read` + reordered `field_order` |
| `.gitignore` | upstream keeps ignoring the build | we un-ignore it — **never take upstream's version blindly** |
| `package.json` (develop only) | script changes | the build gate |
| `wiki/patches.txt` (develop only) | new patches | our three patches |
