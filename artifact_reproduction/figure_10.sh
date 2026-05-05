#!/bin/bash
# Figure 10: Verification throughput overhead (uses shared benchmark data)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

DATA_DIR="${WORKDIR}/artifact_reproduction/data/benchmark"

echo "=== Figure 10: Verification Throughput Overhead ==="
echo ""

echo "Generating plot..."
run_in_docker "cd ${HARTATTACK_ROOT} \
    && python3 tests/stats_verification_throughput/plot_verification_impact.py \
        ${DATA_DIR} \
    && mv verification_throughput_dualrocket.pdf ${FIGURES_DIR}/figure_10.pdf"

echo ""
echo "Done. Figure saved to ./figures/figure_10.pdf"
