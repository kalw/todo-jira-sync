"""In-memory model shared by the parser, serializer and sync engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class NodeKind(str, Enum):
    """How a todo line maps onto the Jira hierarchy."""

    ROOT = "root"  # synthetic document root
    EPIC = "epic"  # project line (ends with ':') at column 0
    STORY = "story"  # project line (ends with ':') that is indented
    TASK = "task"  # todo item whose container is a project/root
    SUBTASK = "subtask"  # todo item scaffolded under another todo item
    OTHER = "other"  # blank line / comment / anything we pass through verbatim

    @property
    def is_project(self) -> bool:
        return self in (NodeKind.EPIC, NodeKind.STORY)

    @property
    def is_issue(self) -> bool:
        return self in (NodeKind.EPIC, NodeKind.STORY, NodeKind.TASK, NodeKind.SUBTASK)


class Status(str, Enum):
    """Synchronised status, abstracted over both worlds.

    Maps to Todo+ symbols on one side and Jira status categories on the other.
    """

    TODO = "todo"  # box symbol, no @started  <-> category "new"
    IN_PROGRESS = "in_progress"  # box symbol + @started <-> category "indeterminate"
    DONE = "done"  # done symbol            <-> category "done"
    CANCELLED = "cancelled"  # cancelled symbol  <-> Done + cancel resolution


@dataclass
class Node:
    """A single line in the todo file (or a synthetic root)."""

    kind: NodeKind
    title: str = ""  # clean summary: no symbol, no managed tags, no colon
    status: Status = Status.TODO
    jira_key: str | None = None
    indent: int = -1  # leading whitespace columns (tabs expanded)

    # Preserved, non-managed Todo+ tags (e.g. "@today", "@est(2h)"), verbatim.
    tags: list[str] = field(default_factory=list)
    started_at: str | None = None  # value captured from @started(...)
    finished_at: str | None = None  # value captured from @done(...)/@cancelled(...)

    raw: str | None = None  # original text for OTHER passthrough lines

    children: list[Node] = field(default_factory=list)
    parent: Node | None = field(default=None, repr=False)

    # Resolved during a tree pass; not parsed from the file.
    jira_parent_key: str | None = field(default=None, repr=False)

    def add(self, child: Node) -> None:
        child.parent = self
        self.children.append(child)

    def walk(self):
        """Depth-first pre-order over all descendants (excluding self)."""
        for child in self.children:
            yield child
            yield from child.walk()

    def issues(self):
        """All descendant nodes that map to a Jira issue, in document order."""
        return (n for n in self.walk() if n.kind.is_issue)

    def depth(self) -> int:
        """Number of ancestors above this node, root being depth 0."""
        d = 0
        p = self.parent
        while p is not None and p.kind is not NodeKind.ROOT:
            d += 1
            p = p.parent
        return d

    def nearest_ancestor(self, *kinds: NodeKind) -> Node | None:
        p = self.parent
        while p is not None:
            if p.kind in kinds:
                return p
            p = p.parent
        return None


@dataclass
class JiraIssue:
    """Normalised view of a Jira issue used by the engine."""

    key: str
    summary: str
    status: Status
    issue_type: str  # raw Jira type name (Epic / Story / Task / Sub-task)
    parent_key: str | None = None
    updated: str | None = None  # ISO timestamp from Jira, informational
