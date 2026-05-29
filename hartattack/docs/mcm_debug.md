# MCM Debugging Guide

## Overview

The Memory Consistency Model (MCM) fuzzing mode (`--fuzz-mcm`) generates programs designed to expose weak memory ordering violations in multicore designs. Debugging MCM-related bugs requires understanding how the solver works and how to interpret its output.

## Enabling MCM fuzzing

```bash
python3 hartattack/main.py <design> --fuzz-mcm --verify-memory-trace dat
```

The `--verify-memory-trace` flag selects the verification backend:
- `dat` -- Uses Dat3M
- other backends are not yet well sopported

Without `--verify-memory-trace`, the built-in Z3-based solver is used.

## How the MCM solver works

The solver operates in steps, where each step covers the instructions between two MCM reset handlers:

1. **Memory operation extraction** -- Loads, stores, AMOs, and fences are extracted from the Spike and RTL traces.

2. **PPO graph construction** -- Preserved Program Order edges are added based on RVWMO rules:
   - Same-address ordering
   - Fence ordering (based on predecessor/successor sets)
   - Address, data, and control dependencies
   - Atomicity constraints (AMO operations)

3. **RF/CO/FR enumeration** -- The solver enumerates possible reads-from (rf), coherence order (co), and from-reads (fr) edges using Z3 constraints.

4. **Cycle detection** -- If a valid acyclic ordering exists that explains the observed values, the execution is RVWMO-compliant. If no valid ordering exists, it is a bug.

## Key modules

| Module | Purpose |
|--------|---------|
| `mcm/ppo_rules.py` | Computes PPO relationships between memory operations |
| `mcm/solve_steps.py` | Z3-based solver for memory ordering constraints |
| `mcm/memops.py` | Memory operation types (Load, Store, Amo, MemFence) |
| `mcm/mcmstate.py` | MCM state tracking during program generation |
| `mcm/dartagnan.py` | Dat3M integration for external verification |

## Debugging tips

### Inspecting generated programs

Use `--keep-tmpfiles` to retain intermediate files:

```bash
python3 hartattack/main.py <design> --fuzz-mcm --fuzzsingle <seed> --keep-tmpfiles
```

### Common issues

- **Solver timeout** -- Complex programs with many memory operations can cause Z3 to time out. Reduce `--num-bbs` or increase the `FREE_POLLUTED` weight in `hartattack_config.toml` to generate shorter MCM-relevant sequences.

- **False positives from AMOs** -- AMO operations modify data in-place, which can confuse the store-to-data mapping. The solver handles this specially, but edge cases may arise.

- **Non-termination** -- Programs that deadlock (e.g., due to unfulfilled synchronization) will cause the simulation to hang. Use simulation timeouts to catch these.

### Comparing with external solvers

When the built-in Z3 solver reports a violation, cross-check with Herdtools7:

```bash
python3 hartattack/main.py <design> --fuzz-mcm --fuzzsingle <seed> --verify-memory-trace dat
```

If the external solver disagrees, the issue may be in the trace extraction rather than the processor.
