#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
if [ -z "${WORKDIR}" ]; then
    source "${SCRIPT_DIR}"/env.sh
fi

lsenv() {
    echo "WORKDIR=${WORKDIR}"
    echo "HARTATTACK_ROOT=${HARTATTACK_ROOT}"
    echo "HARTATTACK_CORES=${HARTATTACK_CORES}"
    echo "DESIGN_DIR=${DESIGN_DIR}"
    echo "HARTATTACK_DATADIR=${HARTATTACK_DATADIR}"
    echo "HARTATTACK_BUGDIR=${HARTATTACK_BUGDIR}"
}

lsfn() {
    echo "Available functions:"
    echo ""
    echo "  lsenv                  - list environment variables"
    echo "  dshell                 - open a shell in the docker container"
    echo "  mstatus <value>        - decode mstatus register"
    echo "  rvdump <elf>           - disassemble ELF with colors"
}

# Disassemble an ELF with colored output
rvdump() {
    riscv64-unknown-elf-objdump -d --disassembler-color=on --visualize-jumps=color -M no-alias "$@"
}

# Decode the mstatus register
mstatus() {
    python3 "${SCRIPT_DIR}/mstatus_decoder.py" "$@"
}

# Open an interactive shell in the docker container with all designs available
dshell() {
    "${SCRIPT_DIR}/run_docker.sh" run zsh
}
