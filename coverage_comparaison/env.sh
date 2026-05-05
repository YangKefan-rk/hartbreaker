#!/bin/sh
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only

# riscv dv
export QUESTA_HOME=/usr/local/questa-2022-03/questasim/
export RISCV_TOOLCHAIN=$RISCV
export RISCV_OBJCOPY=$RISCV_TOOLCHAIN/bin/riscv64-unknown-elf-objcopy
export RISCV_GCC=$RISCV_TOOLCHAIN/bin/riscv64-unknown-elf-gcc
export SPIKE_PATH=$RISCV_TOOLCHAIN/bin/
