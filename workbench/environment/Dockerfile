# syntax=docker/dockerfile:1
#
# Every workbench environment shares the `base` stage, so it carries only stable
# setup; environment-specific packages belong in the final stage.

# Pinned for reproducible builds; bumping one rebuilds the layers that use it.
ARG NODE_IMAGE=node:24-bookworm-slim
ARG BUN_IMAGE=oven/bun:1.3.14
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.3
ARG PNPM_VERSION=11.20.0
ARG REWARDKIT_VERSION=0.1.7
ARG PAPER_DOCX_VERSION=0.1.2
ARG PAPER_PPTX_VERSION=0.1.2
ARG PAPER_XLSX_VERSION=0.1.3

FROM ${NODE_IMAGE} AS node
FROM ${BUN_IMAGE} AS bun
FROM ${UV_IMAGE} AS uv

# Same image as `base`, so the compiled binary matches the runtime glibc.
FROM ubuntu:26.04 AS build

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev && \
    rm -rf /var/lib/apt/lists/*

COPY run-as-environment.c /run-as-environment.c
RUN gcc -O2 -Wall -Wextra -o /run-as-environment /run-as-environment.c

FROM ubuntu:26.04 AS base

ARG DEBIAN_FRONTEND=noninteractive
ARG PNPM_VERSION
ARG REWARDKIT_VERSION

# A container is already isolated, so uv targets the system interpreter.
ENV UV_SYSTEM_PYTHON=1

# Ubuntu 26.04 ships Python 3.14; the assert fails the build if that changes.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        sudo \
        python3 \
        python3-pip \
        python3-venv && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -c 'import sys; assert sys.version_info[:2] == (3, 14), sys.version'

# node, npm, npx, and corepack all live under /usr/local in the Node image.
COPY --from=node /usr/local /usr/local
COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun

RUN python3 -m pip install --upgrade --break-system-packages pip && \
    corepack enable && \
    corepack prepare "pnpm@${PNPM_VERSION}" --activate && \
    node --version && pnpm --version && bun --version && uv --version

# environment serves the agent-facing tools, agent does the task work, verifier
# grades it, and sandbox runs what the verifier delegates. environment and
# verifier join the agent group to reach the workspace; sandbox joins verifier so
# the verifier can hand it files. The UIDs are fixed because bind-mounted files
# and collected logs carry numeric ownership onto the host.
RUN useradd -m -u 10000 -d /home/environment -s /bin/bash environment && \
    useradd -m -u 10001 -d /home/agent -s /bin/bash agent && \
    useradd -m -u 10002 -d /home/verifier -s /bin/bash verifier && \
    useradd -m -u 10003 -d /home/sandbox -s /bin/bash sandbox && \
    usermod -aG agent environment && \
    usermod -aG agent verifier && \
    usermod -aG verifier sandbox && \
    echo "verifier ALL=(sandbox) NOPASSWD: ALL" > /etc/sudoers.d/verifier && \
    chmod 440 /etc/sudoers.d/verifier

# Harbor's runtime paths. Reward Kit's default workspace is /app, which symlinks
# to the agent's workspace.
#
# A materialized environment bundle unpacks across two of these: its
# `workspace/` — the professional's own document folders — becomes
# /home/agent/workspace, and its `state/` — the projected tool databases —
# becomes /home/environment/state, mode 0700 so only the environment user can
# open it. The MCP servers launch behind run-as-environment, so the emulated
# products are the agent's only aperture onto the record; nothing under
# /home/agent/workspace names a database, a server, or the bundle. The verifier
# and the reference solution are offstage by design and receive the databases
# through $WORKBENCH_STATE (the bundle-relative default is ../state).
RUN install -d -m 755 /logs && \
    install -d -o agent -g agent -m 775 /home/agent/workspace /logs/agent && \
    install -d -o environment -g environment -m 700 /home/environment/state && \
    install -d -o agent -g agent -m 777 /installed-agent /oracle && \
    install -d -o verifier -g agent -m 775 /logs/verifier && \
    ln -sfn /home/agent/workspace /app

# --chown needs the environment user, so this follows user creation.
COPY --from=build --chown=environment:environment \
    /run-as-environment /usr/local/bin/run-as-environment
RUN chmod 4755 /usr/local/bin/run-as-environment

# Preinstalled so tests/test.sh can call `rewardkit /tests` without network;
# [all] adds the document and image criteria. harborframework.com/docs/rewardkit
RUN UV_TOOL_DIR=/opt/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin \
    uv tool install --python python3 "harbor-rewardkit[all]==${REWARDKIT_VERSION}" && \
    chmod -R a+rX /opt/uv-tools && \
    rewardkit --help > /dev/null

WORKDIR /home/agent/workspace
CMD ["/bin/bash"]

FROM base

ARG DEBIAN_FRONTEND=noninteractive
ARG PAPER_DOCX_VERSION
ARG PAPER_PPTX_VERSION
ARG PAPER_XLSX_VERSION

# paper-xlsx delegates formula recalculation and certification to LibreOffice.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libreoffice-calc && \
    rm -rf /var/lib/apt/lists/*

# Agent-first forks of python-docx, python-pptx, and openpyxl. Import names stay
# docx, pptx, and openpyxl. paperinstruments.com/paper-python
RUN uv pip install --system --break-system-packages \
    "paper-docx==${PAPER_DOCX_VERSION}" \
    "paper-pptx==${PAPER_PPTX_VERSION}" \
    "paper-xlsx==${PAPER_XLSX_VERSION}"
