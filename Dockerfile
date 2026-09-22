FROM python:3.13-slim-trixie AS base
COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /uvx /bin/

LABEL maintainer="Montandon Dev"
LABEL org.opencontainers.image.source="https://github.com/IFRCGo/montandon-etl/"

ENV PYTHONUNBUFFERED=1

ENV UV_SYSTEM_PYTHON=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT="/usr/local/"

WORKDIR /code

COPY libs /code/libs

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    apt-get update -y \
    && apt-get install -y --no-install-recommends \
        # Build required packages
        build-essential libgdal-dev \
        gcc libc-dev gdal-bin libproj-dev \
        # PCRE headers so the pip-built uWSGI gets internal routing support
        # (needed for the `route = ... donotlog:` probe-log suppression in uwsgi.ini)
        libpcre2-dev \
        # Required by uv to fetch the banjo-utils git dependency
        git \
        # Helper packages
        procps \
        jq wait-for-it \
    # FIXME: Add condition to skip dev dependencies
    && uv lock --locked --offline \
    # Evict any cached uWSGI wheel so it recompiles against libpcre2-dev now that
    # the headers are present (a wheel cached before PCRE existed lacks routing support).
    && uv cache clean uwsgi \
        && uv sync --frozen --no-install-project --all-groups \
    # Clean-up
    && apt-get remove -y \
        gcc libc-dev libproj-dev git \
        build-essential libgdal-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . /code/
