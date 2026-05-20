"""Dependency-free configuration for the sync core.

This module deliberately avoids any third-party imports so that the parser,
serializer and sync engine can be imported and unit-tested without installing
``pydantic`` or ``requests``. The Typer CLI builds a :class:`FormatConfig` from
the richer :class:`todo_jira_sync.settings.Settings` (which reads the
environment), but the engine only ever sees this plain dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Conflict resolution strategies when both sides changed the same field.
CONFLICT_JIRA = "jira"  # Jira wins
CONFLICT_TODO = "todo"  # local todo file wins
CONFLICT_SKIP = "skip"  # leave both untouched and report


@dataclass(frozen=True)
class FormatConfig:
    """Everything the parser/serializer/engine needs, with safe defaults.

    The default symbol sets match the *out of the box* Todo+ configuration
    (``☐`` / ``✔`` / ``✘``) plus the common bracket forms so that files written
    in either style round-trip. Bare single-character TaskPaper symbols
    (``-`` / ``x`` / ``+``) are intentionally excluded by default because they
    produce false positives on ordinary prose lines; enable them explicitly if
    you use TaskPaper mode.
    """

    # --- Todo+ syntax -----------------------------------------------------
    box_symbols: tuple[str, ...] = ("\u2610", "[ ]")  # ☐
    done_symbols: tuple[str, ...] = ("\u2714", "[x]", "[X]", "\u2713")  # ✔ ✓
    cancelled_symbols: tuple[str, ...] = ("\u2718", "[-]")  # ✘
    indent_unit: str = "  "  # Todo+ default `todo.indentation`
    tab_size: int = 4  # how wide a literal TAB is when measuring indentation

    # --- Jira issue-type names (per your project's scheme) ----------------
    type_epic: str = "Epic"
    type_story: str = "Story"
    type_task: str = "Task"
    type_subtask: str = "Sub-task"

    # --- Jira status mapping ---------------------------------------------
    # Status *names* that should be treated as "cancelled" when pulled from
    # Jira (Jira has no cancelled status *category*; it is Done + a resolution).
    cancelled_status_names: tuple[str, ...] = (
        "Cancelled",
        "Canceled",
        "Won't Do",
        "Won't Fix",
        "Rejected",
    )

    # --- Sync behaviour ---------------------------------------------------
    conflict: str = CONFLICT_JIRA
    # When a key exists in the saved state and in Jira but no longer in the
    # todo file, treat that as a local deletion. If True, re-add it to the todo
    # file on the next pull; if False, drop it silently (never touches Jira).
    pull_locally_deleted: bool = False

    @property
    def canonical_box(self) -> str:
        return self.box_symbols[0]

    @property
    def canonical_done(self) -> str:
        return self.done_symbols[0]

    @property
    def canonical_cancelled(self) -> str:
        return self.cancelled_symbols[0]

    def all_symbols(self) -> list[str]:
        """All recognised leading symbols, longest first (for matching)."""
        symbols = [*self.box_symbols, *self.done_symbols, *self.cancelled_symbols]
        return sorted(set(symbols), key=len, reverse=True)
