"""The bidirectional sync engine.

It is pure orchestration over four inputs - the parsed todo tree, the live Jira
issues, the saved baseline state and a :class:`JiraClient` - and emits a list of
:class:`Action` records describing exactly what it did (or, in ``dry_run`` mode,
what it *would* do).

Directions:

* ``both``  - true 3-way merge. A field is pushed when only the todo changed,
  pulled when only Jira changed, and flagged as a conflict (resolved per
  ``cfg.conflict``) when both changed.
* ``push``  - the todo file is authoritative; differences are written to Jira.
* ``pull``  - Jira is authoritative; differences are written to the todo file.

The engine never deletes Jira issues and never deletes local lines; a Jira issue
that vanished is reported (``JIRA_GONE``) and left in place for you to decide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import CONFLICT_JIRA, CONFLICT_SKIP, CONFLICT_TODO, FormatConfig
from .jira_client import JiraClient, issue_type_name, kind_from_type
from .models import JiraIssue, Node, NodeKind, Status
from .state import BaseEntry, SyncState
from .todo_format import parse, resolve_jira_parents, serialize

_CREATE_RANK = {
    NodeKind.EPIC: 0,
    NodeKind.STORY: 1,
    NodeKind.TASK: 1,
    NodeKind.SUBTASK: 2,
}


@dataclass
class Action:
    op: str
    key: str | None
    detail: str = ""

    def __str__(self) -> str:
        key = self.key or "-"
        return f"[{self.op}] {key} {self.detail}".rstrip()


@dataclass
class SyncResult:
    todo_text: str
    state: SyncState
    actions: list[Action] = field(default_factory=list)

    @property
    def conflicts(self) -> list[Action]:
        return [a for a in self.actions if a.op == "CONFLICT"]


def _now(now_fn) -> str:
    return now_fn().strftime("%y-%m-%d %H:%M")


def sync(
    todo_text: str,
    *,
    project: str,
    client: JiraClient,
    state: SyncState,
    cfg: FormatConfig | None = None,
    direction: str = "both",
    dry_run: bool = False,
    now_fn=lambda: datetime.now(timezone.utc),
) -> SyncResult:
    cfg = cfg or FormatConfig()
    root = parse(todo_text, cfg)
    actions: list[Action] = []
    new_entries: dict[str, BaseEntry] = {}

    jira_issues = client.search_issues(project)
    jira_by_key = {i.key: i for i in jira_issues}

    dry_counter = [0]

    # ------------------------------------------------------------------ #
    # Phase A: create todo-only issues in Jira (push side)
    # ------------------------------------------------------------------ #
    if direction in ("both", "push"):
        keyless = [n for n in root.issues() if not n.jira_key]
        keyless.sort(key=lambda n: _CREATE_RANK[n.kind])
        for node in keyless:
            parent_key = _resolve_parent_key(node)
            itype = issue_type_name(node.kind, cfg)
            if dry_run:
                dry_counter[0] += 1
                node.jira_key = f"NEW-{dry_counter[0]}"
                actions.append(
                    Action("CREATE", node.jira_key, f"{itype}: {node.title!r}")
                )
            else:
                key = client.create_issue(
                    project=project,
                    issue_type=itype,
                    summary=node.title,
                    parent_key=parent_key,
                )
                node.jira_key = key
                actions.append(Action("CREATE", key, f"{itype}: {node.title!r}"))
                if node.status is not Status.TODO:
                    client.set_status(key, node.status)
                    actions.append(Action("SET_STATUS", key, node.status.value))
            new_entries[node.jira_key] = _entry_from_node(node)
        resolve_jira_parents(root, cfg)  # refresh links now that keys exist

    todo_by_key = {n.jira_key: n for n in root.issues() if n.jira_key}

    # ------------------------------------------------------------------ #
    # Phase B: reconcile issues present on both sides
    # ------------------------------------------------------------------ #
    for key, node in list(todo_by_key.items()):
        if key in new_entries:  # just created this run; nothing to reconcile
            continue
        issue = jira_by_key.get(key)
        if issue is None:
            if key in state.entries and direction in ("both", "pull"):
                actions.append(
                    Action("JIRA_GONE", key, "missing in Jira; kept locally")
                )
            elif key not in state.entries:
                actions.append(
                    Action("JIRA_GONE", key, "unknown key; kept locally")
                )
            new_entries.setdefault(key, _entry_from_node(node))
            continue
        base = state.entries.get(key)
        _reconcile_pair(
            node, issue, base, cfg, direction, client, dry_run, actions,
            new_entries, now_fn,
        )

    # ------------------------------------------------------------------ #
    # Phase C: issues present in Jira but not in the todo file
    # ------------------------------------------------------------------ #
    if direction in ("both", "pull"):
        missing = [i for i in jira_issues if i.key not in todo_by_key]
        _pull_missing(
            missing, root, todo_by_key, state, cfg, dry_run, actions, new_entries
        )

    # ------------------------------------------------------------------ #
    # Finalise
    # ------------------------------------------------------------------ #
    resolve_jira_parents(root, cfg)
    new_state = SyncState(
        project=project,
        entries=new_entries,
        last_sync=now_fn().isoformat(),
    )
    return SyncResult(todo_text=serialize(root, cfg), state=new_state, actions=actions)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _resolve_parent_key(node: Node) -> str | None:
    if node.kind is NodeKind.SUBTASK:
        task = node.nearest_ancestor(NodeKind.TASK)
        return task.jira_key if task else None
    if node.kind in (NodeKind.STORY, NodeKind.TASK):
        container = node.nearest_ancestor(
            NodeKind.EPIC, NodeKind.STORY, NodeKind.TASK
        )
        return container.jira_key if container else None
    return None


def _entry_from_node(node: Node) -> BaseEntry:
    return BaseEntry(
        summary=node.title,
        status=node.status.value,
        issue_type=node.kind.value,
        parent_key=node.jira_parent_key,
    )


def _entry_from_issue(issue: JiraIssue, kind: NodeKind) -> BaseEntry:
    return BaseEntry(
        summary=issue.summary,
        status=issue.status.value,
        issue_type=kind.value,
        parent_key=issue.parent_key,
    )


def _reconcile_pair(
    node, issue, base, cfg, direction, client, dry_run, actions, new_entries, now_fn
) -> None:
    """Resolve summary and status for one matched (todo, jira) pair."""
    # If we have no baseline for a keyed issue, trust Jira as the source of
    # record for this run rather than risk clobbering it with stale local text.
    base_summary = base.summary if base else issue.summary
    base_status = base.status_enum() if base else issue.status

    agreed_summary = _merge_field(
        kind="summary",
        key=node.jira_key,
        todo_val=node.title,
        jira_val=issue.summary,
        base_val=base_summary,
        cfg=cfg,
        direction=direction,
        actions=actions,
        push=lambda v: None if dry_run else client.update_summary(node.jira_key, v),
        pull=lambda v: _set_title(node, v),
    )

    agreed_status = _merge_field(
        kind="status",
        key=node.jira_key,
        todo_val=node.status,
        jira_val=issue.status,
        base_val=base_status,
        cfg=cfg,
        direction=direction,
        actions=actions,
        push=lambda v: None if dry_run else client.set_status(node.jira_key, v),
        pull=lambda v: _set_status(node, v, now_fn),
    )

    # Note: node is mutated only by the pull lambda. For push / equal / skip the
    # node already holds the correct local value, so we never reassign here.
    new_entries[node.jira_key] = BaseEntry(
        summary=agreed_summary,
        status=agreed_status.value,
        issue_type=node.kind.value,
        parent_key=node.jira_parent_key,
    )


def _merge_field(
    *, kind, key, todo_val, jira_val, base_val, cfg, direction, actions, push, pull
):
    """Return the agreed value and perform the side effect for one field."""
    push_op = {"summary": "UPDATE_SUMMARY", "status": "SET_STATUS"}[kind]
    pull_op = {"summary": "PULL_SUMMARY", "status": "PULL_STATUS"}[kind]

    if direction == "push":
        if todo_val != jira_val:
            push(todo_val)
            actions.append(Action(push_op, key, _fmt(kind, todo_val)))
        return todo_val
    if direction == "pull":
        if todo_val != jira_val:
            pull(jira_val)
            actions.append(Action(pull_op, key, _fmt(kind, jira_val)))
        return jira_val

    # direction == both -> 3-way merge
    if todo_val == jira_val:
        return todo_val
    todo_changed = todo_val != base_val
    jira_changed = jira_val != base_val
    if todo_changed and not jira_changed:
        push(todo_val)
        actions.append(Action(push_op, key, _fmt(kind, todo_val)))
        return todo_val
    if jira_changed and not todo_changed:
        pull(jira_val)
        actions.append(Action(pull_op, key, _fmt(kind, jira_val)))
        return jira_val
    # both sides changed differently -> conflict
    if cfg.conflict == CONFLICT_JIRA:
        pull(jira_val)
        actions.append(Action("CONFLICT", key, f"{kind}: Jira wins -> {_fmt(kind, jira_val)}"))
        return jira_val
    if cfg.conflict == CONFLICT_TODO:
        push(todo_val)
        actions.append(Action("CONFLICT", key, f"{kind}: todo wins -> {_fmt(kind, todo_val)}"))
        return todo_val
    # CONFLICT_SKIP: leave both, preserve the old baseline for re-detection
    actions.append(
        Action("CONFLICT", key, f"{kind}: skipped (todo={_fmt(kind, todo_val)} jira={_fmt(kind, jira_val)})")
    )
    return base_val


def _fmt(kind, value):
    return value.value if isinstance(value, Status) else repr(value)


def _set_title(node: Node, value: str) -> None:
    node.title = value


def _set_status(node: Node, value: Status, now_fn) -> None:
    node.status = value
    if value is Status.IN_PROGRESS:
        node.started_at = node.started_at or _now(now_fn)
        node.finished_at = None
    elif value in (Status.DONE, Status.CANCELLED):
        node.finished_at = node.finished_at or _now(now_fn)
    else:  # TODO
        node.started_at = None
        node.finished_at = None


def _pull_missing(
    missing, root, todo_by_key, state, cfg, dry_run, actions, new_entries
) -> None:
    """Insert Jira issues that are absent from the todo file."""
    pending: list[JiraIssue] = []
    for issue in missing:
        if issue.key in state.entries and not cfg.pull_locally_deleted:
            # Existed before, removed locally on purpose -> respect deletion.
            actions.append(Action("LOCAL_DELETE", issue.key, "removed locally; dropped from state"))
            continue
        pending.append(issue)

    # Insert in waves so a parent is always present before its children.
    progress = True
    while pending and progress:
        progress = False
        still: list[JiraIssue] = []
        for issue in pending:
            kind = kind_from_type(issue.issue_type, cfg)
            parent_node = todo_by_key.get(issue.parent_key) if issue.parent_key else None
            if issue.parent_key and parent_node is None and issue.parent_key in {i.key for i in pending}:
                still.append(issue)  # parent will appear in a later wave
                continue
            node = Node(kind=kind, title=issue.summary, status=issue.status, jira_key=issue.key)
            target = parent_node if parent_node is not None else root
            target.add(node)
            todo_by_key[issue.key] = node
            new_entries[issue.key] = _entry_from_issue(issue, kind)
            actions.append(Action("PULL_NEW", issue.key, f"{kind.value}: {issue.summary!r}"))
            progress = True
        pending = still
    for issue in pending:  # parent never found -> attach at root
        kind = kind_from_type(issue.issue_type, cfg)
        node = Node(kind=kind, title=issue.summary, status=issue.status, jira_key=issue.key)
        root.add(node)
        todo_by_key[issue.key] = node
        new_entries[issue.key] = _entry_from_issue(issue, kind)
        actions.append(Action("PULL_NEW", issue.key, f"{kind.value} (orphan): {issue.summary!r}"))
