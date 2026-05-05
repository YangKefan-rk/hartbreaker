#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only

# Path to the work directory
export WORKDIR="${WORKDIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export HARTATTACK_ROOT="${WORKDIR}/hartattack"
export DESIGN_DIR="${WORKDIR}/design-sources"

# Cores used both for Docker builds (make -j) and for parallel fuzzing in the
# reproduction experiments. Override via `export HARTATTACK_CORES=<N>` before
# launching any build or figure script. The default is intentionally low so
# Docker builds work on small machines; bump it for fuzzing on a beefy host.
export HARTATTACK_CORES="${HARTATTACK_CORES:-15}"
export TOOLDIR="${WORKDIR}/.tools"

export HARTATTACK_SIMULATORS_DIR="${HARTATTACK_SIMULATORS_DIR:-${WORKDIR}/simulators}"
export HARTATTACK_DATADIR="${HARTATTACK_DATADIR:-${WORKDIR}/run-data}"
export HARTATTACK_BUGDIR="${HARTATTACK_BUGDIR:-${WORKDIR}/bug_backup}"
export PYTHONPATH="${HARTATTACK_ROOT}"
export HARTATTACK_ENV_SOURCED=yes
