"""pytest plugin: point switch-core's testcontainers Postgres at Edison's sidecar.

Loaded with `-p pg_redirect` before conftest.py imports PostgresContainer, so the
tests get a real Postgres without the sandbox ever touching the Docker socket.
"""

import os

import testcontainers.postgres


class SidecarPostgres:
    username = os.environ.get("EDISON_PG_USER", "edison")
    password = os.environ.get("EDISON_PG_PASSWORD", "edison")
    dbname = os.environ.get("EDISON_PG_DB", "edison")

    def __init__(self, *args, **kwargs):
        pass

    def with_command(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_container_host_ip(self):
        return os.environ["EDISON_PG_HOST"]

    def get_exposed_port(self, port):
        return int(os.environ.get("EDISON_PG_PORT", "5432"))


testcontainers.postgres.PostgresContainer = SidecarPostgres
