#!/bin/bash

set -euo pipefail

# Colors
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RESET="\033[0m"

CHECK_DIFF_ONLY=false

# Parse command line flags
for arg in "$@"; do
    case "$arg" in
        --check-diff-only)
            echo -e "${YELLOW}Running in diff-only mode (no snapshot updates).${RESET}"
            CHECK_DIFF_ONLY=true
            ;;
        *)
            echo -e "${RED}Unknown argument: $arg${RESET}"
            echo "Usage: $0 [--check-diff-only]"
            exit 1
            ;;
    esac
done

# Determine directory of this script (resolves symlinks too)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd "$SCRIPT_DIR"

TESTS_FILE="tests.yaml"
SNAPSHOT_DIR="snapshots"

mkdir -p "$SNAPSHOT_DIR"

# Read test names
TEST_NAMES=$(yq '.tests | keys | .[]' "$TESTS_FILE")

overall_ok=true

for test_name in $TEST_NAMES; do
    echo -e "${YELLOW}Processing test: $test_name${RESET}"

    VALUES_ARGS=()
    VALUES=$(yq ".tests.\"$test_name\"[]" "$TESTS_FILE")
    for values_file in $VALUES; do
        VALUES_ARGS+=( --values "$values_file" )
    done
    VALUES_ARGS+=( --values "tests/$test_name" )

    SNAPSHOT_PATH="${SNAPSHOT_DIR}/${test_name%.yaml}.yaml"

    # Render template to temp file
    TMP_OUTPUT=$(mktemp)
    helm template ./ "${VALUES_ARGS[@]}" > "$TMP_OUTPUT"

    if $CHECK_DIFF_ONLY; then
        if [[ ! -f "$SNAPSHOT_PATH" ]]; then
            echo -e "${RED}❌ Snapshot missing: $SNAPSHOT_PATH${RESET}"
            overall_ok=false
            continue
        fi

        if diff -u "$SNAPSHOT_PATH" "$TMP_OUTPUT" > /dev/null; then
            echo -e "${GREEN}✔ Snapshot up to date: $SNAPSHOT_PATH${RESET}"
        else
            echo -e "${RED}❌ Snapshot out of date: $SNAPSHOT_PATH${RESET}"
            echo -e "${YELLOW}--- Diff: ---${RESET}"
            diff -u "$SNAPSHOT_PATH" "$TMP_OUTPUT" || true
            overall_ok=false
        fi
    else
        # Update snapshot
        mv "$TMP_OUTPUT" "$SNAPSHOT_PATH"
        echo -e "${GREEN}✔ Snapshot updated: $SNAPSHOT_PATH${RESET}"
    fi
done

if $CHECK_DIFF_ONLY; then
    if $overall_ok; then
        echo -e "${GREEN}✔ All snapshots are up to date.${RESET}"
        exit 0
    else
        echo -e "${RED}❌ Some snapshots are outdated.${RESET}"
        exit 1
    fi
fi
