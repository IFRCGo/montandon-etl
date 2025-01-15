FROM python:3.12-slim-bullseye AS base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

LABEL maintainer="Togglecorp Dev"

ENV PYTHONUNBUFFERED=1

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
        gcc libc-dev gdal-bin libproj-dev \
        # Helper packages
        wait-for-it \
    && uv sync --frozen --no-install-project  --no-dev \
    # Clean-up
    && apt-get remove -y gcc libc-dev libproj-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*


COPY . /code/
