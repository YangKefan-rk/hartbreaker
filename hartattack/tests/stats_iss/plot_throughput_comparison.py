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

def load_jsonl_throughputs(file_path: Path, size: int) -> List[float]:
    """Load throughputs from a JSONL file.

    Calculates throughput as: instruction_count / total_time
    where total_time = generation + simulation + verification
    """
    gen_times = []
    iss_times = []
    verif_times = []
    sim_time = []
    with open(file_path, "r") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                # Calculate total time from components
                gen_times.append(data.get("generation", 0))
                iss_times.append(data.get("iss_sim", 0))
                verif_times.append(data.get("verification", 0))
                sim_time.append(data.get("simulation", 0))
    return gen_times, iss_times, verif_times, sim_time

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

    data: dict[int, tuple[dict[str, int], dict[str, int]]] = {}

    for size_dir in size_dirs:
        size = int(size_dir.name)
        if size > 8000 or size < 1000:
            continue
        verif_file = size_dir / f"{design}_{size}_verif.jsonl"
        noverif_file = size_dir / f"{design}_{size}_noverif.jsonl"

        # Skip if files don't exist or are empty
        if not verif_file.exists() or not noverif_file.exists() \
                or verif_file.stat().st_size == 0 or noverif_file.stat().st_size == 0:
            print(f"Warning: Missing or empty files for size {size}, skipping")
            continue

        total_time_verif = 0
        total_gen_verif = 0
        total_iss_verif = 0
        total_verif_verif = 0
        total_sim_verif = 0
        gen_times_v, iss_times_v, verif_times_v, sim_times_v = load_jsonl_throughputs(verif_file, size)
        for gen, iss, verif, sim in zip(gen_times_v, iss_times_v, verif_times_v, sim_times_v):
            total_time_verif += gen + iss + verif + sim
            total_gen_verif += gen
            total_iss_verif += iss
            total_verif_verif += verif
            total_sim_verif += sim

        verif_data = {
            "iss": total_iss_verif / total_time_verif,
            "gen": total_gen_verif / total_time_verif,
            "verif": total_verif_verif / total_time_verif,
            "sim": total_sim_verif / total_time_verif
        }

        total_time_noverif = 0
        total_gen_noverif = 0
        total_iss_noverif = 0
        total_sim_noverif = 0
        gen_times, iss_times, verif_times, sim_times = load_jsonl_throughputs(noverif_file, size)
        for gen, iss, verif, sim in zip(gen_times, iss_times, verif_times, sim_times):
            # assert verif == 0, f"verif should be 0: {verif}"
            total_time_noverif += gen + iss + sim
            total_gen_noverif += gen
            total_iss_noverif += iss
            total_sim_noverif += sim

        noverif_data = {
            "iss": total_iss_noverif / total_time_noverif,
            "gen": total_gen_noverif / total_time_noverif,
            "verif": 0,
            "sim": total_sim_noverif / total_time_noverif
        }

        data[size] = (verif_data, noverif_data)

    return data


def plot_verification_throughput(
    data,
    output_file: str = "step_split.pdf",
):
    sizes = list(data.keys())

    # Extract stacked values
    gen_verif = [data[s][0]["gen"] for s in sizes]
    iss_verif = [data[s][0]["iss"] for s in sizes]
    verif_verif = [data[s][0]["verif"] for s in sizes]
    sim_verif = [data[s][0]["sim"] for s in sizes]

    gen_noverif = [data[s][1]["gen"] for s in sizes]
    iss_noverif = [data[s][1]["iss"] for s in sizes]
    verif_noverif = [data[s][1]["verif"] for s in sizes]  # always 0
    sim_noverif = [data[s][1]["sim"] for s in sizes]  # always 0

    # X positions: two bars per size
    x = np.arange(len(sizes))
    width = 0.35

    # Shared colors for both bars
    color_gen = colors_c[0]
    color_iss = colors_c[1]
    color_verif = colors_c[2]
    color_sim = colors_c[3]

    fig, ax = plt.subplots(figsize=(3.5, 2.5))

    # --- Without verification ---
    ax.bar(x - width/2, gen_noverif, width, color=color_gen)
    ax.bar(x - width/2, iss_noverif, width, bottom=gen_noverif, color=color_iss)
    ax.bar(
        x - width/2,
        verif_noverif,
        width,
        bottom=np.array(gen_noverif) + np.array(iss_noverif),
        color=color_verif,
    )
    ax.bar(
        x - width/2,
        sim_noverif,
        width,
        bottom=np.array(gen_noverif) + np.array(iss_noverif) + np.array(verif_noverif),
        color=color_sim,
    )

    # --- With verification ---
    ax.bar(x + width/2, gen_verif, width, color=color_gen)
    ax.bar(x + width/2, iss_verif, width, bottom=gen_verif, color=color_iss)
    ax.bar(
        x + width/2,
        verif_verif,
        width,
        bottom=np.array(gen_verif) + np.array(iss_verif),
        color=color_verif,
    )
    ax.bar(
        x + width/2,
        sim_verif,
        width,
        bottom=np.array(gen_verif) + np.array(iss_verif) + np.array(verif_verif),
        color=color_sim,
    )

    # Labels and formatting
    ax.set_ylabel("Fraction of total time")

    # First level: verif / no-verif labels under each bar
    bar_positions = []
    bar_labels = []
    for i in range(len(sizes)):
        bar_positions.append(x[i] - width/2)
        bar_labels.append("no-verif")
        bar_positions.append(x[i] + width/2)
        bar_labels.append("verif")
    ax.set_xticks(bar_positions)
    ax.set_xticklabels(bar_labels, fontsize=6, rotation=45, ha="center")

    # Second level: size labels below, centered on each group
    for i, size in enumerate(sizes):
        ax.text(
            x[i], -0.43, str(size),
            ha="center", va="top",
            fontsize=SMALL_SIZE, transform=ax.get_xaxis_transform()
        )

    # Add "Program Size (instruction)" label with extra padding
    ax.set_xlabel("Program size (instruction)", labelpad=15)


    # Legend above the plot
    legend_patches = [
        mpatches.Patch(color=color_gen, label="Generation"),
        mpatches.Patch(color=color_iss, label="ISS"),
        mpatches.Patch(color=color_verif, label="MCM Verification"),
        mpatches.Patch(color=color_sim, label="RTL Simulation"),
    ]
    ax.legend(
        handles=legend_patches, loc="lower center",
        bbox_to_anchor=(0.5, 1.02), ncol=4, fontsize=6,
        frameon=False, columnspacing=1, handletextpad=0.5, handlelength=1.4
    )

    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")





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
    data = collect_data(
        base_dir, "tripplerocket"
    )

    # Create the throughput plot
    plot_verification_throughput(data)


if __name__ == "__main__":
    main()
