"""Tests for the bidirectional sync engine.

Runs under pytest, or standalone: ``python tests/test_sync.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from tests.fake_jira import FakeJira
from todo_jira_sync.config import CONFLICT_SKIP, CONFLICT_TODO, FormatConfig
from todo_jira_sync.models import Status
from todo_jira_sync.state import BaseEntry, SyncState
from todo_jira_sync.sync import sync

BOX, DONE = "\u2610", "\u2714"


def CLOCK() -> datetime:
    return datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc)


def _sync(text, jira, state=None, **kw):
    return sync(
        text,
        project="WEB",
        client=jira,
        state=state or SyncState.empty("WEB"),
        now_fn=CLOCK,
        **kw,
    )


def test_create_pushes_full_hierarchy_with_parents():
    jira = FakeJira()
    text = (
        "Website:\n"
        f"  Auth:\n"
        f"    {BOX} Login\n"
        f"      {BOX} Google\n"
    )
    res = _sync(text, jira)
    ops = [c[0] for c in jira.calls]
    assert ops.count("create") == 4
    # Epic created first, subtask last; parents wired correctly.
    epic = jira.issues["WEB-1"]
    story = jira.issues["WEB-2"]
    login = jira.issues["WEB-3"]
    google = jira.issues["WEB-4"]
    assert (epic.issue_type, epic.parent_key) == ("Epic", None)
    assert (story.issue_type, story.parent_key) == ("Story", "WEB-1")
    assert login.issue_type == "Task" and login.parent_key == "WEB-2"  # task -> enclosing story
    assert google.issue_type == "Sub-task" and google.parent_key == "WEB-3"  # -> task
    # Keys are written back into the todo file.
    assert "@jira(WEB-1)" in res.todo_text and "@jira(WEB-4)" in res.todo_text
    # Freshly created issues must not be misreported as missing in Jira.
    assert not any(a.op == "JIRA_GONE" for a in res.actions)


def test_task_parents_to_nearest_container_story_or_epic():
    """A Task under a Story parents to the Story; under an Epic, to the Epic."""
    jira = FakeJira()
    text = (
        "Authentication:\n"
        f"  Login flow:\n"
        f"    {BOX} Build the login form\n"
        f"    {BOX} Add OAuth providers\n"
        f"      {BOX} Google provider\n"
        f"  {BOX} Password reset email\n"
    )
    _sync(text, jira)
    by_summary = {i.summary: i for i in jira.issues.values()}
    auth = by_summary["Authentication"]
    flow = by_summary["Login flow"]
    build = by_summary["Build the login form"]
    oauth = by_summary["Add OAuth providers"]
    google = by_summary["Google provider"]
    reset = by_summary["Password reset email"]

    assert (auth.issue_type, auth.parent_key) == ("Epic", None)
    assert (flow.issue_type, flow.parent_key) == ("Story", auth.key)
    assert (build.issue_type, build.parent_key) == ("Task", flow.key)  # task -> story
    assert (oauth.issue_type, oauth.parent_key) == ("Task", flow.key)  # task -> story
    assert (google.issue_type, google.parent_key) == ("Sub-task", oauth.key)
    assert (reset.issue_type, reset.parent_key) == ("Task", auth.key)  # task -> epic (no story)


def test_done_task_is_created_then_transitioned():
    jira = FakeJira()
    _sync(f"P:\n  {DONE} finished thing\n", jira)
    assert jira.issues["WEB-2"].status is Status.DONE
    assert any(c[0] == "set_status" for c in jira.calls)


def test_local_edit_is_pushed_when_jira_unchanged():
    jira = FakeJira()
    jira.seed("WEB-1", "old title", issue_type="Task")
    state = SyncState("WEB", {"WEB-1": BaseEntry("old title", "todo", "task")})
    res = _sync(f"P:\n  {BOX} new title @jira(WEB-1)\n", jira, state)
    assert jira.issues["WEB-1"].summary == "new title"
    assert any(a.op == "UPDATE_SUMMARY" for a in res.actions)


def test_jira_edit_is_pulled_when_todo_unchanged():
    jira = FakeJira()
    jira.seed("WEB-1", "renamed in jira", issue_type="Task")
    state = SyncState("WEB", {"WEB-1": BaseEntry("original", "todo", "task")})
    res = _sync(f"P:\n  {BOX} original @jira(WEB-1)\n", jira, state)
    assert "renamed in jira" in res.todo_text
    assert any(a.op == "PULL_SUMMARY" for a in res.actions)


def test_jira_done_is_pulled_into_todo_symbol():
    jira = FakeJira()
    jira.seed("WEB-1", "task", status=Status.DONE, issue_type="Task")
    state = SyncState("WEB", {"WEB-1": BaseEntry("task", "todo", "task")})
    res = _sync(f"P:\n  {BOX} task @jira(WEB-1)\n", jira, state)
    assert DONE in res.todo_text
    assert "@done(26-05-20 09:00)" in res.todo_text


def test_conflict_jira_wins_by_default():
    jira = FakeJira()
    jira.seed("WEB-1", "jira version", issue_type="Task")
    state = SyncState("WEB", {"WEB-1": BaseEntry("base", "todo", "task")})
    res = _sync(f"P:\n  {BOX} todo version @jira(WEB-1)\n", jira, state)
    assert "jira version" in res.todo_text
    assert res.conflicts and "Jira wins" in res.conflicts[0].detail


def test_conflict_todo_wins_when_configured():
    jira = FakeJira()
    jira.seed("WEB-1", "jira version", issue_type="Task")
    state = SyncState("WEB", {"WEB-1": BaseEntry("base", "todo", "task")})
    _sync(
        f"P:\n  {BOX} todo version @jira(WEB-1)\n",
        jira,
        state,
        cfg=FormatConfig(conflict=CONFLICT_TODO),
    )
    assert jira.issues["WEB-1"].summary == "todo version"


def test_conflict_skip_preserves_baseline():
    jira = FakeJira()
    jira.seed("WEB-1", "jira version", issue_type="Task")
    state = SyncState("WEB", {"WEB-1": BaseEntry("base", "todo", "task")})
    res = _sync(
        f"P:\n  {BOX} todo version @jira(WEB-1)\n",
        jira,
        state,
        cfg=FormatConfig(conflict=CONFLICT_SKIP),
    )
    # Neither side written; baseline kept so the conflict re-surfaces next run.
    assert jira.issues["WEB-1"].summary == "jira version"
    assert "todo version" in res.todo_text
    assert res.state.entries["WEB-1"].summary == "base"


def test_pull_new_jira_issue_into_todo_under_parent():
    jira = FakeJira()
    jira.seed("WEB-1", "Epic", issue_type="Epic")
    jira.seed("WEB-2", "child story", issue_type="Story", parent_key="WEB-1")
    res = _sync("Epic @jira(WEB-1):\n", jira)
    assert "child story" in res.todo_text
    assert any(a.op == "PULL_NEW" and a.key == "WEB-2" for a in res.actions)


def test_local_deletion_is_respected_not_resurrected():
    jira = FakeJira()
    jira.seed("WEB-1", "deleted locally", issue_type="Task")
    state = SyncState("WEB", {"WEB-1": BaseEntry("deleted locally", "todo", "task")})
    res = _sync("P:\n", jira, state)  # WEB-1 no longer in the file
    assert "WEB-1" not in res.todo_text
    assert "WEB-1" not in res.state.entries
    assert any(a.op == "LOCAL_DELETE" for a in res.actions)


def test_dry_run_makes_no_jira_calls():
    jira = FakeJira()
    res = _sync(f"P:\n  {BOX} new\n", jira, dry_run=True)
    assert jira.calls == []
    assert any(a.op == "CREATE" for a in res.actions)


def test_push_direction_does_not_pull():
    jira = FakeJira()
    jira.seed("WEB-1", "jira changed", issue_type="Task")
    state = SyncState("WEB", {"WEB-1": BaseEntry("base", "todo", "task")})
    res = _sync(
        f"P:\n  {BOX} base @jira(WEB-1)\n", jira, state, direction="push"
    )
    # push-only: todo wins, jira overwritten, todo text keeps local value
    assert jira.issues["WEB-1"].summary == "base"
    assert "jira changed" not in res.todo_text


def test_full_cycle_is_stable():
    """Sync, feed the output back with persisted state -> no further actions."""
    jira = FakeJira()
    text = f"Epic:\n  Story:\n    {BOX} Task\n      {BOX} Sub\n"
    res1 = _sync(text, jira)
    res2 = sync(
        res1.todo_text, project="WEB", client=jira, state=res1.state, now_fn=CLOCK
    )
    mutating = [a for a in res2.actions if a.op not in ("JIRA_GONE",)]
    assert mutating == [], f"unexpected second-pass actions: {mutating}"


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
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(funcs) - failed}/{len(funcs)} passed")
    sys.exit(1 if failed else 0)
