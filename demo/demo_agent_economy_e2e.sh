#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

cargo test -p turing-qualification new_project_agent_economy_e2e -- --nocapture
