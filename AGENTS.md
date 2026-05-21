# AGENTS.md

Guidance for AI coding agents (and humans) working in this repo.

## What this is

A bidirectional sync between a **Jira** project and a **Todo+** text file
(the format used by the `fabiospampinato/vscode-todo-plus` VS Code extension).

## Architecture (important)

The package is split so the **sync core has zero third-party dependencies** and
can be unit-tested with the standard library alone:

| Module            | Depends on        | Purpose                                              |
|-------------------|-------------------|------------------------------------------------------|
| `config.py`       | stdlib only       | `FormatConfig` dataclass + conflict constants        |
| `models.py`       | stdlib only       | `Node`, `JiraIssue`, `NodeKind`, `Status`            |
| `todo_format.py`  | stdlib only       | `parse()`, `serialize()`, `resolve_jira_parents()`   |
| `state.py`        | stdlib only       | JSON sidecar baseline for 3-way merge                |
| `sync.py`         | stdlib only       | the 3-way merge engine: `sync(...) -> SyncResult`    |
| `jira_client.py`  | `requests` (lazy) | `RestJiraClient` against Jira Cloud REST v3          |
| `settings.py`     | `pydantic-settings` | env/`.env` -> `FormatConfig` + credentials         |
| `cli.py`          | `typer`           | `sync` / `push` / `pull` / `status` commands         |

**Rule:** never import `requests`, `pydantic`, or `typer` from the core
modules (`config`, `models`, `todo_format`, `state`, `sync`). Keep them at the
edges (`jira_client`, `settings`, `cli`).

## Mapping rules

- Line ending with `:` at column 0 -> **Epic**
- Indented line ending with `:` -> **User Story**
- A Todo+ task (leading box/done/cancelled symbol) -> **Task**
- A task nested under another task -> **Sub-task**
- Identity anchor is the `@jira(KEY)` tag, written back into the file.

A node's Jira **parent** is its nearest enclosing container: Task -> enclosing
Story (or Epic if none); Story -> Epic; Sub-task -> the Task it sits under
(deeper nesting collapses onto that Task, since Jira forbids sub-task-of-sub-task).

## Jira API note

Uses `POST /rest/api/3/search/jql` with `nextPageToken` pagination. The legacy
`/rest/api/3/search` endpoint was removed by Atlassian and must **not** be
reintroduced. `fields` must be requested explicitly (the default is now `id`).

## Tests

```bash
pytest                       # via uv/pip-installed pytest
python tests/test_sync.py    # also runs standalone, no pytest needed
python tests/test_todo_format.py
```

The engine is tested against `tests/fake_jira.py`, an in-memory double — no
live Jira is required.

## Build, container & CI

uv is used everywhere (Makefile, Dockerfile, workflows). The image is a
multi-stage build: a `uv pip install` build stage and a slim runtime stage
whose entrypoint is the `todo-jira-sync` CLI. Versioning is `setuptools-scm`
(git tags); pass `--build-arg VERSION=...` to the Docker build since the build
context has no `.git`. GitHub Actions: `ci.yaml` (ruff + mypy + pytest, py3.10
–3.14), `publish-pypi.yaml` (sdist/wheel to PyPI via OIDC on `v*` tags) and
`publish-docker.yaml` (multi-arch image to GHCR on `v*` tags / manual dispatch).
Dependabot tracks pip, github-actions and docker.

## Git workflow

**All changes must go through a pull request. Never push directly to `main`.**

### Branch naming

```
<type>/<short-description>
```

| Type | When to use |
|------|-------------|
| `feat` | new user-facing behaviour |
| `fix` | bug fix |
| `ci` | workflow / pipeline changes |
| `docs` | documentation only |
| `refactor` | code restructure, no behaviour change |
| `test` | test additions or fixes |
| `chore` | maintenance (deps, config, tooling) |

Examples: `feat/add-pull-command`, `fix/sync-edge-case`, `ci/faster-matrix`.

### Commit messages — Conventional Commits (enforced)

Every commit is validated by `commitlint.yaml` on every PR:

```
<type>(<optional scope>): <subject>

<optional body>

<optional footer>   ← put BREAKING CHANGE: here for major bumps
```

Examples:
```
feat(cli): add --dry-run flag to pull command
fix(sync): handle missing @jira tag gracefully
ci: cache uv downloads between matrix jobs
```

The commit type drives the **semver bump** when a release is cut:

| Commits since last release | Version bump |
|----------------------------|-------------|
| at least one `feat` | minor (`1.2.0 → 1.3.0`) |
| only `fix` / `perf` | patch (`1.2.0 → 1.2.1`) |
| any with `BREAKING CHANGE:` footer | major (`1.2.0 → 2.0.0`) |
| `chore`, `ci`, `docs`, `style`, … | no release |

### Standard agent flow

```bash
# 1. Start on a branch — always.
git checkout -b <type>/<description>

# 2. Make changes, commit with a conventional message.
git add <specific files>   # never `git add -A` (avoids accidental .env commits)
git commit -m "type(scope): subject"

# 3. Push and open a PR. --fill uses the branch name and first commit as defaults.
git push -u origin HEAD
gh pr create --fill
```

**Do not** `git push origin main`. If working on an existing PR branch, push to
that branch and let CI run before requesting review.

### Release flow (fully automated)

Merging any PR to `main` triggers `release.yaml`, which runs
[release-please](https://github.com/googleapis/release-please). Release-please
opens or updates a **Release PR** titled `chore(main): release X.Y.Z` that:

- Bumps `version.txt` to the next semver
- Regenerates `CHANGELOG.md` from the accumulated conventional commits

Merging that Release PR:

1. Creates the `vX.Y.Z` git tag
2. Creates the GitHub Release with CHANGELOG and Docker/PyPI artifact links
3. Triggers `publish-docker.yaml` → multi-arch image pushed to GHCR
4. Triggers `publish-pypi.yaml` → sdist + wheel published to PyPI via OIDC

**Do not** create version tags or GitHub Releases by hand.
