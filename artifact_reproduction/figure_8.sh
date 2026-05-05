#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only
# Figure 8: PPO rule usage probabilities
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

PPO_DATA="${HARTATTACK_ROOT}/tests/stats_ppo_rules/ppo_stats_out/ppo_rules_dualrocket.json"

echo "=== Figure 8: PPO Rule Usage Probabilities ==="
echo ""

echo "Generating test programs and collecting PPO rule statistics..."
run_in_docker "cd ${HARTATTACK_ROOT} \
    && python3 -u tests/stats_ppo_rules/main.py"

echo "Generating plot..."
run_in_docker "cd ${HARTATTACK_ROOT} \
    && python3 tests/stats_ppo_rules/plot_ppo_rules.py \
        tests/stats_ppo_rules/ppo_stats_out/ppo_rules_dualrocket.json \
        ${FIGURES_DIR}/figure_8.png"

echo ""
echo "Done. Figure saved to ./figures/figure_8.pdf"
