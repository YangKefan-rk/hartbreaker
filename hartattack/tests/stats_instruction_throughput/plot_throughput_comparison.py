#!/usr/bin/env python3
"""
Plot median throughput (instructions/second) for different designs at all instruction sizes.
Creates stacked bar plots showing with and without verification time for each design.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import sys
from typing import Dict, List, Tuple

colors_c = [ "#328e13", "#9E52F2","#0D75FF", "#FFAB00", "#F20000"]
# Set font sizes
SMALL_SIZE = 8
MEDIUM_SIZE = 9
BIGGER_SIZE = 10

plt.rc("font", size=SMALL_SIZE)  # default text sizes
plt.rc("axes", titlesize=BIGGER_SIZE)  # axes title
plt.rc("axes", labelsize=MEDIUM_SIZE)  # x and y labels
plt.rc("xtick", labelsize=SMALL_SIZE)  # x tick labels
plt.rc("ytick", labelsize=SMALL_SIZE)  # y tick labels
plt.rc("legend", fontsize=SMALL_SIZE)  # legend
plt.rc("figure", titlesize=BIGGER_SIZE)  # figure title

CORES = {
    "naxriscv": "NaxRiscv",
    "tripplerocket": "Rocket",
    "dualrocket": "Rocket",
    "trippleboomv3": "Boom",
    "dualboomv3": "Boom",
    "xiangshan": "XiangShan",
    "toooba-3core": "Toooba",
    "toooba": "Toooba",
}


def load_jsonl_data(file_path: Path) -> List[Tuple[int, float, float, float]]:
    """Load instruction count and time components from a JSONL file.

    Returns list of (instruction_count, generation, simulation, verification) tuples.
    """
    data_points = []
    with open(file_path, "r") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                generation = data.get("generation", 0)
                simulation = data.get("simulation", 0)
                verification = data.get("verification", 0)
                instr_count = data.get("instructions count", 0)
                data_points.append((instr_count, generation, simulation, verification))
    return data_points


def compute_average_throughput(file_path: Path) -> Tuple[float, float]:
    """Compute the median throughput with and without verification time from a JSONL file."""
    data_points = load_jsonl_data(file_path)
    if not data_points:
        return 0.0, 0.0

    with_throughputs = []
    without_throughputs = []
    for instr_count, gen, sim, verif in data_points:
        total_with = gen + sim + verif
        total_without = gen + sim
        with_throughputs.append(instr_count / total_with if total_with > 0 else 0)
        without_throughputs.append(instr_count / total_without if total_without > 0 else 0)
    return float(np.mean(with_throughputs)), float(np.mean(without_throughputs))


def collect_data_for_design(
    base_dir: Path, design: str, target_size: int
) -> Tuple[float, float]:
    """
    Collect median throughput with and without verification time for a single design at target size.

    Args:
        base_dir: Base directory containing the data
        design: Design name
        target_size: Target instruction size

    Returns:
        Tuple of (with_verif_throughput, without_verif_throughput) for the target size
    """
    design_dir = base_dir / design
    if not design_dir.exists():
        print(f"Warning: Design directory {design_dir} does not exist, skipping")
        return 0.0, 0.0

    verif_file = design_dir / str(target_size) / f"{design}_{target_size}_verif.jsonl"
    noverif_file = design_dir / str(target_size) / f"{design}_{target_size}_noverif.jsonl"

    file_to_use = noverif_file if design == "xiangshan" else verif_file

    with_verif_throughput, without_verif_throughput = 0.0, 0.0

    if file_to_use.exists():
        with_verif_throughput, without_verif_throughput = compute_average_throughput(file_to_use)

    return with_verif_throughput, without_verif_throughput


def plot_all_designs(
    base_dir: Path, designs: List[str], sizes: List[int], output_file: str = "throughput_comparison.pdf"
):
    """
    Create a stacked bar plot showing median throughput for all designs at all instruction sizes.
    X-axis: instruction sizes, bars: stacked with and without verification time for each design.

    Args:
        base_dir: Base directory containing the data
        designs: List of design names to plot
        sizes: List of instruction sizes to plot
        output_file: Output file name
    """
    # Collect data for all designs and sizes
    data = {}
    for size in sizes:
        data[size] = {}
        for design in designs:
            with_verif, without_verif = collect_data_for_design(base_dir, design, size)
            print(with_verif)
            print(without_verif)
            if with_verif > 0 or without_verif > 0:  # Include if any data
                data[size][design] = {"with": with_verif, "without": without_verif}

    if not data:
        print("Error: No data found for any design")
        sys.exit(1)

    # Create plot
    fig, ax = plt.subplots(figsize=(3.5, 2.2))

    x = np.arange(len(sizes))
    width = 0.8 / len(designs)

    # Plot for each size and design
    for i, design in enumerate(designs):
        design_color = colors_c[i % len(colors_c)]
        for j, size in enumerate(sizes):
            if design in data[size]:
                with_val = data[size][design]["with"]
                without_val = data[size][design]["without"]
                ax.bar(x[j] + i * width, with_val, width, color=design_color, alpha=0.9)
                # ax.bar(x[j] + i * width, without_val - with_val, width, bottom=with_val, color=design_color, alpha=0.7)

    ax.set_ylabel("Throughput (instr/s)")
    ax.set_xlabel("Program Size (instruction)")
    ax.set_xticks(x + (len(designs) - 1) * width / 2)
    ax.set_xticklabels([f"{int(size/1000)}k" for size in sizes])

    # Combined legend
    from matplotlib.patches import Patch
    design_patches = [
        Patch(facecolor=colors_c[i % len(colors_c)], label=CORES.get(design, design))
        for i, design in enumerate(designs)
    ]
    # time_patches = [
    #     Patch(facecolor='white', edgecolor='black', alpha=0.9, hatch="///////", label="Verification"),
    #     Patch(facecolor='white', edgecolor='black', alpha=0.7, label="No verification"),
    # ]
    # all_handles = design_patches + time_patches
    all_handles = design_patches
    ax.legend(handles=all_handles, loc='upper left', bbox_to_anchor=(-0.05, 1.4), ncol=3)

    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{output_file}.pdf", format='pdf', bbox_inches="tight")
    plt.savefig(f"{output_file}.svg", format='svg', bbox_inches="tight")
    print(f"Plot saved to {output_file}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python plot_throughput_comparison.py <data_directory>")
        print("Example: python plot_throughput_comparison.py /path/to/data")
        sys.exit(1)

    base_dir = Path(sys.argv[1])
    if not base_dir.exists():
        print(f"Error: Directory {base_dir} does not exist")
        sys.exit(1)

    # Use the expected designs in display order
    expected = ["naxriscv", "tripplerocket", "trippleboomv3", "xiangshan", "toooba-3core"]
    available = {d.name for d in base_dir.iterdir() if d.is_dir()}
    designs = [d for d in expected if d in available]

    if not designs:
        print(f"Error: No design directories found in {base_dir}")
        sys.exit(1)

    # Discover all instruction sizes
    sizes = set()
    for design in designs:
        design_dir = base_dir / design
        if design_dir.exists():
            for sub in design_dir.iterdir():
                if sub.is_dir() and sub.name.isdigit():
                    sizes.add(int(sub.name))
    sizes = sorted(list(sizes))

    if not sizes:
        print(f"Error: No size directories found in {base_dir}")
        sys.exit(1)

    print(f"Found designs: {', '.join(designs)}")
    print(f"Found sizes: {', '.join(map(str, sizes))}")

    # Create the plot
    output_file = "throughput_comparison_all_2cores"
    plot_all_designs(base_dir, designs, sizes, output_file)


if __name__ == "__main__":
    main()
