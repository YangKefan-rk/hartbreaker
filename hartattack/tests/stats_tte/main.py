# Copyright 2026 Flavien Solt, Quentin Bordier ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only


# Toplevel for a cycle of program generation and RTL simulation.

from hartattack.fuzzfromdescriptor import (
    gen_new_test_instance,
    fuzz_single_from_descriptor,
)
from hartattack.instgen import ISAInstrClass
from hartattack.toleratebugs import tolerate_bug_for_bug_timing, is_tolerate_naxriscv_clint

import hartattack.runparams as rp
import multiprocessing as mp
import signal
import time
import threading
import os
import json
import subprocess

TIMEOUT = 60 * 100  # 60 minutes per testscases
NUM_CORES = int(os.environ.get("HARTATTACK_CORES", 200))
N_BUG_REDISCOVER = 20

BASE_DISTRIBUTION = {
    ISAInstrClass.ALU: 0.1,
    ISAInstrClass.ALU64: 0.1,
    ISAInstrClass.MULDIV: 0.1,
    ISAInstrClass.MULDIV64: 0.1,
    ISAInstrClass.JAL: 0.01,
    ISAInstrClass.JALR: 0.01,
    ISAInstrClass.BRANCH: 0.4,
    ISAInstrClass.MEM: 0.5,
    ISAInstrClass.MEM64: 0.5,
    ISAInstrClass.AMO: 0.0, # not supported, stores must be larger than loads
    ISAInstrClass.AMO64: 0.0,
    ISAInstrClass.FENCE: 0.000001,
    ISAInstrClass.MEMFPU: 0,
    ISAInstrClass.MEMFPUD: 0,
    ISAInstrClass.FPUFSM: 0,
    ISAInstrClass.FPU: 0,
    ISAInstrClass.FPU64: 0,
    ISAInstrClass.FPUD: 0,
    ISAInstrClass.FPUD64: 0,
    ISAInstrClass.REGFSM: 0.1,
    ISAInstrClass.TVECFSM: 0.1,
    ISAInstrClass.EPCFSM: 0.1,
    ISAInstrClass.FREE_POLLUTED: 5.0,       # utility for MCM fuzzing
    ISAInstrClass.CREATE_ADDR_DEP: 2.0,  # utility for MCM fuzzing
    ISAInstrClass.MACHINE_CSR: 0.1,
    ISAInstrClass.EXCEPTION: 0.1,
    ISAInstrClass.RANDOM_CSR: 0.0,
    ISAInstrClass.DESCEND_PRV: 0.1,
    ISAInstrClass.WFI_TRAP: 0.7,
    ISAInstrClass.WFI_NOTRAP: 0.4,
    ISAInstrClass.SEND_IPI: 5.0,
    ISAInstrClass.SEND_LOCAL_INTERRUPT: 0,
    ISAInstrClass.CLEAR_INTERRUPT: 0.4,
    ISAInstrClass.WRITE_INSTR: 0,
    ISAInstrClass.WAIT_FOR_INSTR: 0.0,
    ISAInstrClass.CLEAR_MDT: 0.0,
    ISAInstrClass.RESET_MCM: 0.0
}

class FuzzDesign:
    """Hold the arguments for the current run"""

    def __init__(
        self,
        design_name: str,
        num_cores: int,
        seed_offset: int,
    ):
        self.design_name = design_name
        self.num_cores = num_cores
        self.seed_offset = seed_offset

        self.callback_lock = threading.Lock()
        self.newly_finished_tests = 0
        self.curr_round_id = 0

        self.pool = mp.Pool(
            processes=num_cores,
            initializer=signal.signal,
            initargs=(signal.SIGINT, signal.SIG_IGN),
        )
        self.process_instance_id = 0
        self.start_time = time.time()
        self.over = False

    def test_done_callback(self, result=None):
        with self.callback_lock:
            self.newly_finished_tests += 1
            if isinstance(result, str):
                print(result)
                if self.design_name == 'dualboomv4':
                    if "MCM mismatch" in result and "hang" not in result:
                        self.over = True
                elif self.design_name == 'naxriscv_mcm':
                    if 'Found MCM violation' in result:
                        self.over = True
                elif self.design_name == 'naxriscv_int':
                    if 'timeout' in result:
                        self.over = True
                elif self.design_name == 'xiangshan':
                    if 'returned non-zero exit status 1' in result:
                        self.over = True
                else:
                    if "simulation timed out" in result:
                        self.over = True

    def start(self) -> float:
        assert self.num_cores > 0

        for _ in range(self.num_cores):
            self._apply_test()

        try:
            while not self.over:
                time.sleep(1)
                with self.callback_lock:
                    if self.newly_finished_tests > 0:
                        for _ in range(self.newly_finished_tests):
                            self._apply_test()
                        self.newly_finished_tests = 0
        except KeyboardInterrupt:
            print("Interrupted by user, cleaning up...")
            raise
        finally:
            elapsed = time.time() - self.start_time
            print("Terminating pool...")
            self.pool.terminate()
            self.pool.join()

        return elapsed

    def _apply_test(self):
        """launches a new testcase run"""
        test_params = self._gen_test_instance(
            self.seed_offset + self.process_instance_id
        )

        # Launch the async task
        async_result = self.pool.apply_async(
            fuzz_single_from_descriptor,
            args=(test_params, None)
        )

        # Store the async result for timeout handling
        self._handle_async_result(async_result)
        self.process_instance_id += 1
        print(f"new test {self.process_instance_id}")

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
                self.test_done_callback()
            except Exception as e:
                if self.design_name == "naxriscv":
                    subprocess.run(["pkill", "-9", "java"], stderr=subprocess.DEVNULL)
                # Handle other exceptions
                print(f"Exception in async task: {e}")
                self.test_done_callback()

        # Run the timeout handling in a separate thread
        threading.Thread(target=handle_result, daemon=True).start()

    def _gen_test_instance(self, random_seed: int):
        """Generates a new test instance given a random seed"""
        custom_boosters = BASE_DISTRIBUTION
        if self.design_name == 'dualboomv4':
            custom_boosters[ISAInstrClass.MEM] = 2
            custom_boosters[ISAInstrClass.MEM64] = 2
        elif self.design_name == 'xiangshan':
            custom_boosters[ISAInstrClass.SEND_LOCAL_INTERRUPT] = 0.6
        elif self.design_name == 'naxriscv_mcm':
            custom_boosters[ISAInstrClass.AMO64] = 0.1

        if self.design_name == 'naxriscv_mcm':
            design_name = 'naxriscv'
        elif self.design_name == 'naxriscv_int':
            design_name = 'naxriscv'
        else:
            design_name = self.design_name
        test_params = gen_new_test_instance(
            design_name, random_seed, True, custom_boosters=custom_boosters
        )
        return test_params


def launch_run(design, base_output_dir):

    output_dir = os.path.join(base_output_dir, design)
    os.makedirs(output_dir, exist_ok=True)
    verif_suffix = "_mcm" if rp.FUZZ_MCM else "_int"
    output_file = os.path.join(output_dir, f"{design}_{verif_suffix}.jsonl")
    # Create empty file (JSON Lines format - one JSON object per line)
    with open(output_file, "w") as f:
        pass  # Empty file, entries will be appended as lines
    print(f"\nResults will be saved to {output_file}")

    for attempt in range(N_BUG_REDISCOVER):
        print(f"[{design}] Rediscovery attempt {attempt + 1}/{N_BUG_REDISCOVER}")
        seed_offset = attempt * 10**6
        if 'naxriscv' in design:
            n_cores = 20
        else:
            n_cores = NUM_CORES
        fuzzer = FuzzDesign(design, n_cores, seed_offset)
        elapsed = fuzzer.start() * n_cores
        print(f"[{design}] Bug found in {elapsed:.2f}s (attempt {attempt + 1})")
        with open(output_file, "a") as f:
            f.write(json.dumps({"design": design, "attempt": attempt, "time_s": elapsed}) + "\n")

    print(f"[{design}] All {N_BUG_REDISCOVER} rediscoveries done.")

def configure_design(design):
    """Set runparams for the given design."""
    if design in ('toooba', 'xiangshan'):
        rp.FUZZ_MCM = False
        rp.USE_ADDR_REGS = False
        rp.FUZZ_INTERRUPT = True
        rp.SKIP_NO_INTERRUPT = True
        rp.JIT_SCENARIO = True
        rp.MAX_N_CONSECUTIVE_MEMOPS = 70
    elif design == 'naxriscv_int':
        rp.FUZZ_MCM = False
        rp.USE_ADDR_REGS = False
        rp.FUZZ_INTERRUPT = True
        rp.SKIP_NO_INTERRUPT = True
        rp.JIT_SCENARIO = True
        rp.MAX_N_CONSECUTIVE_MEMOPS = 70
        tolerate_bug_for_bug_timing('naxriscv', 'n1', True)
    elif design == 'naxriscv_mcm':
        rp.FUZZ_MCM = True
        rp.USE_ADDR_REGS = True
        rp.VERIFY_MEMORY_TRACE = "dat"
        rp.FUZZ_INTERRUPT = False
        rp.SKIP_NO_INTERRUPT = False
        rp.JIT_SCENARIO = False
        rp.MAX_N_CONSECUTIVE_MEMOPS = 70
    elif design == 'dualboomv4':
        rp.FUZZ_MCM = True
        rp.USE_ADDR_REGS = False
        rp.VERIFY_MEMORY_TRACE = None
        rp.FUZZ_INTERRUPT = False
        rp.SKIP_NO_INTERRUPT = False
        rp.JIT_SCENARIO = False
        rp.MAX_N_CONSECUTIVE_MEMOPS = 5


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Time-to-Exposure experiments")
    parser.add_argument("design", nargs="?", default=None,
                        help="Single design to run (default: all designs)")
    parser.add_argument("--output-dir", default="./tte_data",
                        help="Base output directory for TTE data")
    args = parser.parse_args()

    all_designs = ['dualboomv4', 'toooba', 'naxriscv_mcm', 'naxriscv_int', 'xiangshan']
    designs = [args.design] if args.design else all_designs

    rp.NO_FINAL_CHECK = True

    for design in designs:
        configure_design(design)
        print(f"Running test for {design}")
        launch_run(design, args.output_dir)

if __name__ == "__main__":
    main()

# keys
# boom, nax: 'MCM mismatch' and  no 'Pipeline has hung'
# toooba: timeout
# xiangshan: timeout
