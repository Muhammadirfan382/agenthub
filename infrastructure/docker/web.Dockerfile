# syntax=docker/dockerfile:1
#
# The AgentHub web image: the built frontend, served by Caddy, which also
# terminates TLS and proxies /api to the backend.
#
#   docker build -f infrastructure/docker/web.Dockerfile -t agenthub-web .
#
# Built from the repository root. Base images are pinned by digest.

FROM node:26.9.0-alpine@sha256:dbaa92e5758cbbcf85d65d5403fdb530fe3442cbe8c6dbfb7ef23365450d5070 AS build

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
# Exactly the locked tree, and no install scripts: a dependency does not get to
# run code on the build machine.
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/ ./

# Same origin as the API (Caddy proxies /api), and the backend by default.
# Nothing secret belongs in VITE_* variables: they are compiled into the bundle.
ENV VITE_DATA_SOURCE=api \
    VITE_API_BASE_URL=
RUN npm run build


FROM caddy:2.11.4-alpine@sha256:de23def33b17fb5d1290b0f6c2add1d70780e52341896c00a4c8a2a2fe9d355e AS runtime

ARG REVISION=unknown
ARG SOURCE=unknown
LABEL org.opencontainers.image.title="agenthub-web" \
      org.opencontainers.image.source="${SOURCE}" \
      org.opencontainers.image.revision="${REVISION}"

# Caddy runs unprivileged and listens on 8080/8443; the host maps 80/443 to
# them. (Binding low ports would need a file capability, which
# no-new-privileges correctly refuses to grant.) Its state directories are
# created here so the named volumes mounted over them start out owned by it.
RUN addgroup -S -g 10002 caddy-web \
    && adduser -S -u 10002 -G caddy-web -H -h /nonexistent -s /sbin/nologin caddy-web \
    && mkdir -p /data/caddy /config/caddy \
    && chown -R 10002:10002 /data /config

COPY --from=build /build/dist /srv
COPY infrastructure/deployment/Caddyfile /etc/caddy/Caddyfile

USER 10002:10002
EXPOSE 8080 8443
