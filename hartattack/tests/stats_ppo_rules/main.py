

# Toplevel for a cycle of program generation and RTL simulation.

from hartattack.fuzzfromdescriptor import (
    gen_new_test_instance,
    fuzz_single_from_descriptor,
)
import hartattack.runparams as rp
from typing import Optional, TYPE_CHECKING
from datetime import datetime
import multiprocessing as mp
import signal
import time
import threading
import os
import json

if TYPE_CHECKING:
    from hartattack.proggen import TestCaseGenerator

TIMEOUT = 10 * 60  # 10 minutes per testscases


"""This is the main entry point of the program. The main function will create
an instance of this object, and call one of its functions to run the desired
functionality of cascade
"""


class FuzzDesign:
    """Hold the arguments for the current run"""

    def __init__(
        self,
        design_name: str,
        num_cores: int,
        seed_offset: int,
        can_authorize_privileges: bool,
    ):
        self.design_name = design_name
        self.num_cores = num_cores
        self.seed_offset = seed_offset
        self.can_authorize_privileges = can_authorize_privileges

        self.callback_lock = threading.Lock()
        self.newly_finished_tests = 0
        self.rtl_timeouts = 0
        self.z3_timeouts = 0
        self.tested_programs = 0
        def _worker_init():
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            import sys
            sys.stdout = open(os.devnull, "w")
            sys.stderr = open(os.devnull, "w")

        self.pool = mp.Pool(
            processes=num_cores,
            initializer=_worker_init,
        )
        self.process_instance_id = 0

        self.throughput_data = []

        # PPO rule statistics
        self.ppo_rule_stats = {
            "1": 0,
            "2": 0,
            "3": 0,
            "4": 0,
            "5": 0,
            "6": 0,
            "7": 0,
            "9": 0,
            "10": 0,
            "11": 0,
            "12": 0,
            "13": 0,
        }
        self.total_memops = 0

        pretty_timestamp = datetime.now().strftime("%Y-%d-%m_%H-%M-%S")
        self.log_file_name = f"log_{self.design_name}_{pretty_timestamp}.log"
        self.json_file_name = f"ppo_rules_{self.design_name}.json"
        datadir = os.getenv("HARTATTACK_DATADIR")
        if not datadir:
            raise ValueError("HARTATTACK_DATADIR var not set, source ./script/all.sh")
        logs_dir = os.path.join(datadir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        self.log_file_path = f"{logs_dir}/{self.log_file_name}"

    def test_done_callback(
        self, ret: Optional["TestCaseGenerator"], timed_out: bool = False
    ):
        with self.callback_lock:
            self.newly_finished_tests += 1
            if timed_out:
                self.z3_timeouts += 1
                print(
                    f"Z3 timeout - Total: {self.z3_timeouts} Z3 timeouts, {self.rtl_timeouts} RTL timeouts, {self.tested_programs} completed"
                )
            elif ret is None:
                self.rtl_timeouts += 1
                pass
                print(
                    f"RTL timeout - Total: {self.z3_timeouts} Z3 timeouts, {self.rtl_timeouts} RTL timeouts, {self.tested_programs} completed"
                )
            elif isinstance(ret, str):
                # Error message returned, skip
                pass
            else:
                self.tested_programs += 1

                # Collect PPO rule statistics
                for steps in ret.mcmstate.steps:
                    for memops in steps.step_memops.values():
                        for memop in memops.values():
                            self.total_memops += 1

                            # Count each rule if it's used (non-empty set)
                            if memop.rw_w_overlap:
                                self.ppo_rule_stats["1"] += 1
                            if memop.r_r_overlap:
                                self.ppo_rule_stats["2"] += 1
                            if memop.amo_read:
                                self.ppo_rule_stats["3"] += 1
                            if memop.fence_successor:
                                self.ppo_rule_stats["4"] += 1
                            if memop.acquire:
                                self.ppo_rule_stats["5"] += 1
                            if memop.release:
                                self.ppo_rule_stats["6"] += 1
                            if memop.sequential:
                                self.ppo_rule_stats["7"] += 1
                            if memop.syntactic_addr_dep:
                                self.ppo_rule_stats["9"] += 1
                            if memop.syntactic_data_dep:
                                self.ppo_rule_stats["10"] += 1
                            if memop.syntactic_ctrl_dep:
                                self.ppo_rule_stats["11"] += 1
                            if memop.rule_12:
                                self.ppo_rule_stats["12"] += 1
                            if memop.rule_13:
                                self.ppo_rule_stats["13"] += 1

                # Log progress every 10 tests
                if self.tested_programs % 10 == 0:
                    print(
                        f"Progress: {self.tested_programs} tests completed, "
                        f"Timeouts: {self.rtl_timeouts} RTL / {self.z3_timeouts} Z3"
                    )

    def genelf_callback(self, ret):
        with self.callback_lock:
            self.newly_finished_tests += 1

    def start(self, target_num_progs: int):
        assert self.num_cores > 0

        print(
            f"Starting fuzzing {target_num_progs} programs with {self.num_cores} cores"
        )

        for _ in range(self.num_cores):
            self._apply_test()

        print(f"Launched {self.num_cores} initial tests")
        last_log_time = time.time()
        try:
            while True:
                time.sleep(2)
                # Log progress every 30 seconds
                if time.time() - last_log_time >= 30:
                    with self.callback_lock:
                        print(f"Test status: {self.tested_programs}/{target_num_progs}")
                        last_log_time = time.time()

                if self.tested_programs >= target_num_progs:
                    print(f"Generated all programs. Stopping...")
                    break

                with self.callback_lock:
                    if self.newly_finished_tests > 0:
                        for _ in range(self.newly_finished_tests):
                            self._apply_test()
                        self.newly_finished_tests = 0
        except KeyboardInterrupt:
            print("Terminating pool...")
        finally:
            self.pool.terminate()
            self.pool.join()
            final_msg = f"Finished: {self.tested_programs} tests in"
            print(final_msg)

    def _apply_test(self):
        """launches a new testcase run"""
        test_params = self._gen_test_instance(
            self.seed_offset + self.process_instance_id
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
                # Timeout occurred - count as Z3 timeout
                print("Task timed out, counting as Z3 timeout")
                self.test_done_callback(None, timed_out=True)
            except Exception:
                self.test_done_callback(None)

        # Run the timeout handling in a separate thread
        threading.Thread(target=handle_result, daemon=True).start()

    def _gen_test_instance(self, random_seed: int):
        """Generates a new test instance given a random seed"""
        test_params = gen_new_test_instance(
            self.design_name, random_seed, self.can_authorize_privileges
        )
        return test_params


def main():
    NUM_CORES = 150
    NUM_PROGS = 10000

    ##
    # Fuzz
    ##
    fuzzer = FuzzDesign("dualrocket", NUM_CORES, 0, True)
    fuzzer.start(NUM_PROGS)

    ##
    # Compute statistics and save to JSON
    ##
    # Calculate probabilities
    ppo_stats_with_probs = {
        "total_memops": fuzzer.total_memops,
        "total_tests": fuzzer.tested_programs,
        "rules": {},
    }

    for rule_name, count in fuzzer.ppo_rule_stats.items():
        probability = count / fuzzer.total_memops if fuzzer.total_memops > 0 else 0
        ppo_stats_with_probs["rules"][rule_name] = {
            "count": count,
            "probability": probability,
        }

    # Write output next to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "ppo_stats_out")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, fuzzer.json_file_name)

    with open(output_file, "w") as f:
        json.dump(ppo_stats_with_probs, f, indent=2)

    print(f"\nPPO Rule Statistics saved to: {output_file}")
    print(f"Total memory operations analyzed: {fuzzer.total_memops}")
    print("\nRule usage probabilities:")
    for rule_name, stats in ppo_stats_with_probs["rules"].items():
        print(
            f"  {rule_name}: {stats['probability']:.4f} ({stats['count']}/{fuzzer.total_memops})"
        )


if __name__ == "__main__":
    if "HARTATTACK_ENV_SOURCED" not in os.environ:
        raise Exception(
            "The Cascade environment must be sourced prior to running the Python recipes."
        )
    rp.FUZZ_MCM = True
    rp.USE_ADDR_REGS = True
    rp.VERIFY_MEMORY_TRACE = None
    rp.FUZZ_INTERRUPT = False
    rp.SKIP_NO_INTERRUPT = False
    rp.JIT_SCENARIO = False
    rp.MAX_N_CONSECUTIVE_MEMOPS = 5
    main()
