#!/bin/bash
# Collect all benchmark data used by figures 10-13.
# Skips runs whose JSONL output already exists and is non-empty.
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

DATA_DIR="${WORKDIR}/artifact_reproduction/data/benchmark"
COLLECTOR="tests/collect_data/main.py"
NUM_PROGRAMS=500
NUM_INSTRS=(1000 2000 4000 8000)

# design  verif_flag
#   Figures 11-13 designs (one mode each)
#   Figure 10 design: dualrocket needs both modes
RUNS=(
    "tripplerocket   --verif"
    "tripplerocket"
    "trippleboomv3   --verif"
    "toooba-3core    --verif"
    "xiangshan"
    "naxriscv        --verif"
)

mkdir -p "${DATA_DIR}"

echo "=== Collecting benchmark data ==="
echo "Instruction sizes: ${NUM_INSTRS[*]}"
echo ""

for run in "${RUNS[@]}"; do
    # Parse design and verif flag
    design=$(echo "$run" | awk '{print $1}')
    verif_flag=$(echo "$run" | awk '{print $2}')

    if [ -n "$verif_flag" ]; then
        VERIF_SUFFIX="verif"
    else
        VERIF_SUFFIX="noverif"
    fi

    for num_instr in "${NUM_INSTRS[@]}"; do
        DATA_FILE="${DATA_DIR}/${design}/${num_instr}/${design}_${num_instr}_${VERIF_SUFFIX}.jsonl"
        if [ -s "${DATA_FILE}" ]; then
            echo "--- ${design} / ${num_instr} / ${VERIF_SUFFIX}: data exists, skipping ---"
            echo "--- To re-generate the data, run ./clean-data.sh"
            continue
        fi

        TOTAL_NUM_INSTRS=$((num_instr * NUM_PROGRAMS))

        echo "--- ${design} / ${num_instr} / ${VERIF_SUFFIX} (${NUM_PROGRAMS} programs) ---"

        run_in_docker "cd ${HARTATTACK_ROOT} \
            && HARTATTACK_BENCH_DIR=${DATA_DIR} \
            python3 -u ${COLLECTOR} ${design} \
                --total-num-instrs ${TOTAL_NUM_INSTRS} --num-instrs ${num_instr} ${verif_flag}"
    done
done

echo ""
echo "Done. Data saved to ${DATA_DIR}"
