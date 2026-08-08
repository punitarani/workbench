# syntax=docker/dockerfile:1
#
# Every workbench environment shares the `base` stage, so it carries only stable
# setup; environment-specific packages belong in the final stage.

# Bump deliberately: each pin invalidates the shared base layers.
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

FROM ubuntu:26.04 AS run-as-environment

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY run-as-environment.c .
RUN gcc -O2 -Wall -Wextra -o run-as-environment run-as-environment.c

FROM ubuntu:26.04 AS base

ARG PNPM_VERSION
ARG REWARDKIT_VERSION

ENV DEBIAN_FRONTEND=noninteractive \
    UV_SYSTEM_PYTHON=1 \
    UV_TOOL_DIR=/opt/uv-tools \
    UV_TOOL_BIN_DIR=/usr/local/bin

# Ubuntu 26.04 ships Python 3.14; the grep fails the build if that ever changes.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        sudo \
        python3 \
        python3-pip \
        python3-venv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    python3 --version | grep -qE '^Python 3\.14\.'

# Node arrives as a whole /usr/local tree, so it must precede the loose binaries.
COPY --from=node /usr/local /usr/local
COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun

RUN python3 -m pip install --upgrade --break-system-packages pip && \
    corepack enable && \
    corepack prepare "pnpm@${PNPM_VERSION}" --activate && \
    node --version && npm --version && pnpm --version && \
    bun --version && uv --version && pip --version

# environment serves the agent-facing tools, agent works, verifier grades, and
# sandbox runs untrusted verifier work. environment and verifier join the agent
# group to reach the workspace; sandbox joins verifier so the verifier can hand
# it data. Harbor addresses these users by name, so keep the UIDs stable.
RUN useradd -m -u 10000 -d /home/environment -s /bin/bash environment && \
    useradd -m -u 10001 -d /home/agent -s /bin/bash agent && \
    useradd -m -u 10002 -d /home/verifier -s /bin/bash verifier && \
    useradd -m -u 10003 -d /home/sandbox -s /bin/bash sandbox && \
    usermod -aG agent environment && \
    usermod -aG agent verifier && \
    usermod -aG verifier sandbox && \
    echo "verifier ALL=(sandbox) NOPASSWD: ALL" >> /etc/sudoers.d/verifier && \
    chmod 440 /etc/sudoers.d/verifier && \
    mkdir -p /home/agent/workspace /installed-agent /oracle /logs/agent /logs/verifier && \
    chown -R agent:agent /home/agent /installed-agent /oracle /logs/agent && \
    chown -R verifier:agent /logs/verifier && \
    chmod g+w /home/agent/workspace && \
    chmod -R a+rw /installed-agent /oracle && \
    chmod 775 /logs/agent /logs/verifier

# Harbor tasks and Reward Kit default to /app as the workspace.
RUN ln -sfn /home/agent/workspace /app

# Needs the environment user to exist for the owner and setuid bit.
COPY --from=run-as-environment /run-as-environment /usr/local/bin/run-as-environment
RUN chown environment:environment /usr/local/bin/run-as-environment && \
    chmod 4755 /usr/local/bin/run-as-environment

# Preinstalled so tests/test.sh can call `rewardkit /tests` without network;
# [all] adds the document and image criteria. harborframework.com/docs/rewardkit
RUN uv tool install --python python3 "harbor-rewardkit[all]==${REWARDKIT_VERSION}" && \
    chmod -R a+rX /opt/uv-tools && \
    rewardkit --help >/dev/null

WORKDIR /home/agent/workspace
CMD ["/bin/bash"]

FROM base

ARG PAPER_DOCX_VERSION
ARG PAPER_PPTX_VERSION
ARG PAPER_XLSX_VERSION

# paper-xlsx delegates formula recalculation and certification to LibreOffice.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libreoffice-calc && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Agent-first forks of python-docx, python-pptx, and openpyxl. Import names stay
# docx, pptx, and openpyxl. paperinstruments.com/paper-python
RUN uv pip install --system --break-system-packages \
    "paper-docx==${PAPER_DOCX_VERSION}" \
    "paper-pptx==${PAPER_PPTX_VERSION}" \
    "paper-xlsx==${PAPER_XLSX_VERSION}"
