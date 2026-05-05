#!/usr/bin/env python3


"""
Script to plot PPO rule usage probabilities from JSON statistics file.
Usage: python plot_ppo_rules.py <json_file_path>
"""

import json
import matplotlib.pyplot as plt
import sys
import os
from pathlib import Path

colors = ["#0D75FF", "#FFAB00", "#F20000", "#9E52F2"]
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


def plot_ppo_probabilities(json_file_path, output_path=None):
    """
    Load JSON statistics and create a bar plot of PPO rule probabilities.

    Args:
        json_file_path: Path to the JSON file containing PPO rule statistics
        output_path: Optional path to save the plot. If None, will be saved as PNG next to JSON file
    """
    # Load the JSON data
    with open(json_file_path, "r") as f:
        data = json.load(f)

    # Extract rule names and probabilities
    rules = data["rules"]
    rule_names = list(rules.keys())
    probabilities = [rules[rule]["probability"] for rule in rule_names]
    counts = [rules[rule]["count"] for rule in rule_names]

    total_memops = data["total_memops"]
    total_tests = data["total_tests"]

    # Create the plot
    fig, ax = plt.subplots(figsize=(3.5, 1.5))

    # Create bars
    bars = ax.bar(range(len(rule_names)), probabilities, color=colors[0])

    # Customize the plot
    ax.set_xlabel("PPO Rules")
    ax.set_ylabel("Probability")

    # Set x-axis labels with rotation for readability
    ax.set_xticks(range(len(rule_names)))
    ax.set_xticklabels(rule_names)

    # Add grid for better readability
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)

    # Set y-axis limits with some padding
    max_prob = max(probabilities) if probabilities else 1
    ax.set_ylim(0, max_prob * 1.15)

    # Tight layout to prevent label cutoff
    plt.tight_layout()

    # Save the plot
    if output_path is None:
        json_path = Path(json_file_path)
        output_path = json_path.parent / f"{json_path.stem}_plot.png"

    # Also save as PDF for better quality in papers
    pdf_path = str(output_path).replace(".png", ".pdf")
    plt.savefig(pdf_path, bbox_inches="tight", dpi=300)

    # Optionally display the plot
    # plt.show()

    # Print summary statistics
    print(f"\n=== PPO Rule Statistics Summary ===")
    print(f"Total memory operations: {total_memops}")
    print(f"Total tests: {total_tests}")
    print(f"\nRule usage (sorted by probability):")

    # Sort rules by probability
    sorted_rules = sorted(
        rules.items(), key=lambda x: x[1]["probability"], reverse=True
    )
    for rule_name, stats in sorted_rules:
        print(
            f"  {rule_name:25s}: {stats['probability']:.4f} ({stats['count']:6d}/{total_memops})"
        )


def main():
    if len(sys.argv) < 2:
        # Try to find the most recent JSON file in ppo_stats_out directory
        ppo_stats_dir = Path("ppo_stats_out")
        if ppo_stats_dir.exists():
            json_files = list(ppo_stats_dir.glob("ppo_rules_*.json"))
            if json_files:
                # Get the most recent file
                json_file = max(json_files, key=lambda p: p.stat().st_mtime)
                print(f"No JSON file specified. Using most recent: {json_file}")
            else:
                print("Error: No JSON files found in ppo_stats_out/")
                print("Usage: python plot_ppo_rules.py <json_file_path>")
                sys.exit(1)
        else:
            print("Error: ppo_stats_out/ directory not found")
            print("Usage: python plot_ppo_rules.py <json_file_path>")
            sys.exit(1)
    else:
        json_file = sys.argv[1]

        if not os.path.exists(json_file):
            print(f"Error: File not found: {json_file}")
            sys.exit(1)

    # Optional: specify output path as second argument
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    plot_ppo_probabilities(json_file, output_path)


if __name__ == "__main__":
    main()
