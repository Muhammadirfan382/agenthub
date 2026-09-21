# syntax=docker/dockerfile:1
#
# The AgentHub backend image: the API, the migrations, and the files the
# host-installed worker is built from.
#
#   docker build -f infrastructure/docker/backend.Dockerfile -t agenthub-backend .
#
# Built from the repository root (migrations live outside backend/).
#
# One image, three uses, all from the same digest:
# - the API (default command), in a container with no container runtime,
#   no provider keys and no internet egress;
# - the migration job (`python -m alembic upgrade head`);
# - the source of the worker, which runs on the host because it drives a
#   rootless container runtime: the deploy script copies /opt/agenthub/backend
#   and /opt/agenthub/wheels out of this image, so the worker runs exactly the
#   code and dependencies that were scanned and signed. See docs/DEPLOYMENT.md.
#
# Python 3.13 on Debian 13 (trixie) on purpose: the worker hosts run Debian 13,
# whose system Python is 3.13, so the wheels built here install there.
# Base images are pinned by digest; Dependabot proposes updates.

FROM python:3.13.15-slim-trixie@sha256:8d9d0b8bcf6506481eae4907c18f5e3e7902e629f5f6d684f9e7c32e85e3ddf0 AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY backend/requirements.txt .

# Wheels first, then the virtual environment from those wheels only: the same
# files are shipped for the worker, so API and worker cannot drift apart.
RUN python -m pip wheel --wheel-dir /wheels --requirement requirements.txt \
    && python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-index --find-links /wheels --requirement requirements.txt


FROM python:3.13.15-slim-trixie@sha256:8d9d0b8bcf6506481eae4907c18f5e3e7902e629f5f6d684f9e7c32e85e3ddf0 AS runtime

ARG REVISION=unknown
ARG SOURCE=unknown
LABEL org.opencontainers.image.title="agenthub-backend" \
      org.opencontainers.image.source="${SOURCE}" \
      org.opencontainers.image.revision="${REVISION}"

# A fixed, unprivileged account. The number matters: host files the container
# must read (secrets) are shared with this gid, so it is set, not allocated.
RUN groupadd --system --gid 10001 agenthub \
    && useradd --system --uid 10001 --gid agenthub --no-create-home \
       --home-dir /nonexistent --shell /usr/sbin/nologin agenthub

COPY --from=build /opt/venv /opt/venv
# Nothing at runtime installs packages, so pip is removed from the system
# Python, the virtual environment and ensurepip. It also bundles its own old
# copies of other libraries that scanners rightly flag. (Worker hosts install
# the wheels below with their own pip.)
RUN /opt/venv/bin/python -m pip uninstall --yes --quiet pip \
    && python -m pip uninstall --yes --quiet pip \
    && rm -rf /usr/local/lib/python3.13/ensurepip
COPY --from=build /wheels /opt/agenthub/wheels
COPY backend/requirements.txt /opt/agenthub/requirements.txt
COPY backend/alembic.ini /opt/agenthub/backend/alembic.ini
COPY backend/app /opt/agenthub/backend/app
# Only the account script: demonstration seeding has no place in production.
COPY backend/scripts/create_user.py /opt/agenthub/backend/scripts/create_user.py
COPY database/migrations /opt/agenthub/database/migrations

WORKDIR /opt/agenthub/backend
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    AGENTHUB_REVISION=${REVISION}

USER 10001:10001
EXPOSE 8000

# Proxy headers are honoured only from FORWARDED_ALLOW_IPS (the reverse proxy's
# fixed address, set in compose); from anyone else they are ignored, so a client
# cannot choose the address the sign-in limiter sees.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--no-server-header", "--timeout-graceful-shutdown", "20"]
