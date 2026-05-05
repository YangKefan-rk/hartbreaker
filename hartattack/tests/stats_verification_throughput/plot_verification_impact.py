#!/usr/bin/env python3
# Copyright 2026 Flavien Solt, Quentin Bordier ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only
"""
Plot the time breakdown for verification and no-verification runs to identify throughput bottlenecks.
Shows stacked bars for generation, simulation, and verification times.
"""

import json
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path
import sys
from typing import Dict, List, Tuple

colors_c = ["#0D75FF", "#FFAB00", "#F20000", "#9E52F2"]
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

def load_jsonl_throughputs(file_path: Path, size: int) -> List[float]:
    """Load throughputs from a JSONL file.

    Calculates throughput as: instruction_count / total_time
    where total_time = generation + simulation + verification
    """
    throughputs = []
    with open(file_path, "r") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                # Calculate total time from components
                generation = data.get("generation", 0) + data.get("iss_sim", 0)
                simulation = data.get("simulation", 0)
                verification = data.get("verification", 0)
                total_time = generation + simulation + verification
                throughput = size / total_time if total_time > 0 else 0
                throughputs.append(throughput)
    return throughputs





def collect_data(
    base_dir: Path, design: str = "tripplerocket"
) -> Tuple[List[int], List[List[float]], List[List[float]]]:
    """
    Collect throughputs for verification and no-verification runs.

    Args:
        base_dir: Base directory containing the data
        design: Design name (default: tripplerocket)

    Returns:
        Tuple of (instruction_sizes, verif_throughputs, noverif_throughputs)
        where throughputs are lists of lists: [size][run_throughputs]
    """
    design_dir = base_dir / design
    if not design_dir.exists():
        print(f"Error: Design directory {design_dir} does not exist")
        sys.exit(1)

    # Get all instruction size directories
    size_dirs = sorted(
        [d for d in design_dir.iterdir() if d.is_dir()], key=lambda x: int(x.name)
    )

    instruction_sizes = []
    verif_throughputs = []
    noverif_throughputs = []

    for size_dir in size_dirs:
        size = int(size_dir.name)
        if size > 8000 or size < 1000:
            continue
        verif_file = size_dir / f"{design}_{size}_verif.jsonl"
        noverif_file = size_dir / f"{design}_{size}_noverif.jsonl"

        # Skip if files don't exist
        if not verif_file.exists() or not noverif_file.exists():
            print(f"Warning: Missing files for size {size}, skipping")
            continue

        verif_runs = load_jsonl_throughputs(verif_file, size)
        noverif_runs = load_jsonl_throughputs(noverif_file, size)

        instruction_sizes.append(size)
        verif_throughputs.append(verif_runs)
        noverif_throughputs.append(noverif_runs)

    return instruction_sizes, verif_throughputs, noverif_throughputs


def plot_verification_throughput(
    instruction_sizes: List[int],
    verif_throughputs: List[List[float]],
    noverif_throughputs: List[List[float]],
    output_file: str = "verification_throughput.pdf",
):
    """
    Create box plots showing throughput distribution with and without verification, overlaid in the same plot.

    Args:
        instruction_sizes: List of instruction counts
        verif_throughputs: List of lists of throughputs with verification (instructions/second)
        noverif_throughputs: List of lists of throughputs without verification (instructions/second)
        output_file: Output file name
    """
    def format_size(x):
        if x >= 1000:
            return f'{x//1000}k'
        else:
            return str(x)

    fig, ax = plt.subplots(figsize=(3.5, 1.9))

    # Prepare data
    noverif_data = [run for run in noverif_throughputs if run]
    verif_data = [run for run in verif_throughputs if run]

    positions = range(len(instruction_sizes))

    if noverif_data:
        # Plot no-verification
        bp1 = ax.boxplot(noverif_data, positions=positions, patch_artist=True,
                         widths=0.3, showfliers=False)
        for patch in bp1['boxes']:
            patch.set_facecolor(colors_c[0])
            patch.set_linewidth(0)
        for median in bp1['medians']:
            median.set_color('black')
            median.set_linewidth(0.5)
        for whisker in bp1['whiskers']:
            whisker.set_linewidth(0.5)
        for cap in bp1['caps']:
            cap.set_linewidth(0.5)

    if verif_data:
        # Plot verification
        bp2 = ax.boxplot(verif_data, positions=positions, patch_artist=True,
                         widths=0.3, showfliers=False)
        for patch in bp2['boxes']:
            patch.set_facecolor(colors_c[1])
            patch.set_linewidth(0)
        for median in bp2['medians']:
            median.set_color('black')
            median.set_linewidth(0.5)
        for whisker in bp2['whiskers']:
            whisker.set_linewidth(0.5)
        for cap in bp2['caps']:
            cap.set_linewidth(0.5)

    # Labels
    ax.set_xlabel("Program Size (instructions)")
    ax.set_ylabel("Throughput (instr/s)")
    ax.set_ylim(bottom=0)
    ax.set_xticks(positions)
    ax.set_xticklabels([format_size(size) for size in instruction_sizes])

    # Format y-axis for large numbers
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f'{x/1000:.1f}k' if x >= 1000 else f'{x:.1f}'))

    ax.grid(axis="y", alpha=0.3)

    # Legend
    legend_elements = [
        mpatches.Rectangle((0,0),1,1, facecolor=colors_c[0], label='Disabled'),
        mpatches.Rectangle((0,0),1,1, facecolor=colors_c[1], label='Enabled')
    ]
    ax.legend(handles=legend_elements, title="Verification", loc='upper left')

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"Plot saved to {output_file}")

    # Print throughput statistics
    print("\nVerification Throughput Statistics:")
    print(
        f"{'Instr Count':<15} {'No Verif Mean (instr/s)':<25} {'Verif Mean (instr/s)':<25} {'Ratio':<10}"
    )
    print("-" * 75)
    for size, noverif, verif in zip(instruction_sizes, noverif_throughputs, verif_throughputs):
        noverif_mean = np.mean(noverif) if noverif else 0
        verif_mean = np.mean(verif) if verif else 0
        ratio = verif_mean / noverif_mean if noverif_mean > 0 else 0
        print(f"{size:<15} {noverif_mean:<25.2f} {verif_mean:<25.2f} {ratio:<10.2f}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python plot_verification_impact.py <data_directory>")
        print("Example: python plot_verification_impact.py /path/to/data")
        sys.exit(1)

    base_dir = Path(sys.argv[1])
    if not base_dir.exists():
        print(f"Error: Directory {base_dir} does not exist")
        sys.exit(1)

    # Collect data for tripplerocket
    instruction_sizes, verif_throughputs, noverif_throughputs = collect_data(
        base_dir, "tripplerocket"
    )

    if not instruction_sizes:
        print("Error: No data found")
        sys.exit(1)

    # Create the throughput plot
    output_file_throughput = "verification_throughput_dualrocket.pdf"
    plot_verification_throughput(
        instruction_sizes, verif_throughputs, noverif_throughputs, output_file_throughput
    )


if __name__ == "__main__":
    main()
