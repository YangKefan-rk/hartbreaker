#!/bin/bash

# Path to the work directory
export WORKDIR="${WORKDIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export HARTATTACK_ROOT="${WORKDIR}/hartattack"
export DESIGN_DIR="${WORKDIR}/design-sources"

# The number of core Cascade can use to build and run
export HARTATTACK_CORES="${HARTATTACK_CORES:-15}"
export TOOLDIR="${WORKDIR}/.tools"

export HARTATTACK_SIMULATORS_DIR="${HARTATTACK_SIMULATORS_DIR:-${WORKDIR}/simulators}"
export HARTATTACK_DATADIR="${HARTATTACK_DATADIR:-${WORKDIR}/run-data}"
export HARTATTACK_BUGDIR="${HARTATTACK_BUGDIR:-${WORKDIR}/bug_backup}"
export PYTHONPATH="${HARTATTACK_ROOT}"
export HARTATTACK_ENV_SOURCED=yes
