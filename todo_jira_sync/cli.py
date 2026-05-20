"""Typer command-line interface.

Commands
--------
``sync``    Bidirectional sync (create, push and pull).
``push``    One-way: local todo file -> Jira (never edits the file from Jira).
``pull``    One-way: Jira -> local todo file (never creates/edits Jira).
``status``  Dry run: print what *would* happen, touching nothing.

All commands read connection details from the environment / ``.env`` via
:class:`todo_jira_sync.settings.Settings`, but every value can be overridden on
the command line. The todo file and its JSON state sidecar are only written
when not running in dry-run mode.

The options use the ``Annotated[...]`` Typer idiom (value defaults stay on the
parameter) so the signatures type-check cleanly under mypy.
"""

from pathlib import Path
from typing import Annotated

import typer

from .jira_client import RestJiraClient
from .settings import Settings
from .state import SyncState
from .sync import SyncResult, sync

app = typer.Typer(
    add_completion=False,
    help="Bidirectionally sync a Jira project with a Todo+ text file.",
)

# Reusable option annotations.
TodoOpt = Annotated[str | None, typer.Option("--todo", "-t", help="Path to the Todo+ file.")]
ProjectOpt = Annotated[str | None, typer.Option("--project", "-p", help="Jira project key.")]
ConflictOpt = Annotated[str | None, typer.Option("--conflict", "-c", help="jira | todo | skip.")]
DryRunOpt = Annotated[bool, typer.Option("--dry-run", help="Show actions without writing.")]


def _run(
    direction: str,
    dry_run: bool,
    todo: str | None,
    project: str | None,
    conflict: str | None,
) -> SyncResult:
    settings = Settings()
    if conflict:
        settings.conflict = conflict
    todo_path = todo or settings.todo_file
    project_key = project or settings.jira_project

    settings.require("jira_url", "jira_api_token")
    if not project_key:
        raise SystemExit(
            "Missing required configuration: JIRA_PROJECT (pass --project or set it in .env)"
        )

    path = Path(todo_path)
    if not path.exists():
        if direction == "push":
            raise SystemExit(f"Todo file not found: {todo_path}")
        path.write_text("", encoding="utf-8")  # first pull may create it
    todo_text = path.read_text(encoding="utf-8")

    cfg = settings.format_config()
    client = RestJiraClient(
        settings.jira_url,
        email=settings.jira_email,
        token=settings.jira_api_token,
        auth=settings.jira_auth,
        cfg=cfg,
    )
    state = SyncState.load(todo_path, project_key)

    result = sync(
        todo_text,
        project=project_key,
        client=client,
        state=state,
        cfg=cfg,
        direction=direction,
        dry_run=dry_run,
    )

    _report(result, dry_run)

    if not dry_run:
        path.write_text(result.todo_text, encoding="utf-8")
        result.state.save(todo_path)
        typer.secho(
            f"\nWrote {todo_path} and {SyncState.path_for(todo_path).name}",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho("\nDry run - nothing was written.", fg=typer.colors.YELLOW)
    return result


def _report(result: SyncResult, dry_run: bool) -> None:
    if not result.actions:
        typer.echo("Already in sync; no changes.")
        return
    for action in result.actions:
        color = {
            "CREATE": typer.colors.GREEN,
            "PUSH": typer.colors.CYAN,
            "PULL": typer.colors.BLUE,
            "SET_STATUS": typer.colors.CYAN,
            "CONFLICT": typer.colors.RED,
            "JIRA_GONE": typer.colors.MAGENTA,
        }.get(action.op, typer.colors.WHITE)
        typer.secho(str(action), fg=color)
    conflicts = result.conflicts
    if conflicts:
        typer.secho(
            f"\n{len(conflicts)} conflict(s) - resolved per policy.",
            fg=typer.colors.RED,
        )


@app.command(name="sync")
def sync_cmd(
    todo: TodoOpt = None,
    project: ProjectOpt = None,
    conflict: ConflictOpt = None,
    dry_run: DryRunOpt = False,
) -> None:
    """Bidirectional sync (default)."""
    _run("both", dry_run, todo, project, conflict)


@app.command()
def push(
    todo: TodoOpt = None,
    project: ProjectOpt = None,
    dry_run: DryRunOpt = False,
) -> None:
    """One-way: local todo file -> Jira."""
    _run("push", dry_run, todo, project, None)


@app.command()
def pull(
    todo: TodoOpt = None,
    project: ProjectOpt = None,
    dry_run: DryRunOpt = False,
) -> None:
    """One-way: Jira -> local todo file."""
    _run("pull", dry_run, todo, project, None)


@app.command()
def status(
    todo: TodoOpt = None,
    project: ProjectOpt = None,
) -> None:
    """Dry run: show what a bidirectional sync would do."""
    _run("both", True, todo, project, None)


def main() -> None:  # console-script entry point
    app()


if __name__ == "__main__":
    main()
