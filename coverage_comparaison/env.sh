#!/bin/sh

# riscv dv
export QUESTA_HOME=/usr/local/questa-2022-03/questasim/
export RISCV_TOOLCHAIN=$RISCV
export RISCV_OBJCOPY=$RISCV_TOOLCHAIN/bin/riscv64-unknown-elf-objcopy
export RISCV_GCC=$RISCV_TOOLCHAIN/bin/riscv64-unknown-elf-gcc
export SPIKE_PATH=$RISCV_TOOLCHAIN/bin/
