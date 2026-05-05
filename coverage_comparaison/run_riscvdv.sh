#!/bin/bash
# run_parallel_riscv_dv.sh
# Launch multiple riscv-dv test generations in parallel using plain Bash

source env.sh

start_time=$(date +%s)

# List of all test names available for the multicore target
tests=(
    riscv_arithmetic_basic_test
    riscv_rand_instr_test
    riscv_jump_stress_test
    riscv_loop_test
    riscv_rand_jump_test
    riscv_mmu_stress_test
    riscv_no_fence_test
    riscv_illegal_instr_test
    riscv_ebreak_test
    riscv_ebreak_debug_mode_test
    riscv_full_interrupt_test
    riscv_unaligned_load_store_test
    riscv_non_compressed_instr_test
    riscv_hint_instr_test
    riscv_load_store_shared_mem_test
    riscv_amo_test
    riscv_single_hart_test
)

# RISCV_DV_DIR is set inside the covcollect Docker image; this script must
# run there.
: "${RISCV_DV_DIR:?must be set; run this script inside the covcollect Docker container}"
DV_PATCH="$(pwd)/dv.patch"

# Apply the local patch if it isn't already applied.
if ! git -C "$RISCV_DV_DIR" apply --reverse --check "$DV_PATCH" 2>/dev/null; then
  git -C "$RISCV_DV_DIR" apply "$DV_PATCH"
fi

cd "$RISCV_DV_DIR"
source env.sh

# Base output directory; override with RISCVDV_OUT_BASE.
out_base="${RISCVDV_OUT_BASE:-./riscvdv-out}"
mkdir -p "$out_base"

# Function to run one test
run_test() {
  local testname="$1"
  local out_dir="$out_base/$testname"
  mkdir -p "$out_dir"

  echo "[INFO] Launching $testname..."
  python3 run.py \
    --target multi_harts \
    --test "$testname" \
    --simulator questa \
    --o "$out_dir" \
    --iterations 5000 \
    --batch_size 100 \
    --gen_timeout 3600 \
    > "$out_dir/run.log" 2>&1

  echo "[DONE] $testname finished"
}

# Launch tests in background with limited concurrency
for testname in "${tests[@]}"; do
  run_test "$testname" &
done

# Wait for remaining jobs
wait

end_time=$(date +%s)
runtime=$((end_time - start_time))

echo "✅ All tests generation completed in ${runtime}s."
