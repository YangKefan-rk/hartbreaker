#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only

set -e

# Check for exactly one argument
if [ $# -ne 1 ]; then
    echo "Usage: $0 <argument>"
    echo "Argument must be 'passthrough' or 'rfuzz'"
    exit 1
fi

# Check if argument is valid
if [ "$1" != "passthrough" ] && [ "$1" != "rfuzz" ]; then
    echo "Invalid argument: $1. Must be 'passthrough' or 'rfuzz'"
    exit 1
fi

INSTRUMENTATION=$1

ROOT_DIR=$(pwd)
SRC_DIR="${ROOT_DIR}/sources"
OUT_DIR="${ROOT_DIR}/out"
OUT_SIM_NAME="${INSTRUMENTATION}-sim"
VERILATOR_BUILD_DIR="verilator_build_${INSTRUMENTATION}"
TOP_LEVEL="TestDriver"

ORIGINAL_SOC_DIR="chipyard.harness.TestHarness.MyTrippleBoomV3ConfigLog"
ORIGINAL_SRC="${ROOT_DIR}/${ORIGINAL_SOC_DIR}/gen-collateral"

# Resolve @COV_COMPARE_DIR@ in the filelist to this checkout's path.
RESOLVED_F="${OUT_DIR}/sim_files_${INSTRUMENTATION}.resolved.f"
mkdir -p "$OUT_DIR"
sed "s|@COV_COMPARE_DIR@|${ROOT_DIR}|g" "$SRC_DIR/sim_files_$INSTRUMENTATION.f" > "$RESOLVED_F"

VERILATOR_FLAGS="--main --timing --cc --exe"

CFLAGS="-O3 -std=c++17 -I${RISCV}/include -I${SRC_DIR}/DRAMSim2 -I${ORIGINAL_SRC} -DVERILATOR"
LDFLAGS=" -L${RISCV}/lib -Wl,-rpath,${RISCV}/lib -L${ORIGINAL_SRC} -L${SRC_DIR}/DRAMSim2 -lriscv -lfesvr -ldramsim"

##
# Compile the design with Verilator
##
verilator $VERILATOR_FLAGS \
    -CFLAGS "$CFLAGS" \
    -LDFLAGS "$LDFLAGS" \
    --threads 1 \
    --threads-dpi all \
    -O3 \
    --x-assign fast \
    --x-initial fast \
    --output-split 10000 \
    --output-split-cfuncs 100 \
    --assert \
    -Wno-fatal \
    --timescale 1ns/1ps \
    --max-num-width 1048576 \
    +define+CLOCK_PERIOD=1.0 \
    +define+RESET_DELAY=777.7 \
    +define+PRINTF_COND=$TOP_LEVEL.printf_cond \
    +define+STOP_COND=!$TOP_LEVEL.reset \
    +define+MODEL=TestHarness \
    +define+RANDOMIZE_MEM_INIT \
    +define+RANDOMIZE_REG_INIT \
    +define+RANDOMIZE_GARBAGE_ASSIGN \
    +define+RANDOMIZE_INVALID_ASSIGN \
    +define+VERILATOR \
    --top-module $TOP_LEVEL \
    --vpi \
    -f "$RESOLVED_F" \
    -o $OUT_DIR/$OUT_SIM_NAME \
    -Mdir $OUT_DIR/$VERILATOR_BUILD_DIR

##
# Make the simulation binary
##
make VM_PARALLEL_BUILDS=1 -C ${OUT_DIR}/$VERILATOR_BUILD_DIR -f V$TOP_LEVEL.mk
