# HartAttack — Multicore RISC-V Fuzzer

HartAttack is a hardware fuzzing framework that generates concurrent RISC-V programs to find bugs in multicore processor implementations. It targets correctness issues in memory consistency, privilege modes, interrupts, and core synchronization by comparing RTL simulation results against the Spike ISA simulator.

## Architecture

HartAttack follows a generate-and-compare approach:

1. **Program generation** -- Randomly generates concurrent RISC-V programs with proper synchronization, trap handlers, and a final register/memory dump block. Instruction selection is controlled by configurable weights in `hartattack_config.toml`.

2. **ISA simulation** -- Runs the generated program on the Spike ISA simulator to establish expected behavior (the "golden model").

3. **RTL simulation** -- Executes the same program on the target processor's Verilator-based RTL simulator.

4. **Bug detection** -- Compares the RTL output against the Spike reference. Mismatches in register or memory state indicate a processor bug.

5. **MCM verification** (optional) -- For memory consistency bugs, uses Z3 or external tools (Herdtools7, Dat3M) to check whether observed memory orderings are permitted by the RISC-V Weak Memory Ordering (RVWMO) model.

6. **Reduction** (optional) -- Minimizes failing test cases to isolate the root cause.

## Package structure

```
hartattack/
├── main.py                 Entry point
├── hartattack_config.toml  Instruction and exception weight configuration
├── docs/                   Documentation
│
├── proggen/       Test case generation (basic blocks, instruction sequences)
├── riscv/         RISC-V ISA encoding (RV32/64I, M, A, C, F, D, privileged)
├── mcm/           Memory Consistency Model verification (PPO rules, solver)
├── instgen/       Instruction generation from fuzzer state
├── states/        Fuzzer state tracking (CoreState, FuzzerState, HartState, etc.)
├── params/        Design and test parameter configuration
├── staticblocks/  Initial, final, and reset block generation
├── rtlsim/        RTL simulation execution and result parsing
├── preisasim/     Spike simulation execution
├── reduce/        Program reduction for bug minimization
├── genelf/        ELF binary generation from bytecode
├── asm/           Assembly helpers and snippets
├── runparams/     Runtime parameter globals
└── toleratebugs/  Known bug handling
```

## Usage

Ensure the environment is sourced first:

```bash
source ./scripts/all.sh
```

Then run from the repository root:

```bash
python3 hartattack/main.py <design_name> [OPTIONS]
```

### Modes of operation

| Flag | Description |
|------|-------------|
| *(no flag)* | Continuous fuzzing campaign (default) |
| `--gensingle SEED` | Generate a single ELF for a given seed |
| `--fuzzsingle SEED` | Fuzz a single seed (generate + simulate + check) |
| `--manyelfs N` | Generate N test ELFs without simulating |
| `--reduce SEED` | Minimize a failing test case (experimental) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--num-cores N` | 1 | Parallel fuzzing threads |
| `--memsize BYTES` | auto | Memory size override |
| `--num-bbs N` | auto | Maximum number of basic blocks per test |
| `--seed-offset N` | 0 | Starting seed offset |
| `--authorize-privileges` | true | Allow privileged instructions |
| `--fuzz-mcm` | false | Fuzz memory consistency model |
| `--fuzz-interrupts` | false | Enable interrupt fuzzing |
| `--verify-memory-trace {dat}` | none | Use external MCM solver (Herdtools7 or Dat3M) |
| `--keep-tmpfiles` | false | Retain generated files after execution |
| `--debug-rtl` | false | Generate ELF with Spike device addresses |
| `--no-final-check` | false | Skip register verification after execution |
| `--skip-no-interrupts` | false | Skip test cases that produce no interrupts |
| `--jit-scenario` | false | Enable JIT scenario |

### Examples

```bash
# Continuous fuzzing on dualrocket with 8 parallel cores
python3 hartattack/main.py dualrocket --num-cores 8

# Generate a single ELF for seed 42
python3 hartattack/main.py boom --gensingle 42

# Fuzz memory consistency model with dartagna verification
python3 hartattack/main.py dualboomv3 --fuzz-mcm --verify-memory-trace dat

# Fuzz with interrupts enabled
python3 hartattack/main.py tripplerocket --fuzz-interrupts --num-cores 4
```

## Configuration

The fuzzer's instruction mix is controlled by [hartattack_config.toml](hartattack_config.toml):

- **`[instruction_weights]`** -- Probability weights for each instruction class (ALU, memory, branch, fence, FPU, exceptions, interrupts, etc.). Setting a weight to 0 disables that class.
- **`[exception_weights]`** -- Probability weights for different exception types (misaligned access, illegal instruction, breakpoint, ecall, etc.).

## Dependencies

Key Python dependencies (see `requirements.txt`):

- `numpy`, `matplotlib` -- Data processing and visualization
- `z3-solver` -- SMT constraint solving for MCM verification
- `pyelftools` -- ELF file manipulation
- `psutil`, `sysv_ipc` -- System utilities
- `docker` -- Container management
- `tqdm` -- Progress bars

External tools (installed via `scripts/local_install.sh` or Docker):

- RISC-V GNU Toolchain
- Spike ISA simulator
- Verilator
- Bluespec compiler (BSC)
- Herdtools7 (optional, for MCM verification)
- Dat3M (optional, for MCM verification)

## Further reading

- [docs/design.md](docs/design.md) -- Address space layout and memory map
- [docs/quickstart.md](docs/quickstart.md) -- Adding new designs to the fuzzer
