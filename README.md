# HartBreaker -- Artifact Evaluation

## Prerequisites

All build and reproduction steps run inside Docker. The `chipyard`, `covcollect`, `toooba`, `xs`, and `run` images all derive from a shared `base:v1` image, so build that first:

```bash
./scripts/build_docker.sh base
```

Subsequent build scripts (`build_chipyard.sh`, `build_toooba.sh`, `build_xs.sh`) and the experiment scripts assume `base:v1` exists. If you only want Figure 14, you also need the `covcollect:v1` image:

```bash
./scripts/build_docker.sh covcollect
```

The `covcollect` image bakes in pinned clones of [milesan-yosys](https://github.com/milesan-artifacts/milesan-yosys) and [riscv-dv](https://github.com/chipsalliance/riscv-dv) -- you do **not** need to clone or build them on the host.

## Simulators

Simulator binaries are not committed to the repository. Each build script compiles a design inside its Docker container and extracts the binary plus a generated `cfg.json` (describing the design parameters) into `simulators/<design>/`.

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

## Configuration

Two knobs control reproduction cost. Both are environment variables -- export them before launching any reproduction script (or set them in `scripts/env.sh`):

| Variable | Used by | Default | What it controls |
|---|---|---|---|
| `HARTATTACK_CORES` | All build scripts and all reproduction scripts | `15` | Cores for `make -j` during Docker builds and parallel workers during fuzzing. Set this to your machine's core count (e.g. `200` on a cluster node). |
| `HARTATTACK_NUM_PROGRAMS` | `collect_data.sh` (Figs 10-13), `stats_ppo_rules` (Fig 8) | `500` (collect_data) / `10000` (PPO) | Programs generated per design/instruction-size combo. |
| `HARTATTACK_NUM_ELFS` | `figure_9.sh` | `10000` | ELFs analyzed for the memory-distance distribution. |

Example -- run everything on a 64-core box with shorter benchmarks:

```bash
export HARTATTACK_CORES=64
export HARTATTACK_NUM_PROGRAMS=100
./artifact_reproduction/collect_data.sh
./artifact_reproduction/figure_10.sh
```

Per-design caps (e.g. naxriscv/vexiiriscv max 20 cores) still apply on top of `HARTATTACK_CORES`.

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

The pre-built RISCV-DV test binaries are distributed separately as a tarball (~14 GB) on Zenodo, not in this repository. Download `riscvdv-out.tar.gz` from the Zenodo record into `artifact_reproduction/data/riscvdv_corpus/` before running Figure 14. See its [README](artifact_reproduction/data/riscvdv_corpus/README.md) for details.

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
| `simulators/` | Per-design output directory; populated by the build scripts (binary + `cfg.json`) |
| `artifact_reproduction/` | Scripts to reproduce each figure |
| `figures/` | Generated output figures (PDF) |
| `docker/` | Dockerfiles for building simulator and run images |
| `scripts/` | Environment setup and build scripts |
