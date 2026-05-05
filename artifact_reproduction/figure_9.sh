#!/bin/bash
# Figure 9: Memory operations distance distribution
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

DESIGN="trippleboomv3"
NUM_ELFS=10000
NUM_CORES=150

MEMOP_DATA="${HARTATTACK_ROOT}/tests/stats_memops_distance/memop_dist_probability.pdf"

echo "=== Figure 9: Memory Operations Distance ==="
echo ""

echo "Generating ${NUM_ELFS} programs on ${DESIGN} with ${NUM_CORES} cores."
run_in_docker "cd ${HARTATTACK_ROOT} \
    && python3 -u tests/stats_memops_distance/main.py ${DESIGN} ${NUM_ELFS} ${NUM_CORES} \
    && mv tests/stats_memops_distance/memop_dist_probability.pdf ${FIGURES_DIR}/figure_9.pdf"

echo ""
echo "Done. Figure saved to ./figures/figure_9.pdf"
