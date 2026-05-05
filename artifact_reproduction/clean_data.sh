#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only
# Remove all generated data so figure scripts will regenerate from scratch.
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

echo "=== Cleaning generated data ==="

# Figures 10-13: Shared benchmark data
rm -rf "${WORKDIR}/artifact_reproduction/data/ppo_rules"
echo "Removed figure 8 data"

# Figures 10-13: Shared benchmark data
rm -rf "${WORKDIR}/artifact_reproduction/data/benchmark"
echo "Removed figure 10-13 data"

# Figure 14: Coverage comparison
rm -rf "${WORKDIR}/artifact_reproduction/data/coverage"
echo "Removed figure 14 data"

# Figure 15: Time-to-Exposure
rm -rf "${WORKDIR}/artifact_reproduction/data/tte"
echo "Removed figure 15 data"

# Generated figures
rm -rf "${FIGURES_DIR}"
echo "Removed generated figures"

echo ""
echo "Done. All generated data has been removed."
