"""Tests for the Todo+ parser and serializer.

Runs under pytest, or standalone: ``python tests/test_todo_format.py``.
"""

from __future__ import annotations

from todo_jira_sync.config import FormatConfig
from todo_jira_sync.models import NodeKind, Status
from todo_jira_sync.todo_format import parse, serialize

BOX, DONE, CANCEL = "\u2610", "\u2714", "\u2718"


def _kinds(text):
    return [(n.kind, n.title) for n in parse(text).issues()]


def test_epic_vs_story_by_indentation():
    text = "Top epic:\n  Nested story:\n"
    nodes = list(parse(text).issues())
    assert nodes[0].kind is NodeKind.EPIC
    assert nodes[1].kind is NodeKind.STORY


def test_task_then_subtask_when_scaffolded():
    text = f"Proj:\n  {BOX} Parent task\n    {BOX} Child subtask\n"
    nodes = list(parse(text).issues())
    assert nodes[1].kind is NodeKind.TASK
    assert nodes[2].kind is NodeKind.SUBTASK


def test_sibling_tasks_are_not_subtasks():
    # Regression: a task following a deeper task must not inherit "subtask".
    text = f"Proj:\n  {BOX} A\n    {BOX} A1\n  {BOX} B\n"
    nodes = list(parse(text).issues())
    by_title = {n.title: n.kind for n in nodes}
    assert by_title["A"] is NodeKind.TASK
    assert by_title["A1"] is NodeKind.SUBTASK
    assert by_title["B"] is NodeKind.TASK


def test_leading_symbol_wins_over_trailing_colon():
    text = f"{BOX} Remember this:\n"
    node = next(parse(text).issues())
    assert node.kind is NodeKind.TASK
    assert node.title == "Remember this:"


def test_status_from_symbols():
    text = f"P:\n  {BOX} a\n  {DONE} b\n  {CANCEL} c\n"
    statuses = [n.status for n in parse(text).issues() if n.kind is NodeKind.TASK]
    assert statuses == [Status.TODO, Status.DONE, Status.CANCELLED]


def test_started_tag_makes_in_progress():
    text = f"P:\n  {BOX} a @started(26-01-01 09:00)\n"
    task = [n for n in parse(text).issues() if n.kind is NodeKind.TASK][0]
    assert task.status is Status.IN_PROGRESS
    assert task.started_at == "26-01-01 09:00"


def test_jira_key_extracted_from_task_and_project():
    text = f"Epic name @jira(WEB-1):\n  {BOX} task @jira(WEB-2)\n"
    epic, task = list(parse(text).issues())
    assert epic.jira_key == "WEB-1" and epic.title == "Epic name"
    assert task.jira_key == "WEB-2" and task.title == "task"


def test_unmanaged_tags_are_preserved():
    text = f"P:\n  {BOX} ship it @today @est(2h) @jira(WEB-9)\n"
    task = [n for n in parse(text).issues() if n.kind is NodeKind.TASK][0]
    assert task.title == "ship it"
    assert task.tags == ["@today", "@est(2h)"]
    assert task.jira_key == "WEB-9"


def test_comments_and_blanks_preserved_verbatim():
    text = "P:\n  # a note\n\n  " + BOX + " task\n"
    out = serialize(parse(text))
    assert "# a note" in out
    assert "\n\n" in out


def test_roundtrip_is_idempotent():
    text = (
        f"Website:\n"
        f"  Auth @jira(WEB-1):\n"
        f"    {BOX} login @jira(WEB-2)\n"
        f"    {BOX} oauth @started(26-05-20 09:00) @jira(WEB-3)\n"
        f"      {DONE} apple @done(26-05-19 18:00) @jira(WEB-5)\n"
        f"  {CANCEL} legacy @jira(WEB-6)\n"
        f"{BOX} standalone @high @jira(WEB-7)\n"
    )
    first = serialize(parse(text))
    second = serialize(parse(first))
    assert first == second

    def sig(root):
        return [
            (n.kind, n.status, n.jira_key, n.jira_parent_key, n.title, tuple(n.tags))
            for n in root.issues()
        ]

    assert sig(parse(text)) == sig(parse(first))


def test_tabs_count_as_indentation():
    cfg = FormatConfig()
    text = f"P:\n\t{BOX} tab-indented subtask-of-nothing\n"
    nodes = list(parse(text, cfg).issues())
    assert nodes[1].kind is NodeKind.TASK  # under project P, so a Task


if __name__ == "__main__":
    import sys

    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in funcs:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{len(funcs) - failed}/{len(funcs)} passed")
    sys.exit(1 if failed else 0)
