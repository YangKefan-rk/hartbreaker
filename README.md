# HartBreaker -- Artifact Evaluation

## Simulators

Pre-built simulator binaries are included in `simulators/` and are ready to use. Each subdirectory contains the simulator executable and a `cfg.json` describing the design parameters.

### Re-building simulators from source

If you want to rebuild the simulators from source, each build script compiles the design inside a Docker container and extracts the binaries to `simulators/`.

```bash
# Chipyard designs (Rocket, BOOM)
./scripts/build_chipyard.sh

# Toooba designs
./scripts/build_toooba.sh

# XiangShan
./scripts/build_xs.sh
```

NaxRiscv is built via its own Dockerfile:

```bash
./scripts/build_docker.sh naxriscv
```

Building all simulators from source takes several hours and requires significant disk space for the intermediate Docker images.

## Reproducing the experiments

Each figure from the paper has a corresponding script in `artifact_reproduction/`. All scripts run inside the `run` Docker container and produce PDF figures in `figures/`.

### Data collection

Figures 10--13 share a single benchmark dataset. Collect it first with:

```bash
./artifact_reproduction/collect_data.sh
```

This runs 500 programs per design/size/mode combination across all needed designs and instruction sizes (1K, 2K, 4K, 8K). Data is saved to `artifact_reproduction/data/benchmark/` and is skipped if it already exists.

Figures 8, 9, and 14 collect their own data and do not need this step.

### Generating figures

Once the data is collected, generate any figure independently:

```bash
./artifact_reproduction/figure_8.sh   # PPO Rule Usage Probabilities
./artifact_reproduction/figure_9.sh   # Memory Operations Distance Distribution
./artifact_reproduction/figure_10.sh  # Verification Throughput Overhead
./artifact_reproduction/figure_11.sh  # Instruction Throughput Across Designs
./artifact_reproduction/figure_12.sh  # Simulation Time Across Designs
./artifact_reproduction/figure_13.sh  # ISS and Simulation Time Breakdown
./artifact_reproduction/figure_14.sh  # Coverage Comparison (HartBreaker vs RISCV-DV)
```

### Figure 8 -- PPO Rule Usage Probabilities

Generates test programs and collects statistics on PPO rule usage probabilities.

- **Design**: dualrocket
- **Output**: `figures/figure_8.pdf`

### Figure 9 -- Memory Operations Distance Distribution

Generates 10,000 programs and analyzes the distribution of distances between memory operations.

- **Design**: trippleboomv3
- **Cores**: 150
- **Output**: `figures/figure_9.pdf`

### Figure 10 -- Verification Throughput Overhead

Benchmarks the overhead of the verification system on instruction throughput, comparing runs with and without verification across instruction sizes (1K, 2K, 4K, 8K).

- **Design**: tripplerocket
- **Data**: `artifact_reproduction/data/benchmark/`
- **Output**: `figures/figure_10.pdf`

### Figure 11 -- Instruction Throughput Across Designs

Compares instruction throughput across five designs and four instruction sizes.

- **Designs**: naxriscv, tripplerocket, trippleboomv3, xiangshan, toooba-3core
- **Data**: `artifact_reproduction/data/benchmark/`
- **Output**: `figures/figure_11.pdf`

### Figure 12 -- Simulation Time Across Designs

Shows raw simulation time for XiangShan across instruction sizes.

- **Data**: `artifact_reproduction/data/benchmark/`
- **Output**: `figures/figure_12.pdf`

### Figure 13 -- ISS and Simulation Time Breakdown

Shows the time breakdown between the instruction set simulator and hardware simulation.

- **Design**: tripplerocket
- **Data**: `artifact_reproduction/data/benchmark/`
- **Output**: `figures/figure_13.pdf`

### Figure 14 -- Coverage Comparison (HartBreaker vs RISCV-DV)

Compares toggle coverage between HartBreaker (with and without verification) and RISCV-DV on a coverage-instrumented BoomV3 core.

- **Design**: trippleboomv3
- **Output**: `figures/figure_14.pdf`

The experiment has four phases:

1. **Build coverage-instrumented simulator** -- Instruments the BoomV3 RTL with rfuzz toggle coverage using Yosys, then compiles with Verilator. Runs in the `covcollect` Docker container.
2. **Generate HartBreaker corpus** -- Runs HartBreaker in two scenarios (interrupt + MCM) to produce a corpus of test ELFs.
3. **Collect coverage** -- Runs both the HartBreaker corpus and the pre-built RISCV-DV corpus through the instrumented simulator.
4. **Plot** -- Generates the coverage evolution plot.

Pre-built RISCV-DV test binaries are included in `artifact_reproduction/data/riscvdv_corpus/`. See its [README](artifact_reproduction/data/riscvdv_corpus/README.md) for details.

Use `--quick` to test the pipeline with shorter generation timeouts (60s per scenario instead of ~6h):

```bash
./artifact_reproduction/figure_14.sh --quick
```

#### Re-building the coverage-instrumented simulator

The coverage simulator is built automatically by `figure_14.sh` if it does not already exist. To rebuild it manually:

```bash
# Inside the covcollect Docker container:
cd coverage_comparaison
bash make_sources.sh rfuzz   # Instrument RTL with Yosys rfuzz pass
bash build_sim.sh rfuzz      # Compile with Verilator
```

This produces the simulator binary at `coverage_comparaison/out/rfuzz-sim`. Building requires the `covcollect:v1` Docker image (which includes Verilator 5.034 and sv2v).

To force a full rebuild, remove the generated files first:

```bash
rm -f coverage_comparaison/out/rfuzz.v
rm -rf coverage_comparaison/out/verilator_build_rfuzz
rm -f coverage_comparaison/out/rfuzz-sim
```

#### Re-generating the RISCV-DV corpus

The RISCV-DV binaries are shipped as a pre-built artifact. To regenerate them from scratch, you need Questa installed:

```bash
cd coverage_comparaison
source env.sh
./run_riscvdv.sh
```

Generation time: ~18 hours on 17 cores (65,314s). See `artifact_reproduction/data/riscvdv_corpus/README.md` for full details.

### Cleaning data

To remove all generated data and force a full re-run:

```bash
./artifact_reproduction/clean_data.sh
```

## Output

All generated figures are saved to `figures/`. Intermediate benchmark data is stored under `artifact_reproduction/data/` and can be reused across runs.

## Repository layout

| Directory | Description |
|-----------|-------------|
| `hartattack/` | Fuzzing framework (program generation, simulation, verification) |
| `simulators/` | Pre-built simulator binaries and configurations |
| `artifact_reproduction/` | Scripts to reproduce each figure |
| `figures/` | Generated output figures (PDF) |
| `docker/` | Dockerfiles for building simulator and run images |
| `scripts/` | Environment setup and build scripts |
