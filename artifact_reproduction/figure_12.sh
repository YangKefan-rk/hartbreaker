#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only
# Figure 12: Simulation time across designs (uses shared benchmark data)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

DATA_DIR="${WORKDIR}/artifact_reproduction/data/benchmark"

echo "=== Figure 12: Simulation Time Across Designs ==="
echo ""

echo "Generating plot..."
run_in_docker "cd ${HARTATTACK_ROOT} \
    && python3 tests/stats_simtime/plot_throughput_comparison.py \
        ${DATA_DIR} \
    && mv simulation_time_boxplot.pdf ${FIGURES_DIR}/figure_12.pdf"

echo ""
echo "Done. Figure saved to ./figures/figure_12.pdf"
