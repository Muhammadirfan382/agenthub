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

FROM python:3.14-alpine3.21

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

USER 65532:65532

# No shell in the entrypoint: one process, no interpretation of arguments.
ENTRYPOINT ["python3", "-I", "-B", "/opt/agenthub/probe.py"]
