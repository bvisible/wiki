# Git Configuration

## Branch de production
- **Branche:** `version-15`
- **Remote:** `origin` (bvisible)

## Upstream (lecture seule)
- **Repo:** https://github.com/frappe/wiki.git
- **Remote:** `upstream`
- **Branche upstream:** `master`
- **Usage:** Pull uniquement pour sync les mises à jour officielles

## Règles
1. TOUJOURS push sur `origin`, JAMAIS sur `upstream`
2. Pour sync: `git fetch upstream && git merge upstream/master`
3. Branch de travail: `version-15`

## Build pipeline (commit-the-build)

⚠️ **Ne jamais lancer `yarn build` ou `bench build --app wiki` localement sur un serveur Neoffice** (4 GB RAM → OOM-kill garanti). Le build se fait UNIQUEMENT sur GitHub Actions (ubuntu-latest, 16 GB RAM).

### Comment ça marche

1. Modif d'un fichier source (`frontend/...`) en local → `git commit` → `git push origin version-15`. **Ne pas builder localement.**
2. Le workflow `.github/workflows/build-frontend.yml` détecte le push, lance `yarn build` sur ubuntu-latest (~1-2 min) et commit les artefacts back avec un commit `[skip-build] frontend artifacts for <SHA>` (par `github-actions[bot]`).
3. Sur les instances clients, le pipeline d'update fait `git pull` (ramène ton commit + le commit du bot). Quand `bench build --app wiki` tourne, il appelle `yarn build` à la racine — **le `package.json` voit les artefacts déjà présents et skip vite** (gate). Plus d'OOM-kill.

### Paths spécifiques

- **Source frontend** : `frontend/`
- **Artefacts vite (commités)** : `wiki/public/frontend/`
- **SPA HTML(s) (commités)** : `wiki/www/wiki-app.html` (v3 : la SPA d'édition a
  déménagé de `/wiki` vers `/wiki-app`, l'ancien `wiki.html` a disparu)
- **Build script root** : `yarn (`yarn tailwind:build && cd frontend && yarn build`)`

### Forcer un rebuild local (si vraiment nécessaire)

```bash
FORCE_REBUILD=1 yarn build
```

### Documentation complète

- Doc canonique : `bvisible/neoffice-devops:main` → `docs/COMMIT-BUILD-PATTERN.md`
- Doc batch migration (12 apps) : même fichier, sections "Apps that have adopted the pattern" + "Edge cases discovered"
- Vault Obsidian : `[[NORA/04-savoir-faire/drive-frontend-build-pattern]]`

### Edge cases spécifiques à wiki

- Idem lms : stub `common_site_config.json` créé par le workflow.

---

# Notes amont (frappe/wiki)

Conservées du CLAUDE.md upstream. ⚠️ La section « Pull Requests » d'origine
demandait d'ignorer le fork et de pousser sur `frappe/wiki` : elle est réécrite
ci-dessous pour notre contexte (on pousse sur `origin`, PR amont seulement pour
contribuer un correctif générique).

## About

Frappe Wiki (Version 3), is a modern Wiki product built on Frappe Framework and Frappe UI (VueJS).

## IMPORTANT

Always load and user frappe-app-dev skills.

## Development Details

Unless mentioned, the site is wiki.localhost with Administrator/admin credentials.

## Planning / Spec-ing

Use Tracer bullets comes from the Pragmatic Programmer. When building systems, you want to write code that gets you feedback as quickly as possible. Tracer bullets are small slices of functionality that go through all layers of the system, allowing you to test and validate your approach early. This helps in identifying potential issues and ensures that the overall architecture is sound before investing significant time in development.

## Implementation Guidelines

* Create a new branch before working on a new feature/spec (branch name patterns: feat/, fix/, just like conventional commit pre-fixes)
* Reconcile the spec and log the progress after each phase of development
* Commit after each meaningful phase
* Commit the spec before the development commits
* Use comments only when necessary to explain "why?" not "how?", how must be clear from the code itself

## Frontend / Backend Sync

* Whenever a new field is added to a backend DocType that is surfaced in the frontend (e.g. settings panels), it must also be handled in the corresponding frontend component so the two stay in sync. This is a convention/reminder only — there is no automatic syncing mechanism; the frontend enumerates fields explicitly.

## Regression tests

* When we fix a bug, add at the very least a Unit test, and verify before/after by temp revert of fix to make sure the test tests what is intended
* For bigger features/workflows, e2e playwright tests are a must.

## Pull Requests

* Notre repo canonique est `bvisible/wiki` (`origin`), branche `version-15` —
  on y pousse directement, sans PR. `upstream` (`frappe/wiki`) est en lecture
  seule et sert à récupérer les releases amont.
* Contribuer un correctif générique en amont (facultatif) : brancher depuis
  `upstream/develop`, pousser la branche sur `upstream`, PR contre `develop`,
  et vérifier que le diff ne contient que tes fichiers
  (`git diff --stat upstream/develop..<branch>`).
* Keep pull request descriptions stupid simple
* Some formats:
    1. h2 Problem (1-2 sentences), h2 Solution: good for bugs, etc.
    2. h2 Why? h2 What? h2 How?: good for new features and enhancements
