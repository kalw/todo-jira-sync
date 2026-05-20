# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Build stage: install the package (and its deps) into an isolated venv with uv.
# ---------------------------------------------------------------------------
FROM python:3.14-slim-bookworm AS build

# uv, copied from its official distroless image (pinned by the publish workflow).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# setuptools-scm derives the version from git. In CI we pass the resolved
# version as a build arg so the build does not need the .git directory.
ARG VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}

WORKDIR /app
COPY pyproject.toml README.md ./
COPY todo_jira_sync ./todo_jira_sync

# Create the venv and install the project into it.
RUN uv venv /opt/venv \
    && VIRTUAL_ENV=/opt/venv uv pip install --no-cache .

# ---------------------------------------------------------------------------
# Runtime stage: copy only the venv onto a slim base. No compilers, no uv.
# ---------------------------------------------------------------------------
FROM python:3.14-slim-bookworm AS runtime

# Run as a non-root user.
RUN useradd --create-home --uid 1000 app

COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Work against a mounted directory holding the todo file and its .env.
WORKDIR /work
USER app

ENTRYPOINT ["todo-jira-sync"]
CMD ["--help"]
