#!/usr/bin/env bash
# Legacy verify script delegating to the unified CLI

set -e
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

./camz verify
