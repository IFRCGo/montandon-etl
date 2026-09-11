#!/bin/bash

# NOTE: The actual implementation lives in the shared fugit submodule.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export SCRIPT_DIR

exec "$SCRIPT_DIR/../fugit/scripts/helm-update-snapshots.sh" "$@"
