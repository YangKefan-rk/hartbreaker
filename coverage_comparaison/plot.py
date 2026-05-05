import os
import json
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
import shutil
import sys
import random
import argparse
TOTAL_N_BITS = 15872

NAMES = {
    "hartattack/INTERRUPT": "HartBreaker no verification",
    "hartattack/MCM": "HartBreaker with verification",
    "riscvdv-out": "RISCV-DV"
}

COLORS = ['#0D75FF', '#FFAB00', '#9E52F2']

# Set font sizes
SMALL_SIZE = 8
MEDIUM_SIZE = 9
BIGGER_SIZE = 10

plt.rc('font', size=SMALL_SIZE)          # default text sizes
plt.rc('axes', titlesize=BIGGER_SIZE)     # axes title
plt.rc('axes', labelsize=MEDIUM_SIZE)     # x and y labels
plt.rc('xtick', labelsize=SMALL_SIZE)     # x tick labels
plt.rc('ytick', labelsize=SMALL_SIZE)     # y tick labels
plt.rc('legend', fontsize=SMALL_SIZE)     # legend
plt.rc('figure', titlesize=BIGGER_SIZE)   # figure title

def bits_covered(content):
    """Return a set of indices of bits that are '1'."""
    return {i for i, c in enumerate(content) if c == "1"}


def load_tool_runtimes(timing_file: str, riscvdv_metadata_file: str,
                       num_cores: int) -> dict:
    """Compute tool runtimes in core-hours from timing log and metadata.

    For HartBreaker: generation time (from timing log) + coverage sim time (from timing log),
    scaled by num_cores.
    For RISCV-DV: generation time (from metadata) + coverage sim time (from timing log),
    where generation core-hours = generation_time_s * generation_cores / 3600.
    """
    runtimes = {}

    # Read timing log (JSONL)
    timing = {}
    if os.path.exists(timing_file):
        with open(timing_file, "r") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    timing[entry["step"]] = entry["elapsed_s"]

    # HartBreaker: generation + coverage collection, all on num_cores
    gen_time_s = timing.get("generate_hartbreaker_corpus", 0)
    cov_hartbreaker_s = timing.get("coverage_hartbreaker", 0)

    # noverif corpus is the INTERRUPT scenario, withverif is MCM
    # Both share the same generation + coverage time, split proportionally
    # For simplicity, use total time for both (they ran sequentially)
    total_hartbreaker_core_h = (gen_time_s + cov_hartbreaker_s) * num_cores / 3600
    # Split: INTERRUPT is ~950s, MCM is ~20000s of the generation
    # Use equal split since we can't distinguish from timing log
    runtimes["hartattack/INTERRUPT"] = total_hartbreaker_core_h / 2
    runtimes["hartattack/MCM"] = total_hartbreaker_core_h / 2

    # RISCV-DV: generation from metadata + coverage collection time
    cov_riscvdv_s = timing.get("coverage_riscvdv", 0)
    riscvdv_gen_core_h = 0
    if os.path.exists(riscvdv_metadata_file):
        with open(riscvdv_metadata_file, "r") as f:
            meta = json.load(f)
        riscvdv_gen_core_h = meta["generation_time_s"] * meta.get("generation_cores", 1) / 3600
    runtimes["riscvdv-out"] = riscvdv_gen_core_h + (cov_riscvdv_s * num_cores / 3600)

    return runtimes


def plot_evolution(cov_data_path: str, out_path: str = "./script_out",
                   tool_runtimes: dict = None):
    final_coverage = {}
    plt.figure(figsize=(3.5, 2))

    # Get top-level directories
    dirs = ["hartattack/INTERRUPT",  "hartattack/MCM",  "riscvdv-out"]

    max_runtime = 0

    for idx, dir_name in enumerate(dirs):
        print(f"in dir {dir_name}")
        dir_path = os.path.join(cov_data_path, dir_name)

        # Find all output files
        out_files = []
        for subdir_path, _, files in os.walk(dir_path):
            for f in files:
                out_files.append(os.path.join(subdir_path, f))

        # Sort files by filename (e.g., timestamp order)
        out_files.sort()

        cumulative_covered = set()
        covered_counts = []
        file_indices = []

        for i, file_path in enumerate(out_files, 1):
            try:
                with open(file_path, "r") as f:
                    content = f.read().strip()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue

            new_covered = bits_covered(content)
            cumulative_covered |= new_covered  # union: add new bits
            covered_counts.append(len(cumulative_covered))
            file_indices.append(i)

        final_coverage[dir_name] = cumulative_covered
        print(f"Directory {dir_name}: {len(cumulative_covered)} total bits covered.")

        if covered_counts:
            # Convert file indices to core hours (linear interpolation)
            # Each file represents an equal fraction of the tool's runtime
            tool_runtime = tool_runtimes.get(dir_name, 0) if tool_runtimes else 0
            if tool_runtime <= 0:
                print(f"Warning: no runtime for {dir_name}, skipping plot")
                continue
            total_files = len(file_indices)
            hours = [(idx / total_files) * tool_runtime for idx in file_indices]
            if dir_name.startswith("hartattack"):
                max_runtime = max(max_runtime, tool_runtime)

            # Convert to percentage
            covered_percentages = [(count / TOTAL_N_BITS) * 100 for count in covered_counts]
            hours = [0] + hours
            covered_percentages = [0] + covered_percentages
            color = COLORS[idx] if idx < len(COLORS) else None
            plt.plot(hours, covered_percentages, label=NAMES[dir_name], color=color)

    plt.xlabel("Fuzzing Time (core hours)")
    plt.ylabel("Coverage (%)")
    if max_runtime > 0:
        plt.xlim(left=0, right=max_runtime)
    plt.legend(loc='lower center', bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{out_path}/cov_evolution.pdf", dpi=300, format="pdf")

    assert len(final_coverage) == 3
    return final_coverage


def plot_final_cov_overlap(final_coverage: dict[str, set[int]], out_path: str = "./script_out"):
    assert len(final_coverage) == 3
    riscv_dv_cov = final_coverage["riscvdv-out"]
    hartattack_cov = final_coverage["hartattack/INTERRUPT"] | final_coverage["hartattack/MCM"]

    indexes = np.arange(TOTAL_N_BITS)
    in_riscvdv = np.array([i in riscv_dv_cov for i in indexes])
    in_hartattack = np.array([i in hartattack_cov for i in indexes])

    # Encode categories:
    # 0 = empty, 1 = only hartattack, 2 = overlap, 3 = only riscvdv
    categories = np.where(
        in_riscvdv & in_hartattack,
        2,  # overlap
        np.where(
            in_riscvdv,
            3,  # only riscvdv
            np.where(in_hartattack, 1, 0),
        ),
    )  # only hartattack or empty

    # Define colors (muted for overlap/empty, bright for unique)
    colors = np.array(
        ['#0D75FF', '#FFAB00', '#F20000', '#9E52F2']
    )

    # Define bar heights — taller for the "only" categories
    heights = np.choose(categories, [1.0, 2.0, 1.0, 2.0])

    cmap = [colors[c] for c in categories]

    # Plot
    plt.figure(figsize=(10, 2))
    plt.bar(indexes, heights, color=cmap, width=1.0)
    plt.yticks([])
    plt.xlabel("Index")
    plt.title("Set membership: only riscvdv / only hartattack / overlap / empty")

    # Legend matching the color scheme
    legend = [
        mpatches.Patch(color="#0D75FF", label="empty"),
        mpatches.Patch(color="#FFAB00", label="only riscvdv"),
        mpatches.Patch(color="#F20000", label="only hartattack"),
        mpatches.Patch(color="#9E52F2", label="overlap"),
    ]
    plt.legend(handles=legend, loc="upper right", frameon=False)

    plt.tight_layout()
    plt.savefig(f"{out_path}/final_cov_overlap.pdf", dpi=300, format="pdf")


def plot_final_cov_split(final_coverage: dict[str, set[int]], out_path: str = "./script_out"):
    assert len(final_coverage) == 3
    riscv_dv_cov = final_coverage["riscvdv-out"]
    hartattack_cov = final_coverage["hartattack/INTERRUPT"] | final_coverage["hartattack/MCM"]

    # Compute unique bits
    riscvdv_only_indices = np.array(list(riscv_dv_cov - hartattack_cov), dtype=int)
    hartattack_only_indices = np.array(list(hartattack_cov - riscv_dv_cov), dtype=int)

    # Extract wire names
    with open("cov_names", "r") as f:
        lines = f.readlines()

    out = []
    out.append("Signals only in riscv-dv:")
    for idx in riscvdv_only_indices:
        out.append(lines[idx].rstrip())  # remove newline

    out.append("\nSignals only in hartattack:")
    for idx in hartattack_only_indices:
        out.append(lines[idx].rstrip())

    with open(f"{out_path}/wires.txt", "w") as f:
        for l in out:
            f.write(l + "\n")

    # Plot as a bar plot
    plt.figure(figsize=(16, 2))

    # Top row = only riscv-dv
    plt.bar(
        riscvdv_only_indices, 2.0, color="#0080ff", width=1.0, label="Only in Riscv-DV"
    )

    # Bottom row = only hartattack
    plt.bar(
        hartattack_only_indices,
        1.0,
        color="#ff0000",
        width=1.0,
        label="Only in HartAttack",
    )

    plt.yticks([1, 2], ["Only in HartAttack", "Only in Riscv-DV"])
    plt.xlabel("Bit index")
    plt.title("Sparse coverage diff (only bits unique to A or B)")
    plt.legend(loc="upper right", frameon=False)
    plt.tight_layout()
    plt.savefig(f"{out_path}/final_cov_split.pdf", dpi=300, format="pdf")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Plot coverage comparison results")
    parser.add_argument("cov_data", type=str, nargs="?", default="./cov_data",
                        help="Path to coverage data directory")
    parser.add_argument("--output", type=str, default="./script_out",
                        help="Output directory for plots")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing output directory without prompting")
    parser.add_argument("--timing", type=str, default=None,
                        help="Path to timing.jsonl from figure_14.sh")
    parser.add_argument("--riscvdv-metadata", type=str, default=None,
                        help="Path to RISCV-DV metadata.json")
    parser.add_argument("--num-cores", type=int, default=200,
                        help="Number of cores used for coverage collection")
    args = parser.parse_args()

    cov_data_path = args.cov_data
    out_path = args.output

    if not os.path.exists(cov_data_path):
        print(f"cov_data directory not found: {cov_data_path}")
        return

    if os.path.exists(out_path):
        if args.force:
            shutil.rmtree(out_path)
        else:
            response = (
                input(
                    f"{out_path} directory exists. Do you want to delete it (y) or abort (n)? "
                )
                .strip()
                .lower()
            )
            if response == "y":
                shutil.rmtree(out_path)
            else:
                print("Aborting.")
                sys.exit(1)
    os.mkdir(out_path)

    # Compute tool runtimes from timing data
    tool_runtimes = load_tool_runtimes(
        args.timing or "",
        args.riscvdv_metadata or "",
        args.num_cores,
    )
    print(f"Computed runtimes (core-hours): {tool_runtimes}")

    # plot comparaison between the different corpus of testcases
    final_coverage = plot_evolution(cov_data_path, out_path, tool_runtimes)

    # plot the comparaison between the final bits vectors
    # plot_final_cov_overlap(final_coverage)
    # plot_final_cov_split(final_coverage, out_path)


if __name__ == "__main__":
    main()
