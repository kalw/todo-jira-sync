"""Parse and serialize Todo+ (`vscode-todo-plus`) files into the Node tree.

Classification rules (matching the requested mapping):

* A line that starts with a *box / done / cancelled* symbol is a **task**
  (a Jira Task, or a Sub-task when it is scaffolded under another task) -
  the leading symbol wins even if the line happens to end with ':'.
* Otherwise, a line ending with ':' is a **project**: an **Epic** when it sits
  at column 0, a **User Story** when it is indented.
* Everything else (blank lines, comments, free text) is preserved verbatim.

Identity for bidirectional sync is carried by an ``@jira(KEY)`` tag, which is a
perfectly valid Todo+ tag. For task lines it is appended at the end; for project
lines it is inserted just before the trailing ':' so the line still reads as a
project.
"""

from __future__ import annotations

import re

from .config import FormatConfig
from .models import Node, NodeKind, Status

# A Todo+ tag: @name or @name(value). Names may contain word chars and dashes.
_TAG_RE = re.compile(r"@([\w-]+)(?:\(([^)]*)\))?")
_JIRA_TAG_RE = re.compile(r"@jira\(([^)]+)\)", re.IGNORECASE)

# Tags whose meaning we manage (not stored as generic preserved tags).
_MANAGED_TAGS = {"jira", "started", "done", "cancelled"}


def _leading_width(line: str, tab_size: int) -> tuple[int, str]:
    """Return (expanded indent width, raw leading whitespace) for a line."""
    raw = line[: len(line) - len(line.lstrip(" \t"))]
    width = 0
    for ch in raw:
        if ch == "\t":
            width += tab_size - (width % tab_size)
        else:
            width += 1
    return width, raw


def _match_leading_symbol(body: str, symbols: list[str]) -> str | None:
    """If `body` (already left-stripped) starts with a symbol token, return it.

    The symbol must be followed by whitespace or be the whole line, so that a
    word such as "Xenon" is not mistaken for the cancelled symbol "X".
    """
    for sym in symbols:  # longest-first from FormatConfig.all_symbols()
        if body == sym:
            return sym
        if body.startswith(sym):
            rest = body[len(sym):]
            if rest[:1] in (" ", "\t"):
                return sym
    return None


def _status_from_symbol(sym: str, cfg: FormatConfig) -> Status:
    if sym in cfg.done_symbols:
        return Status.DONE
    if sym in cfg.cancelled_symbols:
        return Status.CANCELLED
    return Status.TODO


def _extract_tags(text: str) -> tuple[str, dict[str, str | None], list[str]]:
    """Pull tags out of `text`.

    Returns the cleaned text, a dict of managed tags {name: value}, and the list
    of preserved (non-managed) tags as raw strings in their original order.
    """
    managed: dict[str, str | None] = {}
    preserved: list[str] = []

    for m in _TAG_RE.finditer(text):
        name = m.group(1).lower()
        value = m.group(2)
        if name in _MANAGED_TAGS:
            managed[name] = value
        else:
            preserved.append(m.group(0))

    cleaned = _TAG_RE.sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned, managed, preserved


def _apply_managed(node: Node, managed: dict[str, str | None]) -> None:
    jira_value = managed.get("jira")
    if jira_value:
        node.jira_key = jira_value.strip()
    # Status from symbol is authoritative; tags only *refine* TODO -> IN_PROGRESS
    # and carry the timekeeping values for round-tripping.
    if "started" in managed:
        node.started_at = managed["started"]
        if node.status is Status.TODO:
            node.status = Status.IN_PROGRESS
    if "done" in managed:
        node.finished_at = managed["done"]
    if "cancelled" in managed:
        node.finished_at = managed["cancelled"]


def parse(text: str, cfg: FormatConfig | None = None) -> Node:
    """Parse Todo+ text into a Node tree rooted at a synthetic ROOT node."""
    cfg = cfg or FormatConfig()
    symbols = cfg.all_symbols()

    root = Node(kind=NodeKind.ROOT, indent=-1)
    stack: list[Node] = [root]

    for line in text.splitlines():
        width, _ = _leading_width(line, cfg.tab_size)
        body = line.strip()

        if body == "":
            node = Node(kind=NodeKind.OTHER, indent=width, raw=line)
            stack[-1].add(node)
            continue

        left_stripped = line.lstrip(" \t")
        sym = _match_leading_symbol(left_stripped, symbols)

        if sym is not None:
            # --- task line --------------------------------------------------
            # Pop to the real parent *first*; only then can we tell whether this
            # task is scaffolded under another task (-> Sub-task) or a project.
            parent = _pop_to_parent(stack, width)
            content = left_stripped[len(sym):].strip()
            title, managed, preserved = _extract_tags(content)
            ancestor_is_task = any(
                n.kind in (NodeKind.TASK, NodeKind.SUBTASK) for n in stack[1:]
            )
            kind = NodeKind.SUBTASK if ancestor_is_task else NodeKind.TASK
            node = Node(
                kind=kind,
                title=title,
                status=_status_from_symbol(sym, cfg),
                indent=width,
                tags=preserved,
            )
            _apply_managed(node, managed)
            parent.add(node)
            stack.append(node)
            continue

        if body.endswith(":"):
            # --- project line (epic at col 0, story when indented) ----------
            parent = _pop_to_parent(stack, width)
            before_colon = body[:-1]
            title, managed, preserved = _extract_tags(before_colon)
            kind = NodeKind.EPIC if width == 0 else NodeKind.STORY
            node = Node(kind=kind, title=title, indent=width, tags=preserved)
            _apply_managed(node, managed)
            parent.add(node)
            stack.append(node)
            continue

        # --- anything else: preserved verbatim ----------------------------
        node = Node(kind=NodeKind.OTHER, indent=width, raw=line)
        stack[-1].add(node)

    resolve_jira_parents(root, cfg)
    return root


def _pop_to_parent(stack: list[Node], indent: int) -> Node:
    """Pop the stack to the correct container for `indent` and return it."""
    while len(stack) > 1 and stack[-1].indent >= indent:
        stack.pop()
    return stack[-1]


def resolve_jira_parents(root: Node, cfg: FormatConfig) -> None:
    """Fill ``jira_parent_key`` for every issue node from its ancestors.

    The Jira parent of a node is its **nearest enclosing container** in the
    outline:

    * Epic        -> no parent
    * Story       -> nearest ancestor container (normally the enclosing Epic)
    * Task        -> nearest ancestor container: the enclosing Story if there is
                     one, otherwise the enclosing Epic
    * Sub-task    -> nearest ancestor *standard Task* (Jira forbids sub-tasks of
                     sub-tasks, so deeper nesting collapses onto that Task)
    """
    for node in root.issues():
        if node.kind is NodeKind.EPIC:
            node.jira_parent_key = None
        elif node.kind is NodeKind.SUBTASK:
            task = node.nearest_ancestor(NodeKind.TASK)
            node.jira_parent_key = task.jira_key if task else None
        else:  # STORY or TASK -> nearest enclosing container
            container = node.nearest_ancestor(
                NodeKind.EPIC, NodeKind.STORY, NodeKind.TASK
            )
            node.jira_parent_key = container.jira_key if container else None


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #
def _symbol_for(node: Node, cfg: FormatConfig) -> str:
    if node.status is Status.DONE:
        return cfg.canonical_done
    if node.status is Status.CANCELLED:
        return cfg.canonical_cancelled
    return cfg.canonical_box  # TODO and IN_PROGRESS both use the box symbol


def _render_tags(node: Node) -> str:
    """Render managed + preserved tags in a stable order, space-separated."""
    parts: list[str] = []
    if node.status is Status.IN_PROGRESS or node.started_at is not None:
        parts.append(_tag("started", node.started_at))
    if node.status is Status.DONE:
        parts.append(_tag("done", node.finished_at))
    elif node.status is Status.CANCELLED:
        parts.append(_tag("cancelled", node.finished_at))
    parts.extend(node.tags)
    if node.jira_key:
        parts.append(f"@jira({node.jira_key})")
    return " ".join(parts)


def _tag(name: str, value: str | None) -> str:
    return f"@{name}({value})" if value else f"@{name}"


def _render_line(node: Node, cfg: FormatConfig) -> str:
    if node.kind is NodeKind.OTHER:
        return node.raw if node.raw is not None else ""

    indent = cfg.indent_unit * node.depth()
    tags = _render_tags(node)

    if node.kind.is_project:
        head = node.title
        if tags:
            head = f"{head} {tags}".strip()
        return f"{indent}{head}:"

    # task / subtask
    sym = _symbol_for(node, cfg)
    parts = [sym, node.title] if node.title else [sym]
    line = " ".join(parts)
    if tags:
        line = f"{line} {tags}".strip()
    return f"{indent}{line}"


def serialize(root: Node, cfg: FormatConfig | None = None) -> str:
    """Serialize a Node tree back to Todo+ text (trailing newline included)."""
    cfg = cfg or FormatConfig()
    lines: list[str] = []

    def emit(node: Node) -> None:
        for child in node.children:
            lines.append(_render_line(child, cfg))
            emit(child)

    emit(root)
    text = "\n".join(lines)
    return text + "\n" if text else ""
