# RISCV-DV Pre-built Test Corpus

This directory contains pre-built RISCV-DV test binaries used for the coverage
comparison experiment (Figure 14).

## Generation Details

- **Generation time**: 65,314s on 17 cores (~18.1 hours)
- **Test types**: 17 (see list below)
- **Iterations per test**: 5,000
- **Total tests**: ~85,000
- **Simulator**: Questa (for test generation)

### Test Types

- riscv_arithmetic_basic_test
- riscv_rand_instr_test
- riscv_jump_stress_test
- riscv_loop_test
- riscv_rand_jump_test
- riscv_mmu_stress_test
- riscv_no_fence_test
- riscv_illegal_instr_test
- riscv_ebreak_test
- riscv_ebreak_debug_mode_test
- riscv_full_interrupt_test
- riscv_unaligned_load_store_test
- riscv_non_compressed_instr_test
- riscv_hint_instr_test
- riscv_load_store_shared_mem_test
- riscv_amo_test
- riscv_single_hart_test

## How to Regenerate

1. Apply the patch to riscv-dv:
   ```
   cd coverage_comparaison/tools/riscv-dv
   git apply ../../dv.patch
   ```

2. Source the environment:
   ```
   source coverage_comparaison/env.sh
   ```

3. Run the generation script:
   ```
   cd coverage_comparaison
   ./run_riscvdv.sh
   ```

   This requires Questa to be installed and accessible at `$QUESTA_HOME`.
   Expected runtime: ~18 hours on 17 cores.
