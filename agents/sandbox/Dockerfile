# The AgentHub execution sandbox.
#
# This image is the box an agent will eventually run inside. It contains no
# agent code: today it carries one program, `probe.py`, which reports what the
# container can and cannot do so the isolation can be checked rather than
# assumed.
#
# Build (from the repository root):
#   docker build -t agenthub/sandbox:0.6.0 agents/sandbox
#
# It is never run with a mounted socket, a host path, or the host's
# environment: see backend/app/sandbox/spec.py for how it is started.

# Pinned by digest like every other base image; Dependabot proposes updates.
# Alpine 3.21 shipped an OpenSSL with known HIGH/CRITICAL fixes pending.
FROM python:3.15.0rc3-alpine3.24@sha256:f288a00331ddad8ddf86aa9d83331f188d9a5b1999dea3762adf2af1968b0c04

# A fixed, unprivileged account. 65532 is the conventional "nonroot" id, and
# using a number rather than a name means the container cannot be started as
# root by a runtime that cannot resolve the name.
RUN addgroup -g 65532 -S agent \
    && adduser -u 65532 -S -G agent -h /home/agent -s /sbin/nologin agent

WORKDIR /opt/agenthub
COPY probe.py /opt/agenthub/probe.py

# Nothing here needs to be writable: the runtime also starts the container with
# a read-only root filesystem, so this is belt and braces.
RUN chmod 0444 /opt/agenthub/probe.py

# The probe needs Python and nothing else. pip (and the old library copies it
# bundles, which scanners flag) has no business in a sandbox.
RUN python -m pip uninstall --yes --quiet pip \
    && rm -rf /usr/local/lib/python3.13/ensurepip

USER 65532:65532

# No shell in the entrypoint: one process, no interpretation of arguments.
ENTRYPOINT ["python3", "-I", "-B", "/opt/agenthub/probe.py"]
