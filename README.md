# todo-jira-sync

Bidirectionally sync a **Jira** project with a **Todo+** plain-text file — the
format used by the [`vscode-todo-plus`](https://github.com/fabiospampinato/vscode-todo-plus)
extension. Edit your backlog as a flat, version-controllable text file in your
editor while having things sync in Jira.

Scaffolded from [`tedivm/robs_awesome_python_template`](https://github.com/tedivm/robs_awesome_python_template)
conventions (uv, `pyproject.toml`, Typer, Pydantic Settings, Ruff, mypy,
pytest, GitHub Actions).

## Mapping rules

Each non-blank, non-comment line maps to one Jira issue, by indentation and the
trailing colon:

| Todo+ line                                   | Jira issue type |
|----------------------------------------------|-----------------|
| ends with `:`, **no** leading indent         | **Epic**        |
| ends with `:`, **indented**                  | **User Story**  |
| a task (`☐` / `✔` / `✘` …)                    | **Task**        |
| a task **nested under another task**         | **Sub-task**    |

```text
Authentication:                 ← Epic
  Login flow:                   ← Story    (parent: Authentication)
    ☐ Build the login form      ← Task     (parent: Login flow)
    ☐ Add OAuth providers       ← Task     (parent: Login flow)
      ☐ Google provider         ← Sub-task (parent: Add OAuth providers)
  ☐ Password reset email        ← Task     (parent: Authentication)
```

A node's Jira parent is its **nearest enclosing container**: a Task takes the
Story it sits under, or the Epic if there is no enclosing Story; a Story takes
its Epic; a Sub-task takes the Task it sits under.

### Status mapping

| Todo+ symbol            | Status        | Jira category        |
|-------------------------|---------------|----------------------|
| `☐` `[ ]`               | To Do         | *new*                |
| `@started(...)`         | In Progress   | *indeterminate*      |
| `✔` `✓` `[x]`           | Done          | *done*               |
| `✘` `[-]` `@cancelled`  | Cancelled     | *done* + cancelled status name |

Jira has no "cancelled" status *category*; cancelled is detected by status
**name** (configurable via `CANCELLED_STATUS_NAMES`).

### How identity works

Each synced line gets a `@jira(KEY)` tag written back into the file (inserted
*before* the trailing colon for projects, so it still reads as a project):

```text
Authentication @jira(WEB-1):
  ☐ Build the login form @jira(WEB-3)
```

That tag is the stable anchor — rename a line freely and the link survives.

## Install

Requires Python ≥ 3.10. Using [uv](https://docs.astral.sh/uv/):

```bash
uv venv
uv pip install -e ".[dev]"
```

or with pip:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Configure

Copy `.env.example` to `.env` and fill in your details:

```bash
cp .env.example .env
```

For Jira Cloud, create an API token at
<https://id.atlassian.com/manage-profile/security/api-tokens> and set
`JIRA_EMAIL` + `JIRA_API_TOKEN` with `JIRA_AUTH=basic`. For Server/Data Center,
use a personal access token with `JIRA_AUTH=bearer`.

## Use

```bash
# See what would happen — touches nothing:
todo-jira-sync status --todo todo.todo --project WEB

# Full bidirectional sync:
todo-jira-sync sync --todo todo.todo --project WEB

# One-way only:
todo-jira-sync push    # local file -> Jira (never edits the file)
todo-jira-sync pull    # Jira -> local file (never creates/edits Jira)

# Conflict policy when both sides changed the same field:
todo-jira-sync sync --conflict jira   # jira | todo | skip
```

A JSON sidecar `todo.todo.todojira.json` is written next to your file. It is
the 3-way-merge baseline (the common ancestor) — keep it, but it need not be
committed (it is git-ignored by default).

## How sync decides (3-way merge)

For each issue the engine compares the **live file** and **live Jira** against
the **baseline** from the last run:

- only the file changed → **push** to Jira
- only Jira changed → **pull** into the file
- both changed the same field → **conflict**, resolved by `--conflict`
- new in file → **created** in Jira (parents first)
- new in Jira → **pulled** into the file (under the right parent)
- gone from Jira but known → kept locally and reported (never silently lost)

The engine **never deletes Jira issues** and **never deletes local lines**.

## Docker

A multi-stage, uv-based image is included. It builds the package into a slim
runtime image whose entrypoint is the CLI, running as a non-root user.

```bash
# Build (VERSION is only needed because versioning comes from git tags):
docker build --build-arg VERSION=0.1.0 -t todo-jira-sync .

# Run against a working directory that holds your todo file and .env:
docker run --rm --env-file .env -v "$PWD:/work" todo-jira-sync \
  sync --todo todo.todo --project WEB
```

Or via Compose (put your `todo` file and `.env` in `./work`):

```bash
docker compose run --rm sync status
docker compose run --rm sync sync --todo todo.todo --project WEB
```

Prebuilt multi-arch images (amd64 + arm64) are published to GitHub Container
Registry by CI on version tags (and on demand via the workflow's manual
trigger).

## Releasing

Versioning is derived from git tags via `setuptools-scm`. Pushing a tag like
`v0.1.0` triggers two workflows: one builds the sdist/wheel and publishes to
PyPI (via OIDC Trusted Publishing — no API token stored), the other builds and
pushes the multi-arch container image. CI (`ci.yaml`) runs ruff, mypy and
pytest on a Python 3.10–3.14 matrix for every push and PR.

## Develop

```bash
make check     # ruff + mypy + pytest
make test
```

The sync core (`config`, `models`, `todo_format`, `state`, `sync`) is pure
standard library, so the tests run against an in-memory fake Jira with no
network and no live credentials. The two test files also run standalone:

```bash
python tests/test_todo_format.py
python tests/test_sync.py
```

## License

MIT — see [LICENSE](LICENSE).
