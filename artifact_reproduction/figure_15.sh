#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only
# Figure 15: Time-to-Exposure (TTE) for bug rediscovery
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

DATA_DIR="${WORKDIR}/artifact_reproduction/data/tte"
TIMING_FILE="${DATA_DIR}/timing.jsonl"
TTE_SCRIPT="tests/stats_tte/main.py"
PLOT_SCRIPT="tests/stats_tte/plot_tte.py"

DESIGNS=("dualboomv4" "toooba" "naxriscv_mcm" "naxriscv_int" "xiangshan")

mkdir -p "${DATA_DIR}"

echo "=== Figure 15: Time-to-Exposure (Bug Rediscovery) ==="
echo ""

# ── Phase 1: Run TTE experiments per design ──
for design in "${DESIGNS[@]}"; do
    echo "--- ${design}: Running TTE experiment ---"
    mkdir -p "${DATA_DIR}/${design}"
    time_step "${TIMING_FILE}" "tte_${design}" \
        run_in_docker "cd ${HARTATTACK_ROOT} \
            && python3 -u ${TTE_SCRIPT} ${design} \
                --output-dir ${DATA_DIR}"
done

# ── Phase 2: Plot ──
echo ""
echo "--- Generating plot ---"
time_step "${TIMING_FILE}" "plot" \
    run_in_docker "cd ${HARTATTACK_ROOT} \
        && python3 ${PLOT_SCRIPT} ${DATA_DIR} \
        && mv tte_avg.pdf ${FIGURES_DIR}/figure_15.pdf"

echo ""
echo "Timing log saved to ${TIMING_FILE}"
echo "Done. Figure saved to ./figures/figure_15.pdf"
