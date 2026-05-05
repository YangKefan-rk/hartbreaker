# Design Document

## Overview

HartAttack generates concurrent RISC-V test programs that exercise multicore processor designs. Each generated program consists of a bootloader, a randomized test case body, synchronization primitives, and a termination sequence. The sections below describe the memory layout, program structure, and key design decisions.

## Address space

The address space for all generated programs follows the layout below. The text section size varies between test cases and is randomly selected, but the maximum is `1 << 20` bytes (the range of a `jal` instruction).

```
+-------------------+--------------------------------------+
| Address range     | Content                              |
+-------------------+--------------------------------------+
| 0x0000_1000       | Bootloader                           |
|                   | (jumps to test case entry point)     |
+-------------------+--------------------------------------+
| 0x8000_0000       | Test case program                    |
|                   |   - initial basic block              |
|                   |     (memory/register initialization) |
|                   |   - randomized basic blocks          |
|                   |     (the actual test body)           |
|                   |   - final basic block                |
|                   |     (register/memory dump + tohost)  |
| 0x800F_FFFF       | (end of text section, max 1 MiB)     |
+-------------------+--------------------------------------+
| 0x8010_0008       | Core count for final block           |
|                   | (shared counter for synchronization) |
+-------------------+--------------------------------------+
| 0x8010_0020       | Core synchronization region          |
|                   | (one word per core, max 1023 cores)  |
| 0x8010_041F       |                                      |
+-------------------+--------------------------------------+
| 0x8020_0000       | .tohost address                      |
|                   | (write to terminate simulation)      |
+-------------------+--------------------------------------+
```

## Program structure

### Initial basic block

Sets up each core's execution environment:
- Initializes shared memory regions with random values
- Sets up trap vectors (`mtvec`)
- Configures privilege-level related CSRs
- Synchronizes cores before test body begins

### Randomized basic blocks

The core of the test case. Each basic block is a sequence of instructions drawn from the configured instruction classes (see `hartattack_config.toml`). Branches connect basic blocks to form a control-flow graph. Key properties:

- Instructions are selected based on weighted probabilities
- Memory operations target the shared address space to provoke consistency issues
- Branches are bounded to prevent unbounded execution
- Trap handlers are installed to recover from exceptions

### Final basic block

Runs after all cores complete the test body:
- Uses the core synchronization region to ensure all cores have finished
- Dumps register and memory state to known locations
- Writes to `.tohost` to terminate the simulation

## Simulation flow

### Spike (pre-ISA simulation)

The generated ELF is first run on Spike to obtain reference register/memory state. Spike serves as the golden model -- it defines the correct behavior.

### RTL simulation

The same ELF is then run on the target design's Verilator simulator. The simulator produces a commit log of all retired instructions and their effects.

### Comparison

The RTL commit log is parsed and compared against the Spike reference. Any mismatch in final register values or memory state flags a potential bug.

### MCM verification

When `--fuzz-mcm` is enabled, the memory trace from the RTL simulation is checked against the RISC-V RVWMO memory model. The tool builds a graph of memory operations and their ordering constraints (Preserved Program Order rules, fences, address/data/control dependencies) and uses Z3 or an external solver to determine if the observed execution is valid.

## Design-specific configuration

Each simulator target has a `cfg.json` file in the `simulators/` directory that specifies:
- Simulator binary name and path
- Number of harts (cores)
- CLINT base address
- Memory layout parameters
- Commit log format

The framework adapts generated programs to match each design's CLINT address and termination conventions.
