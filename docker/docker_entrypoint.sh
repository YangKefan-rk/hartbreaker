#!/bin/sh
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only

# FIXME when releasing, add and create the user here

export HARTATTACK_SIMULATORS_DIR="${HARTATTACK_SIMULATORS_DIR:-${WORKDIR}/simulators}"
export HARTATTACK_DATADIR="${HARTATTACK_DATADIR:-${WORKDIR}/run-data}"
export HARTATTACK_BUGDIR="${HARTATTACK_BUGDIR:-${WORKDIR}/bug_backup}"
export PYTHONPATH="${HARTATTACK_ROOT}"
export HARTATTACK_ENV_SOURCED=yes
export LD_LIBRARY_PATH=:/opt/riscv/lib/:$LD_LIBRARY_PATH

. "${WORKDIR}"/scripts/env.sh

exec "$@"
