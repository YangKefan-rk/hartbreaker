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
OUT_FILE="boom_core.v"
VERILATOR_BUILD_DIR="verilator_build"
TOP_LEVEL="TestDriver"

: "${MILESAN_YOSYS:?must be set; run this script inside the covcollect Docker container}"
YOSYS="${MILESAN_YOSYS}"
YOSYS_SCRIPT="${ROOT_DIR}/yosys_scripts/${INSTRUMENTATION}.ys.tcl"
PYTHON_SCRIPT="${ROOT_DIR}/python_scripts/"


ORIGINAL_SOC_DIR="chipyard.harness.TestHarness.MyTrippleBoomV3ConfigLog"
# ORIGINAL_SOC_DIR="chipyard.harness.TestHarness.MyBoomV4ConfigLog"
ORIGINAL_SRC="${ROOT_DIR}/${ORIGINAL_SOC_DIR}/gen-collateral"

##
# create single verilog source file, skip if already generated
##

if [ ! -f $OUT_DIR/boom_partial.v ]; then
    echo "[+] Translating to verilog"
    sv2v -w $OUT_DIR/boom_partial.v $ORIGINAL_SRC/*.sv
fi

if [ ! -f $OUT_DIR/$OUT_FILE ]; then
    echo "[+] Concatinating files"
    cat $OUT_DIR/boom_partial.v <(echo) $ORIGINAL_SRC/GenericDigitalInIOCell.v <(echo) $ORIGINAL_SRC/GenericDigitalOutIOCell.v <(echo) $ORIGINAL_SRC/$ORIGINAL_SOC_DIR.top.mems.v <(echo) $ORIGINAL_SRC/plusarg_reader.v > $OUT_DIR/$OUT_FILE
    echo "[+] Cleaning output"
    sed -i '/\$finish;/d' $OUT_DIR/$OUT_FILE
    awk 'NR==1 {prev=$0; next} /\$fwrite/ {prev=""; next} {print prev; prev=$0} END {print prev}' $OUT_DIR/$OUT_FILE > temp_file && mv temp_file $OUT_DIR/$OUT_FILE
    sed -i '/\$finish;/d' $OUT_DIR/$OUT_FILE
    sed -i 's/initial if (reset)/initial/g' $OUT_DIR/$OUT_FILE
fi

##
# Invoke yosys
##

export VERILOG_INPUT=$OUT_DIR/$OUT_FILE
export VERILOG_OUTPUT="${OUT_DIR}/${INSTRUMENTATION}.v"
export TOP_MODULE="ChipTop"
echo "[+] applying yosys pass"
if [ ! -f $VERILOG_OUTPUT ]; then
    $YOSYS -c $YOSYS_SCRIPT -l $OUT_DIR/$INSTRUMENTATION.log

    ##
    # for rfuzz apply post processing
    ##

    if [ "$INSTRUMENTATION" == "rfuzz" ]; then
        echo "[+] cleaning up rfuzz output"
        python $PYTHON_SCRIPT/divide_concat_into_subconcats.py $VERILOG_OUTPUT $VERILOG_OUTPUT
    fi
fi

echo "done"
