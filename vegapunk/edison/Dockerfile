# Edison's test image: switch-core's locked dependencies, no source.
# The PR's tree is mounted at /src at run time, and the container runs with no internet.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.27 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /deps
COPY core/pyproject.toml core/uv.lock core/
RUN uv sync --project core --frozen --no-install-project
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1
# uid 1000 matches the WSL user, so results written into the mounted tree stay readable
RUN useradd -m -u 1000 runner
USER runner
WORKDIR /src
