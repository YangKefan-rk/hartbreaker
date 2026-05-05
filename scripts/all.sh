#!/bin/bash

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
if [ -z "${WORKDIR}" ]; then
    source "${SCRIPT_DIR}"/env.sh
fi

export PATH=:${TOOLDIR}/helix-25.01.1-x86_64-linux/:$PATH
export PATH=:${TOOLDIR}/:$PATH
export PATH=:/usr/local/questa-2022-03/questasim/bin/:$PATH
export PATH=:${TOOLDIR}/verilator/bin:$PATH
export PATH=:${TOOLDIR}/firtool/bin:$PATH
export RISCV="${TOOLDIR}/riscv"
export PATH=:${RISCV}/bin:$PATH
export PATH=:${TOOLDIR}/venv/bin:$PATH
export LD_LIBRARY_PATH=:${TOOLDIR}/riscv/lib/:$LD_LIBRARY_PATH

# openpiton
export VERILATOR_ROOT=${TOOLDIR}/verilator/
export C_INCLUDE_PATH=$RISCV/include:$VERILATOR_ROOT/include
export CPLUS_INCLUDE_PATH=$RISCV/include:$VERILATOR_ROOT/include
export PATH=:${TOOLDIR}/sv2v/bin:$PATH

export BSPATH=${TOOLDIR}/bsc-2025.01.1-ubuntu-22.04
export BLUESPECDIR=$BSPATH/lib
export PATH=$BSPATH/bin:$PATH

# dartagnan
export DAT3M_HOME=$TOOLDIR/Dat3M
export DAT3M_OUTPUT=$DAT3M_HOME/output

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
