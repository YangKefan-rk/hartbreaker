#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only

ROOT_DIR=$(dirname -- ${BASH_SOURCE[0]})

echo "======== Making all designs ========"

echo "1/4 Building Chipyard based design"
$ROOT_DIR/build_chipyard.sh

echo "2/4 Building Toooba"
$ROOT_DIR/build_toooba.sh

echo "3/4 Building XiangShan"
$ROOT_DIR/build_xs.sh

echo "4/4 Building NaxRiscv"
$ROOT_DIR/build_docker.sh naxriscv
