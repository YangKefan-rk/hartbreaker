

# Toplevel for a cycle of program generation and RTL simulation.

from hartattack.fuzzfromdescriptor import (
    gen_new_test_instance,
    fuzz_single_from_descriptor,
)
from hartattack import runparams as mp

import hartattack.runparams as rp
from typing import Optional, TYPE_CHECKING
from datetime import datetime
import multiprocessing as mp
import signal
import time
import threading
import os
import json
import subprocess
import argparse
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from hartattack.proggen import TestCaseGenerator
    from hartattack.proggen import TestCaseGenerator

TIMEOUT = 60 * 100  # 60 minutes per testscases

class FuzzDesign:
    """Hold the arguments for the current run"""

    def __init__(
        self,
        design_name: str,
        num_cores: int,
        seed_offset: int,
        target_tests: int,
        target_instrs: int,
        verif_enabled: bool,
    ):
        self.design_name = design_name
        self.num_cores = num_cores
        self.seed_offset = seed_offset
        self.target_tests = target_tests
        self.target_instrs = target_instrs
        self.verif_enabled = verif_enabled

        self.callback_lock = threading.Lock()
        self.newly_finished_tests = 0
        self.curr_round_id = 0
        self.all_times_to_detection = []
        self.rtl_timeouts = 0
        self.z3_timeouts = 0
        self.tested_programs = 0

        self.pool = mp.Pool(
            processes=num_cores,
            initializer=signal.signal,
            initargs=(signal.SIGINT, signal.SIG_IGN),
        )
        self.process_instance_id = 0

        self.spike_ns_per_instr: Optional[float] = None

        pretty_timestamp = datetime.now().strftime("%Y-%d-%m_%H-%M-%S")
        self.log_file_name = f"log_{self.design_name}_{pretty_timestamp}.log"
        datadir = os.getenv("HARTATTACK_DATADIR")
        if not datadir:
            raise ValueError("HARTATTACK_DATADIR var not set, source ./script/all.sh")
        logs_dir = os.path.join(datadir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        self.log_file_path = f"{logs_dir}/{self.log_file_name}"

        self.json_output_file: Optional[str] = None

    def test_done_callback(
        self, ret: Optional["TestCaseGenerator"], timed_out: bool = False
    ):
        with self.callback_lock:
            self.newly_finished_tests += 1
            if timed_out:
                self.z3_timeouts += 1
            elif ret is None:
                self.rtl_timeouts += 1
            else:
                self.tested_programs += 1
                # Collect all the timing and size information
                entry = {
                    "instructions count": ret.get_total_fuzzing_instrs(),
                    "generation": (
                        ret.seconds_spent_in_gen_bbs
                        + ret.seconds_spent_in_gen_elf
                    ),
                    "iss_sim" : ret.seconds_spent_in_spike_resol,
                    "simulation": ret.seconds_spent_in_rtl_sim,
                    "verification": ret.seconds_spent_verifying_output,
                }

                # Append to JSON file (using JSON Lines format for efficiency)
                if self.json_output_file:
                    try:
                        # Append a single JSON line (no need to read the entire file)
                        with open(self.json_output_file, "a") as f:
                            json.dump(entry, f)
                            f.write("\n")
                    except Exception as e:
                        print(f"Error writing to JSON file: {e}")

    def start(self):
        assert self.num_cores > 0
        console = self.create_table()

        for _ in range(self.num_cores):
            self._apply_test()

        try:
            while True:
                time.sleep(2)
                with self.callback_lock:
                    # Check if we've reached the target
                    if self.tested_programs >= self.target_tests:
                        print(
                            f"\nReached target of {self.target_tests} tested programs. Stopping..."
                        )
                        break

                    if self.newly_finished_tests > 0:
                        self.update_table(console)
                        for _ in range(self.newly_finished_tests):
                            self._apply_test()
                        self.newly_finished_tests = 0
        except KeyboardInterrupt:
            print("Terminating pool...")
        finally:
            # Always clean up the pool
            print("Terminating pool...")
            # Kill each worker process individually
            if hasattr(self.pool, "_pool"):
                for worker in self.pool._pool:  # type: ignore
                    try:
                        os.kill(worker.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # Process already terminated

            # exit all
            os._exit(0)

    def _apply_test(self):
        """launches a new testcase run"""
        test_params = self._gen_test_instance(
            self.seed_offset + self.process_instance_id, self.target_instrs
        )

        # Launch the async task
        async_result = self.pool.apply_async(
            fuzz_single_from_descriptor,
            args=(test_params, self.log_file_path),
        )

        # Store the async result for timeout handling
        self._handle_async_result(async_result)
        self.process_instance_id += 1

    def _handle_async_result(self, async_result):
        """Handle async result with timeout in a separate thread"""

        def handle_result():
            try:
                # Wait for result with timeout
                timeout_seconds = TIMEOUT
                result = async_result.get(timeout=timeout_seconds)
                # Call the callback manually
                self.test_done_callback(result)
            except mp.TimeoutError:
                if self.design_name == "naxriscv":
                    subprocess.run(["pkill", "-9", "java"], stderr=subprocess.DEVNULL)
                # Timeout occurred - count as Z3 timeout
                print("Task timed out, counting as Z3 timeout")
                self.test_done_callback(None, timed_out=True)
            except Exception as e:
                if self.design_name == "naxriscv":
                    subprocess.run(["pkill", "-9", "java"], stderr=subprocess.DEVNULL)
                # Handle other exceptions
                print(f"Exception in async task: {e}")
                self.test_done_callback(None)

        # Run the timeout handling in a separate thread
        threading.Thread(target=handle_result, daemon=True).start()

    def _gen_test_instance(self, random_seed: int, nmax_instrs: int):
        """Generates a new test instance given a random seed"""
        memsize = 1 << 20
        num_bbs = 10000
        test_params = gen_new_test_instance(
            self.design_name, random_seed, True, memsize, num_bbs
        )
        test_params.set_nmax_instructions(nmax_instrs)
        return test_params

    def update_table(self, console: Console):
        # Clear the console and recreate the table with updated data
        console.clear()
        updated_table = Table(title="Fuzz Design Progress")
        updated_table.add_column("Design Name", justify="center")
        updated_table.add_column("#Cores", justify="center")
        updated_table.add_column("Target Tests", justify="center")
        updated_table.add_column("Target Instrs", justify="center")
        updated_table.add_column("Verif Mode", justify="center")
        updated_table.add_column("Tested Programs", justify="center")
        updated_table.add_column("#Crashes", justify="center")
        updated_table.add_column("#Z3 Timeouts", justify="center")

        verif_str = "✓ Enabled" if self.verif_enabled else "✗ Disabled"
        updated_table.add_row(
            self.design_name,
            str(self.num_cores),
            str(self.target_tests),
            str(self.target_instrs),
            verif_str,
            str(self.tested_programs),
            str(self.rtl_timeouts),
            str(self.z3_timeouts),
        )
        console.print(updated_table)

    def create_table(self):
        console = Console()
        table = Table(title="Fuzz Design Progress")
        table.add_column("Design Name", justify="center")
        table.add_column("#Cores", justify="center")
        table.add_column("Target Tests", justify="center")
        table.add_column("Target Instrs", justify="center")
        table.add_column("Verif Mode", justify="center")
        table.add_column("Tested Programs", justify="center")
        table.add_column("#Crashes", justify="center")
        table.add_column("#Z3 Timeouts", justify="center")
        console.clear()
        console.print(table)
        return console


def main():
    parser = argparse.ArgumentParser(description="Run fuzzing benchmarks on a design")
    parser.add_argument(
        "design",
        type=str,
        help="Design name (e.g., tripplerocket, naxriscv, xiangshan)",
    )
    parser.add_argument(
        "--num-instrs", type=int, required=True, help="Number of instructions"
    )
    parser.add_argument(
        "--verif", action="store_true", help="Enable MCM verification mode"
    )
    parser.add_argument(
        "--total-num-instrs",
        type=int,
        required=True,
        help="Total number of instructions to generate",
    )

    args = parser.parse_args()

    design = args.design
    num_instr = args.num_instrs
    enable_verif = args.verif

    num_tests = args.total_num_instrs / num_instr

    NUM_CORES = 100

    rp.NO_FINAL_CHECK = True

    if enable_verif:
        rp.FUZZ_MCM = True
        rp.USE_ADDR_REGS = True
        rp.VERIFY_MEMORY_TRACE = "dat"
        rp.FUZZ_INTERRUPT = False
        rp.SKIP_NO_INTERRUPT = False
        rp.JIT_SCENARIO = False
        rp.MAX_N_CONSECUTIVE_MEMOPS = 70
    else:
        rp.FUZZ_MCM = False
        rp.USE_ADDR_REGS = False
        rp.FUZZ_INTERRUPT = True
        rp.SKIP_NO_INTERRUPT = True
        rp.JIT_SCENARIO = True

    data_base = os.environ.get("HARTATTACK_BENCH_DIR", os.path.join(os.environ.get("HARTATTACK_DATADIR", "."), "bench"))
    output_dir = os.path.join(data_base, "verification_overhead", design, str(num_instr))
    os.makedirs(output_dir, exist_ok=True)
    verif_suffix = "_verif" if rp.FUZZ_MCM else "_noverif"
    output_file = os.path.join(output_dir, f"{design}_{num_instr}{verif_suffix}.jsonl")
    # Create empty file (JSON Lines format - one JSON object per line)
    with open(output_file, "w") as f:
        pass  # Empty file, entries will be appended as lines
    print(f"\nResults will be saved to {output_file}")

    fuzzer = FuzzDesign(design, NUM_CORES, 0, num_tests, num_instr, enable_verif)
    fuzzer.json_output_file = output_file
    fuzzer.start()

    # Verify output JSONL file contains at least the requested number of test entries.
    # This assert will raise an AssertionError if the file doesn't contain enough
    # entries, which lets the caller (or CI) detect incomplete runs.
    with open(output_file, "r") as f:
        # Count lines in JSON Lines format
        run_data = [json.loads(line) for line in f if line.strip()]

    assert isinstance(run_data, list), (
        f"{output_file} does not contain valid JSON lines"
    )
    assert len(run_data) >= (num_tests - num_cores), (
        f"Not enough entries in {output_file}: got {len(run_data)}, expected at least {num_tests - num_cores}"
    )


if __name__ == "__main__":
    main()
