#!/usr/bin/env python3
"""
Plot box plot showing simulation time distribution for all designs and program sizes.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import sys
from typing import Dict, List, Tuple
from matplotlib import patches as mpatches

colors_c = [ "#0D75FF", "#328e13", "#9E52F2", "#FFAB00", "#F20000"]
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
    "trippleboomv3": "Boom",
    "xiangshan": "XiangShan",
    "toooba-3core": "Toooba",
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


def get_simulation_times(file_path: Path) -> List[float]:
    """Get list of simulation times in minutes from a JSONL file."""
    data_points = load_jsonl_data(file_path)
    return [simulation / 60 for _, _, simulation, _ in data_points]


def collect_simulation_times_for_design(
    base_dir: Path, design: str, target_size: int
) -> List[float]:
    """
    Collect simulation times for a single design at target size.

    Args:
        base_dir: Base directory containing the data
        design: Design name
        target_size: Target instruction size

    Returns:
        List of simulation times for the target size
    """
    design_dir = base_dir / design
    if not design_dir.exists():
        print(f"Warning: Design directory {design_dir} does not exist, skipping")
        return []

    verif_file = design_dir / str(target_size) / f"{design}_{target_size}_verif.jsonl"
    noverif_file = design_dir / str(target_size) / f"{design}_{target_size}_noverif.jsonl"

    file_to_use = noverif_file if design == "xiangshan" else verif_file

    if file_to_use.exists():
        return get_simulation_times(file_to_use)
    else:
        return []


def plot_simulation_time_boxplot(base_dir: Path, designs: List[str], sizes: List[int], output_file: str):
    """Create a box plot of simulation times for all designs and sizes, grouped by program size."""
    data = []
    design_order = []

    for size in sizes:
        design_medians = []
        for design in designs:
            sim_times = collect_simulation_times_for_design(base_dir, design, size)
            if sim_times:
                median = np.median(sim_times)
                design_medians.append((design, sim_times, median))
        # Sort by median simulation time
        design_medians.sort(key=lambda x: x[2])
        for design, sim_times, _ in design_medians:
            data.append(sim_times)
            design_order.append(design)

    if not data:
        print("No data found to plot")
        return

    # Group boxes by size
    num_designs = len(designs)
    group_width = num_designs + 0.5  # spacing between groups
    positions = [i * group_width + j for i in range(len(sizes)) for j in range(num_designs)]

    fig, ax = plt.subplots(figsize=(3.5, 1.9))
    bp = ax.boxplot(data, positions=positions, patch_artist=True,
                     widths=0.8, showfliers=False)
    ax.set_ylabel('Simulation Time (min)')
    ax.set_xlabel('Instruction Count (instructions)')

    # Apply styling
    colors = [colors_c[designs.index(d) % len(colors_c)] for d in design_order]
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_linewidth(0)
    for median in bp['medians']:
        median.set_color('black')
        median.set_linewidth(0.5)
    for whisker in bp['whiskers']:
        whisker.set_linewidth(0.5)
    for cap in bp['caps']:
        cap.set_linewidth(0.5)

    # Set major ticks at group centers
    group_centers = [i * group_width + (num_designs - 1) / 2 for i in range(len(sizes))]
    ax.set_xticks(group_centers)
    # ax.set_yscale('log')
    ax.set_xticklabels([f"{int(s/1000)}k" for s in sizes])

    # Add legend
    all_handles = [mpatches.Patch(color=colors_c[i % len(colors_c)]) for i in range(num_designs)]
    ax.legend(handles=all_handles, loc='upper left', bbox_to_anchor=(0.05, 1.4), ncol=3)
    ax.legend(all_handles, [CORES.get(d, d) for d in designs])

    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{output_file}.pdf", dpi=300, bbox_inches='tight')
    plt.show()


def main():
    if len(sys.argv) < 2:
        print("Usage: python plot_throughput_comparison.py <data_directory>")
        print("Example: python plot_throughput_comparison.py /path/to/data")
        sys.exit(1)

    base_dir = Path(sys.argv[1])
    if not base_dir.exists():
        print(f"Error: Directory {base_dir} does not exist")
        sys.exit(1)

    # Automatically discover all design directories
    designs = sorted([d.name for d in base_dir.iterdir() if d.is_dir()])
    designs = [d for d in designs if d == "xiangshan"]  # Only use xiangshan

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
    output_file = "simulation_time_boxplot"
    plot_simulation_time_boxplot(base_dir, designs, sizes, output_file)


if __name__ == "__main__":
    main()
