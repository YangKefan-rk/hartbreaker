#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only
# Common setup for artifact reproduction scripts.
# Source this at the top of each figure script.
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)
source "${SCRIPT_DIR}/../scripts/env.sh"

FIGURES_DIR="${WORKDIR}/figures"
mkdir -p "${FIGURES_DIR}"

# Run a command inside the run container.
# Usage: run_in_docker <command...>
run_in_docker() {
    "${WORKDIR}/scripts/run_docker.sh" run "$*"
}

# Run a command inside the covcollect container.
# Usage: run_in_covcollect_docker <command...>
run_in_covcollect_docker() {
    "${WORKDIR}/scripts/run_docker.sh" covcollect "$*"
}

# Record elapsed time to a JSON timing file.
# Usage: time_step <timing_file> <step_name> <command...>
time_step() {
    local timing_file="$1"
    local step_name="$2"
    shift 2
    local start_time=$(date +%s)
    "$@"
    local end_time=$(date +%s)
    local elapsed=$((end_time - start_time))
    echo "{\"step\": \"${step_name}\", \"elapsed_s\": ${elapsed}, \"timestamp\": \"$(date -Iseconds)\"}" >> "${timing_file}"
    echo "  [timing] ${step_name}: ${elapsed}s"
}
