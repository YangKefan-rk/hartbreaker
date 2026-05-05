# handles running the corpus of tests of the target core and properly store
# coverage information

import multiprocessing
import subprocess
import os
import sys
import argparse
import logging
import tempfile
import shutil
import datetime
import time
from tqdm import tqdm

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _runsim_chipyard(sim_path: str, elf_path: str, tool_output_path: str):
    """Runs a simulation of a chipyard SoC"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        passed = False
        try:
            result = subprocess.run(
                [
                    sim_path,
                    elf_path,
                    f"+loadmem={elf_path}",
                ],
                text=True,
                timeout=60 * 2,  # 2 minutes timeout
                cwd=tmp_dir,
                capture_output=True,
            )
            passed = True
        except subprocess.TimeoutExpired:
            logger.debug(f"Simulation timed out for {elf_path}")

        # Check for the generated file
        output_file = os.path.join(tmp_dir, "auto_cover_toggled.out")
        if os.path.exists(output_file):
            # Generate unique name using timestamp, process ID, and random component
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            pid = os.getpid()
            # Use a counter approach with atomic file creation
            counter = 0
            while True:
                unique_name = f"auto_cover_toggled_{timestamp}_{pid}_{counter}.out"
                dest_path = os.path.join(tool_output_path, unique_name)
                if not os.path.exists(dest_path):
                    break
                counter += 1
            shutil.move(output_file, dest_path)
            logger.debug(f"Moved output to {dest_path}")
        else:
            logger.warning("Expected output file 'auto_cover_toggled.out' not found")

        return passed


def _run_task(task):
    """Wrapper to unpack task tuple for multiprocessing"""
    return _runsim_chipyard(*task)


def run_tests(sim_path: str, num_cores: int, corpus_path: str, output_dir_path: str,
              time_budget: float = 0):
    """Run test corpus through the simulator and collect coverage.

    Args:
        time_budget: Maximum time in seconds for the entire run. 0 means no limit.
    """
    start_time = time.time()
    logger.info(f"looking for corpus in {corpus_path}")
    if time_budget > 0:
        logger.info(f"Time budget: {time_budget:.0f}s")
    dirs = [
        dir
        for dir in os.listdir(corpus_path)
        if os.path.isdir(os.path.join(corpus_path, dir))
    ]
    for dir in dirs:
        if time_budget > 0 and time.time() - start_time >= time_budget:
            logger.info(f"Time budget exhausted, stopping")
            break

        corpus_dir_path = os.path.join(corpus_path, dir)
        tool_output_base = os.path.join(output_dir_path, dir)

        # Find all .elf files recursively
        elf_files = []
        for root, _, files in os.walk(corpus_dir_path):
            for file in files:
                if file.endswith(".elf") or file.endswith(".o"):
                    elf_files.append(os.path.join(root, file))

        logger.info(f"For corpus: {dir}, found: {len(elf_files)}")

        # Prepare tasks
        tasks = []
        for elf_path in elf_files:
            rel_path = os.path.relpath(elf_path, corpus_dir_path)
            output_subdir = os.path.join(tool_output_base, os.path.dirname(rel_path))
            os.makedirs(output_subdir, exist_ok=True)
            tasks.append((sim_path, elf_path, output_subdir))

        # Run in parallel
        results = []
        with multiprocessing.Pool(processes=num_cores) as pool:
            for result in tqdm(
                pool.imap_unordered(_run_task, tasks),
                total=len(tasks),
                desc=f"Processing {dir}",
            ):
                results.append(result)
                if time_budget > 0 and time.time() - start_time >= time_budget:
                    logger.info(f"Time budget exhausted after {len(results)}/{len(tasks)} tests")
                    pool.terminate()
                    break

        # Count failed tests
        total_tests = len(results)
        failed_tests = sum(not r for r in results)
        logger.info(f"Corpus {dir}: {total_tests} tests run, {failed_tests} failed")

    elapsed = time.time() - start_time
    logger.info(f"Total time: {elapsed:.0f}s")


def main():
    # get some arguments
    parser = argparse.ArgumentParser(description="Run the corpus on boom")
    parser.add_argument("--sim", type=str, required=True, help="path to simulator")
    parser.add_argument("--corpus", type=str, required=True, help="path to the corpus")
    parser.add_argument(
        "--num-cores", type=int, default=1, help="Number of cores allocated to fuzzing"
    )
    parser.add_argument(
        "--output", type=str, default="./cov_data",
        help="Output directory for coverage data"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing output directory without prompting"
    )
    parser.add_argument(
        "--time-budget", type=float, default=0,
        help="Maximum time in seconds for coverage collection. 0 means no limit."
    )
    args = parser.parse_args()
    sim_path = os.path.realpath(args.sim)
    num_cores = args.num_cores
    corpus_path = os.path.realpath(args.corpus)

    output_dir_path = os.path.realpath(args.output)

    # Check if output dir exists
    if os.path.exists(output_dir_path):
        if args.force:
            shutil.rmtree(output_dir_path)
            os.makedirs(output_dir_path)
        else:
            logger.info(f"Output directory {output_dir_path} already exists, appending results")
    else:
        os.makedirs(output_dir_path)
    logger.info(f"storing output in {output_dir_path}")

    # run tests
    run_tests(sim_path, num_cores, corpus_path, output_dir_path,
              time_budget=args.time_budget)


if __name__ == "__main__":
    main()
