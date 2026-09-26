# syntax=docker/dockerfile:1
#
# The AgentHub web image: the built frontend, served by Caddy, which also
# terminates TLS and proxies /api to the backend.
#
#   docker build -f infrastructure/docker/web.Dockerfile -t agenthub-web .
#
# Built from the repository root. Base images are pinned by digest.

FROM node:24.21.0-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS build

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


# Caddy, rebuilt. The v2.11.4 release binary embeds Go 1.26.3 and library
# versions with known HIGH vulnerabilities (the CI image scan lists them).
# This compiles the same Caddy release with a patched Go and the patched
# library versions Caddy's own main branch has moved to. Every version is
# explicit, and Go verifies each module against its checksum database.
FROM golang:1.27.0-alpine3.24@sha256:4c9fe60190a2a3350ddc51de80d0224b8a6698d12bdfc999fee45ea9d6c46dbc AS caddy

ENV CGO_ENABLED=0 \
    GOTOOLCHAIN=local \
    GOFLAGS=-trimpath
WORKDIR /src
COPY <<'GO' main.go
package main

import (
	caddycmd "github.com/caddyserver/caddy/v2/cmd"

	// The standard modules: everything the Caddyfile uses, nothing extra.
	_ "github.com/caddyserver/caddy/v2/modules/standard"
)

func main() {
	caddycmd.Main()
}
GO
RUN go mod init agenthub.local/caddy \
    && go get github.com/caddyserver/caddy/v2@v2.11.4 \
    && go get google.golang.org/grpc@v1.83.2 \
              golang.org/x/net@v0.58.0 \
              golang.org/x/text@v0.41.0 \
              golang.org/x/crypto@v0.55.0 \
    && go mod tidy \
    && go build -ldflags "-s -w" -o /out/caddy . \
    && /out/caddy version


FROM caddy:2.11.4-alpine@sha256:de23def33b17fb5d1290b0f6c2add1d70780e52341896c00a4c8a2a2fe9d355e AS runtime

ARG REVISION=unknown
ARG SOURCE=unknown
LABEL org.opencontainers.image.title="agenthub-web" \
      org.opencontainers.image.source="${SOURCE}" \
      org.opencontainers.image.revision="${REVISION}"

# Caddy runs unprivileged and listens on 8080/8443; the host maps 80/443 to
# them. The base image gives the binary a file capability (to bind low
# ports); it is removed, because a container started with every capability
# dropped cannot execute a binary that carries one - the kernel refuses the
# exec outright. Its state directories are created here so the named volumes
# mounted over them start out owned by it.
RUN setcap -r /usr/bin/caddy \
    && addgroup -S -g 10002 caddy-web \
    && adduser -S -u 10002 -G caddy-web -H -h /nonexistent -s /sbin/nologin caddy-web \
    && mkdir -p /data/caddy /config/caddy \
    && chown -R 10002:10002 /data /config

# The rebuilt binary replaces the release one (and carries no file
# capability of its own).
COPY --from=caddy /out/caddy /usr/bin/caddy
COPY --from=build /build/dist /srv
COPY infrastructure/deployment/Caddyfile /etc/caddy/Caddyfile

USER 10002:10002
EXPOSE 8080 8443
