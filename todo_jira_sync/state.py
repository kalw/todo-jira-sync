"""Persisted sync baseline (the "common ancestor" for 3-way merges).

After every successful sync we snapshot, per Jira key, the agreed-upon value of
each synced field. On the next run we compare both the live todo file and live
Jira against this baseline to decide which side changed - and only flag a real
conflict when *both* changed away from it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import Status

STATE_SUFFIX = ".todojira.json"
STATE_VERSION = 1


@dataclass
class BaseEntry:
    summary: str
    status: str  # Status value
    issue_type: str  # epic/story/task/subtask
    parent_key: str | None = None

    def status_enum(self) -> Status:
        return Status(self.status)


@dataclass
class SyncState:
    project: str
    entries: dict[str, BaseEntry]  # keyed by Jira issue key
    last_sync: str | None = None
    version: int = STATE_VERSION

    @classmethod
    def empty(cls, project: str) -> "SyncState":
        return cls(project=project, entries={})

    # -- persistence --------------------------------------------------------
    @classmethod
    def path_for(cls, todo_path: str | Path) -> Path:
        p = Path(todo_path)
        return p.with_name(p.name + STATE_SUFFIX)

    @classmethod
    def load(cls, todo_path: str | Path, project: str) -> "SyncState":
        path = cls.path_for(todo_path)
        if not path.exists():
            return cls.empty(project)
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = {
            key: BaseEntry(**entry) for key, entry in data.get("entries", {}).items()
        }
        return cls(
            project=data.get("project", project),
            entries=entries,
            last_sync=data.get("last_sync"),
            version=data.get("version", STATE_VERSION),
        )

    def save(self, todo_path: str | Path) -> Path:
        path = self.path_for(todo_path)
        payload = {
            "version": self.version,
            "project": self.project,
            "last_sync": self.last_sync,
            "entries": {key: asdict(entry) for key, entry in self.entries.items()},
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
