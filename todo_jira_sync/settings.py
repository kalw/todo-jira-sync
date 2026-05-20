"""Environment-driven settings (the only place ``pydantic`` is imported).

The sync engine itself is dependency-free and only ever sees a plain
:class:`todo_jira_sync.config.FormatConfig`. This module is the bridge: it
reads ``JIRA_*`` / ``TODO_*`` variables from the environment (or a local
``.env`` file) and produces both the credentials needed to build a
:class:`todo_jira_sync.jira_client.RestJiraClient` and a ``FormatConfig`` for
the parser/serializer.

Keeping this isolated means ``import todo_jira_sync.sync`` never drags in
pydantic, so the core can be unit-tested with the standard library alone.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .config import CONFLICT_JIRA, FormatConfig


def _csv(value: str) -> tuple[str, ...]:
    """Parse a comma-separated override into a tuple, dropping blanks."""
    return tuple(part.strip() for part in value.split(",") if part.strip())


class Settings(BaseSettings):
    """All configuration, read from the environment / ``.env``.

    Only ``jira_url`` and a token (plus an email for Basic auth) are strictly
    required; everything else has a sensible default that matches a vanilla
    Todo+ install and a conventional Jira project scheme.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- connection -------------------------------------------------------
    jira_url: str = Field(default="", description="Base URL, e.g. https://acme.atlassian.net")
    jira_email: str | None = Field(default=None, description="Account email (Basic auth)")
    jira_api_token: str = Field(default="", description="API token or PAT")
    jira_auth: str = Field(default="basic", description="'basic' (Cloud) or 'bearer' (Server/DC PAT)")

    # --- what to sync -----------------------------------------------------
    jira_project: str = Field(default="", description="Project key, e.g. WEB")
    todo_file: str = Field(default="todo.todo", description="Path to the Todo+ file")

    # --- behaviour --------------------------------------------------------
    conflict: str = Field(default=CONFLICT_JIRA, description="jira | todo | skip")
    pull_locally_deleted: bool = Field(default=False)

    # --- Jira issue-type names -------------------------------------------
    type_epic: str = "Epic"
    type_story: str = "Story"
    type_task: str = "Task"
    type_subtask: str = "Sub-task"

    # --- Todo+ syntax overrides (comma-separated) ------------------------
    box_symbols: str = ""
    done_symbols: str = ""
    cancelled_symbols: str = ""
    indent_unit: str = "  "
    cancelled_status_names: str = ""

    # ---------------------------------------------------------------------
    def format_config(self) -> FormatConfig:
        """Build the dependency-free config the engine consumes."""
        defaults = FormatConfig()
        return FormatConfig(
            box_symbols=_csv(self.box_symbols) or defaults.box_symbols,
            done_symbols=_csv(self.done_symbols) or defaults.done_symbols,
            cancelled_symbols=_csv(self.cancelled_symbols) or defaults.cancelled_symbols,
            indent_unit=self.indent_unit or defaults.indent_unit,
            type_epic=self.type_epic,
            type_story=self.type_story,
            type_task=self.type_task,
            type_subtask=self.type_subtask,
            cancelled_status_names=(
                _csv(self.cancelled_status_names) or defaults.cancelled_status_names
            ),
            conflict=self.conflict,
            pull_locally_deleted=self.pull_locally_deleted,
        )

    def require(self, *names: str) -> None:
        """Raise a friendly error if any required setting is empty."""
        missing = [n for n in names if not getattr(self, n)]
        if missing:
            joined = ", ".join(m.upper() for m in missing)
            raise SystemExit(f"Missing required configuration: {joined} (set it in .env or the environment)")
