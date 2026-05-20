"""An in-memory Jira double used across the test suite."""

from __future__ import annotations

from todo_jira_sync.models import JiraIssue, Status


class FakeJira:
    """Implements the JiraClient protocol against an in-memory dict."""

    def __init__(self, project: str = "WEB") -> None:
        self.project = project
        self.issues: dict[str, JiraIssue] = {}
        self._counter = 0
        self.calls: list[tuple] = []

    # -- protocol ----------------------------------------------------------
    def search_issues(self, project: str) -> list[JiraIssue]:
        return list(self.issues.values())

    def create_issue(self, *, project, issue_type, summary, parent_key=None) -> str:
        self._counter += 1
        key = f"{project}-{self._counter}"
        self.issues[key] = JiraIssue(
            key=key,
            summary=summary,
            status=Status.TODO,
            issue_type=issue_type,
            parent_key=parent_key,
        )
        self.calls.append(("create", key, issue_type, summary, parent_key))
        return key

    def update_summary(self, key: str, summary: str) -> None:
        self.issues[key].summary = summary
        self.calls.append(("update_summary", key, summary))

    def set_status(self, key: str, status: Status) -> None:
        self.issues[key].status = status
        self.calls.append(("set_status", key, status.value))

    # -- helpers for tests -------------------------------------------------
    def seed(self, key, summary, status=Status.TODO, issue_type="Task", parent_key=None):
        self.issues[key] = JiraIssue(
            key=key, summary=summary, status=status, issue_type=issue_type,
            parent_key=parent_key,
        )
        n = int(key.split("-")[-1])
        self._counter = max(self._counter, n)
        return key
