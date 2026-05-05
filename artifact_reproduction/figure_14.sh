#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only
# Figure 14: Coverage comparison (HartBreaker vs RISCV-DV)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

COV_COMPARE_DIR="${WORKDIR}/coverage_comparaison"
DATA_DIR="${WORKDIR}/artifact_reproduction/data/coverage"
COV_DATA_DIR="${DATA_DIR}/cov_data"
CORPUS_DIR="${DATA_DIR}/corpus"
RISCVDV_CORPUS="${WORKDIR}/artifact_reproduction/data/riscvdv_corpus"
SIM_PATH="${COV_COMPARE_DIR}/out/rfuzz-sim"
TIMING_FILE="${DATA_DIR}/timing.jsonl"
# Override via env: HARTATTACK_CORES.
NUM_CORES="${HARTATTACK_CORES:-200}"

# Quick mode: shorter timeouts for testing the pipeline
QUICK=false
if [ "${1}" = "--quick" ]; then
    QUICK=true
    echo "=== QUICK MODE: reduced timeouts ==="
fi

mkdir -p "${DATA_DIR}" "${CORPUS_DIR}"

echo "=== Figure 14: Coverage Comparison (HartBreaker vs RISCV-DV) ==="
echo ""

# ── Phase 1: Build coverage-instrumented simulator ──
if [ -x "${SIM_PATH}" ]; then
    echo "--- Phase 1: Simulator already built, skipping ---"
else
    echo "--- Phase 1: Building coverage-instrumented simulator ---"
    time_step "${TIMING_FILE}" "build_sources" \
        run_in_covcollect_docker "cd ${COV_COMPARE_DIR} && bash make_sources.sh rfuzz"

    time_step "${TIMING_FILE}" "build_simulator" \
        run_in_covcollect_docker "cd ${COV_COMPARE_DIR} && bash build_sim.sh rfuzz"
fi

# ── Phase 2: Generate HartBreaker test corpus ──
echo ""

if [ "$QUICK" = true ]; then
    export CASCADE_INTERRUPT_TIMEOUT=60
    export CASCADE_MCM_TIMEOUT=60
    export CASCADE_NUM_CORES=${NUM_CORES}
fi

if [ -d "${CORPUS_DIR}/hartattack" ] && [ "$(ls -A "${CORPUS_DIR}/hartattack" 2>/dev/null)" ]; then
    echo "--- Phase 2: HartBreaker corpus already exists, skipping ---"
else
    echo "--- Phase 2: Generating HartBreaker test corpus ---"
    time_step "${TIMING_FILE}" "generate_hartbreaker_corpus" \
        run_in_docker "cd ${HARTATTACK_ROOT} \
            && CORPUS_OUT=${CORPUS_DIR}/hartattack \
            CASCADE_INTERRUPT_TIMEOUT=${CASCADE_INTERRUPT_TIMEOUT:-950} \
            CASCADE_MCM_TIMEOUT=${CASCADE_MCM_TIMEOUT:-20000} \
            CASCADE_NUM_CORES=${NUM_CORES} \
            bash ${COV_COMPARE_DIR}/run_cascade.sh"
fi

# ── Phase 3: Collect coverage ──
echo ""

if [ -d "${COV_DATA_DIR}" ] && [ "$(ls -A "${COV_DATA_DIR}" 2>/dev/null)" ]; then
    echo "--- Phase 3: Coverage data already exists, skipping ---"
else
    echo "--- Phase 3: Collecting coverage ---"

    # Time budget per corpus (0 = no limit)
    if [ "$QUICK" = true ]; then
        TIME_BUDGET="--time-budget 120"
    else
        TIME_BUDGET=""
    fi

    # 3a: HartBreaker corpus
    echo "  Collecting coverage for HartBreaker corpus..."
    time_step "${TIMING_FILE}" "coverage_hartbreaker" \
        run_in_covcollect_docker "cd ${COV_COMPARE_DIR} \
            && python3 orchestrate.py \
                --sim ${SIM_PATH} \
                --corpus ${CORPUS_DIR} \
                --num-cores ${NUM_CORES} \
                --output ${COV_DATA_DIR} \
                --force ${TIME_BUDGET}"

    # 3b: RISCV-DV corpus (pre-built artifact)
    # No --force: preserve hartbreaker data from step 3a
    echo "  Collecting coverage for RISCV-DV corpus..."
    time_step "${TIMING_FILE}" "coverage_riscvdv" \
        run_in_covcollect_docker "cd ${COV_COMPARE_DIR} \
            && python3 orchestrate.py \
                --sim ${SIM_PATH} \
                --corpus ${RISCVDV_CORPUS} \
                --num-cores ${NUM_CORES} \
                --output ${COV_DATA_DIR} ${TIME_BUDGET}"
fi

# ── Phase 4: Plot ──
echo ""
echo "--- Phase 4: Generating plot ---"
time_step "${TIMING_FILE}" "plot" \
    run_in_covcollect_docker "cd ${COV_COMPARE_DIR} \
        && python3 plot.py ${COV_DATA_DIR} \
            --output ${DATA_DIR}/plot_out \
            --force \
            --timing ${TIMING_FILE} \
            --riscvdv-metadata ${RISCVDV_CORPUS}/metadata.json \
            --num-cores ${NUM_CORES} \
        && mv ${DATA_DIR}/plot_out/cov_evolution.pdf ${FIGURES_DIR}/figure_14.pdf"

echo ""
echo "Timing log saved to ${TIMING_FILE}"
echo "Done. Figure saved to ./figures/figure_14.pdf"
