#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [ -z "${WORKDIR}" ]; then
  source "${SCRIPT_DIR}/env.sh"
fi

design_name="$1"
SCRIPT_OR_COMMAND="${@:2}"
echo "Running: ${SCRIPT_OR_COMMAND}"

EXTRA_VOLUMES=()
# Mount data and bug dirs if they live outside the working directory
case "${HARTATTACK_DATADIR}" in
  "${WORKDIR}"/*) ;;
  *) EXTRA_VOLUMES+=(-v "${HARTATTACK_DATADIR}":"${HARTATTACK_DATADIR}":Z) ;;
esac
case "${HARTATTACK_BUGDIR}" in
  "${WORKDIR}"/*) ;;
  *) EXTRA_VOLUMES+=(-v "${HARTATTACK_BUGDIR}":"${HARTATTACK_BUGDIR}":Z) ;;
esac

TTY_FLAG=()
if [ -t 0 ]; then
  TTY_FLAG=(-it)
fi

docker run \
  --rm \
  "${TTY_FLAG[@]}" \
  -v "${WORKDIR}":"${WORKDIR}":Z \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --group-add "$(stat -c '%g' /var/run/docker.sock)" \
  "${EXTRA_VOLUMES[@]}" \
  -e HARTATTACK_CORES="${HARTATTACK_CORES}" \
  -e HARTATTACK_NUM_PROGRAMS \
  -e HARTATTACK_NUM_ELFS \
  -e WORKDIR="${WORKDIR}" \
  -e HARTATTACK_ROOT="${HARTATTACK_ROOT}" \
  -e HARTATTACK_DATADIR="${HARTATTACK_DATADIR}" \
  -e HARTATTACK_BUGDIR="${HARTATTACK_BUGDIR}" \
  -e HARTATTACK_SIMULATORS_DIR="${HARTATTACK_SIMULATORS_DIR}" \
  --user "$(id -u)":"$(id -g)"\
  "$design_name":v1 bash -c "$SCRIPT_OR_COMMAND"
