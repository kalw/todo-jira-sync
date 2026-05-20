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
`publish-docker.yaml` (multi-arch image to GHCR on `main` and `v*` tags).
Dependabot tracks pip, github-actions and docker.
