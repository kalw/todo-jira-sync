"""Thin Jira Cloud REST v3 client plus the Protocol the engine depends on.

The sync engine only ever talks to the :class:`JiraClient` *protocol*, so it
stays free of any network dependency and is trivial to unit-test with a fake.
:class:`RestJiraClient` is the real implementation; it imports ``requests``
lazily so that importing this module never requires it.

Search uses the current enhanced endpoint ``POST /rest/api/3/search/jql`` with
``nextPageToken`` pagination - the legacy ``/rest/api/3/search`` was removed
from Jira Cloud in 2025.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .config import FormatConfig
from .models import JiraIssue, NodeKind, Status

# Jira status categories -> our Status (cancelled is detected separately by name)
_CATEGORY_TO_STATUS = {
    "new": Status.TODO,
    "indeterminate": Status.IN_PROGRESS,
    "done": Status.DONE,
}


# our NodeKind -> the configured Jira issue-type name
def issue_type_name(kind: NodeKind, cfg: FormatConfig) -> str:
    return {
        NodeKind.EPIC: cfg.type_epic,
        NodeKind.STORY: cfg.type_story,
        NodeKind.TASK: cfg.type_task,
        NodeKind.SUBTASK: cfg.type_subtask,
    }[kind]


def kind_from_type(type_name: str, cfg: FormatConfig) -> NodeKind:
    mapping = {
        cfg.type_epic.lower(): NodeKind.EPIC,
        cfg.type_story.lower(): NodeKind.STORY,
        cfg.type_task.lower(): NodeKind.TASK,
        cfg.type_subtask.lower(): NodeKind.SUBTASK,
    }
    return mapping.get(type_name.lower(), NodeKind.TASK)


@runtime_checkable
class JiraClient(Protocol):
    """The capabilities the sync engine needs from Jira."""

    def search_issues(self, project: str) -> list[JiraIssue]: ...

    def create_issue(
        self,
        *,
        project: str,
        issue_type: str,
        summary: str,
        parent_key: str | None = None,
    ) -> str:
        """Create an issue and return its new key."""
        ...

    def update_summary(self, key: str, summary: str) -> None: ...

    def set_status(self, key: str, status: Status) -> None:
        """Transition the issue so it ends in the desired status."""
        ...


class JiraError(RuntimeError):
    pass


class RestJiraClient:
    """Concrete client for Jira Cloud (and Server/DC via bearer auth)."""

    def __init__(
        self,
        base_url: str,
        *,
        email: str | None = None,
        token: str,
        auth: str = "basic",
        cfg: FormatConfig | None = None,
        timeout: float = 30.0,
    ) -> None:
        import requests  # local import keeps the module import dependency-free

        self.base_url = base_url.rstrip("/")
        self.cfg = cfg or FormatConfig()
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )
        if auth == "bearer":
            self._session.headers["Authorization"] = f"Bearer {token}"
        else:  # Jira Cloud: HTTP Basic with email + API token
            if not email:
                raise JiraError("Basic auth requires an email address.")
            self._session.auth = (email, token)

    # -- low level ---------------------------------------------------------
    def _url(self, path: str) -> str:
        return f"{self.base_url}/rest/api/3{path}"

    def _request(self, method: str, path: str, **kwargs):
        resp = self._session.request(method, self._url(path), timeout=self.timeout, **kwargs)
        if resp.status_code >= 400:
            raise JiraError(f"{method} {path} -> {resp.status_code}: {resp.text[:500]}")
        return resp

    # -- protocol ----------------------------------------------------------
    def search_issues(self, project: str) -> list[JiraIssue]:
        issues: list[JiraIssue] = []
        token: str | None = None
        fields = ["summary", "status", "issuetype", "parent", "updated"]
        while True:
            body: dict = {
                "jql": f"project = {project} ORDER BY created ASC",
                "fields": fields,
                "maxResults": 100,
            }
            if token:
                body["nextPageToken"] = token
            data = self._request("POST", "/search/jql", json=body).json()
            for raw in data.get("issues", []):
                issues.append(self._to_issue(raw))
            token = data.get("nextPageToken")
            if data.get("isLast", token is None) or not token:
                break
        return issues

    def _to_issue(self, raw: dict) -> JiraIssue:
        f = raw.get("fields", {})
        status_field = f.get("status", {}) or {}
        category = (status_field.get("statusCategory", {}) or {}).get("key", "new")
        name = status_field.get("name", "")
        if name in self.cfg.cancelled_status_names:
            status = Status.CANCELLED
        else:
            status = _CATEGORY_TO_STATUS.get(category, Status.TODO)
        parent = f.get("parent") or {}
        return JiraIssue(
            key=raw["key"],
            summary=f.get("summary", ""),
            status=status,
            issue_type=(f.get("issuetype", {}) or {}).get("name", ""),
            parent_key=parent.get("key"),
            updated=f.get("updated"),
        )

    def create_issue(
        self,
        *,
        project: str,
        issue_type: str,
        summary: str,
        parent_key: str | None = None,
    ) -> str:
        fields: dict = {
            "project": {"key": project},
            "issuetype": {"name": issue_type},
            "summary": summary,
        }
        if parent_key:
            fields["parent"] = {"key": parent_key}
        data = self._request("POST", "/issue", json={"fields": fields}).json()
        return data["key"]

    def update_summary(self, key: str, summary: str) -> None:
        self._request("PUT", f"/issue/{key}", json={"fields": {"summary": summary}})

    def set_status(self, key: str, status: Status) -> None:
        target = self._pick_transition(key, status)
        if target is None:
            raise JiraError(f"No transition to status {status.value} for {key}.")
        self._request("POST", f"/issue/{key}/transitions", json={"transition": {"id": target}})

    def _pick_transition(self, key: str, status: Status) -> str | None:
        data = self._request("GET", f"/issue/{key}/transitions").json()
        transitions = data.get("transitions", [])

        def category_of(t: dict) -> str:
            return ((t.get("to", {}) or {}).get("statusCategory", {}) or {}).get("key", "")

        def name_of(t: dict) -> str:
            return (t.get("to", {}) or {}).get("name", "")

        if status is Status.CANCELLED:
            for t in transitions:  # prefer a real cancel/won't-do status
                if name_of(t) in self.cfg.cancelled_status_names:
                    return t["id"]
            wanted = "done"
        else:
            wanted = {
                Status.TODO: "new",
                Status.IN_PROGRESS: "indeterminate",
                Status.DONE: "done",
            }[status]

        for t in transitions:
            if category_of(t) == wanted:
                return t["id"]
        return None
