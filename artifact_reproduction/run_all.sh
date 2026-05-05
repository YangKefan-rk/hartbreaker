#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only
# Reproduce all figures from the paper in one pass.
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "============================================"
echo "  HartBreaker Artifact Reproduction"
echo "============================================"
echo ""

# Phase 1: Collect shared benchmark data (used by figures 10-13)
echo ">>> Collecting benchmark data (figures 10-13) <<<"
bash "${SCRIPT_DIR}/collect_data.sh"
echo ""

# Phase 2: Generate all figures
for fig in 8 9 10 11 12 13 14 15; do
    echo ">>> Figure ${fig} <<<"
    bash "${SCRIPT_DIR}/figure_${fig}.sh"
    echo ""
done

echo "============================================"
echo "  All figures generated in ./figures/"
echo "============================================"
