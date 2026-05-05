#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only

# runs cascade

# Set the working directory
# If WORKDIR is not set, use a default path or exit with error
if [ -z "$WORKDIR" ]; then
    echo "Error: WORKDIR environment variable is not set"
    exit 1
fi

# Path to the main.py file
MAIN_PY_PATH="$WORKDIR/hartattack/main.py"
HARTATTACK_DIR="$WORKDIR/hartattack"
ELF_PATH="$WORKDIR/run-data/"
CORPUS_PATH="${CORPUS_OUT:-$WORKDIR/paper_experiments/collect_coverage/corpus/hartattack}"

# Check if the main.py file exists
if [ ! -f "$MAIN_PY_PATH" ]; then
    echo "Error: main.py not found at $MAIN_PY_PATH"
    exit 1
fi

# Change to the hartattack directory before running
cd "$HARTATTACK_DIR" || exit 1

# Define scenarios
INTERRUPT_SCENARIO_ARGS="--fuzz-interrupts --skip-no-interrupts"
MCM_SCENARIO_ARGS="--fuzz-mcm --verify-memory-trace dat --max-n-consecutive-memops 70"

# Array of scenarios with descriptive names
declare -a SCENARIOS=(
    "INTERRUPT:$INTERRUPT_SCENARIO_ARGS"
    "MCM:$MCM_SCENARIO_ARGS"
)

rm -rf $ELF_PATH/elfs
rm -rf $ELF_PATH/dbgcmds
rm -rf $CORPUS_PATH/*

SCENARIO_NAME="INTERRUPT"

echo "========================================"
echo "Starting scenario: $SCENARIO_NAME"
echo "Arguments: $SCENARIO_ARGS"
echo "Running from directory: $(pwd)"
echo "========================================"

# we aloocate more time for the MCM generation, because the throuput is a lot lower

# this has some output, but should not affect overall perf too much
timeout ${CASCADE_INTERRUPT_TIMEOUT:-950} python3 -u main.py trippleboomv3 --keep-tmpfiles --num-cores ${CASCADE_NUM_CORES:-200} $INTERRUPT_SCENARIO_ARGS </dev/null

# Check the exit status
EXIT_CODE=$?
if [ $EXIT_CODE -eq 124 ]; then
    echo "Scenario $SCENARIO_NAME terminated normally"
elif [ $EXIT_CODE -eq 0 ]; then
    echo "Scenario $SCENARIO_NAME completed successfully before timeout"
else
    echo "Scenario $SCENARIO_NAME exited with error code: $EXIT_CODE"
    echo "Continuing to next scenario..."
fi

# move generated rtl elfs
mkdir -p $CORPUS_PATH/$SCENARIO_NAME
mv $ELF_PATH/elfs/rtl* $CORPUS_PATH/$SCENARIO_NAME

# clear current elf dir
rm -rf $ELF_PATH/elfs
rm -rf $ELF_PATH/dbgcmds

SCENARIO_NAME="MCM"

echo "========================================"
echo "Starting scenario: $SCENARIO_NAME"
echo "Arguments: $SCENARIO_ARGS"
echo "Running from directory: $(pwd)"
echo "========================================"

# this has some output, but should not affect overall perf too much
timeout ${CASCADE_MCM_TIMEOUT:-20000} python3 -u main.py trippleboomv3 --keep-tmpfiles --num-cores ${CASCADE_NUM_CORES:-200} $MCM_SCENARIO_ARGS </dev/null

# Check the exit status
EXIT_CODE=$?
if [ $EXIT_CODE -eq 124 ]; then
    echo "Scenario $SCENARIO_NAME terminated normally"
elif [ $EXIT_CODE -eq 0 ]; then
    echo "Scenario $SCENARIO_NAME completed successfully before timeout"
else
    echo "Scenario $SCENARIO_NAME exited with error code: $EXIT_CODE"
    echo "Continuing to next scenario..."
fi

# move generated rtl elfs
mkdir -p $CORPUS_PATH/$SCENARIO_NAME
mv $ELF_PATH/elfs/rtl* $CORPUS_PATH/$SCENARIO_NAME

# clear current elf dir
rm -rf $ELF_PATH/elfs
rm -rf $ELF_PATH/dbgcmds

echo "All scenarios completed!"
