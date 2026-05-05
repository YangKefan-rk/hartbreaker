# Copyright 2026 Flavien Solt, Quentin Bordier ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only


# Toplevel for a cycle of program generation and RTL simulation.

from .fuzzfromdescriptor import (
    gen_new_test_instance,
    fuzz_single_from_descriptor,
    gen_fuzzerstate_elf_expectedvals,
)
from . import runparams
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from tqdm import tqdm
from rich.console import Console
from rich.table import Table
import multiprocessing as mp
import signal
import time
import threading
import logging
import os
import shutil

if TYPE_CHECKING:
    from .params import TestParams
    from .proggen import TestCaseGenerator

logging.basicConfig(level=logging.INFO)

TIMEOUT = 30 * 60  # 30 minutes per testscases


"""This is the main entry point of the program. The main function will create
an instance of this object, and call one of its functions to run the desired
functionality of cascade
"""


def _gen_elf_unpack(args):
    return _gen_elf(*args)


def _gen_elf(test_params: "TestParams", outdir_path: str):
    """Generates a single elf"""
    testcase_generator = gen_fuzzerstate_elf_expectedvals(test_params)
    elfpath = testcase_generator.rtl_elfpath
    design_name = test_params.design_name
    shutil.move(
        elfpath, os.path.join(outdir_path, f"{design_name}_{test_params.randseed}.elf")
    )
    return f"{outdir_path}/{design_name}_{test_params.randseed}.elf"


class FuzzDesign:
    """Hold the arguments for the current run"""

    def __init__(
        self,
        design_name: str,
        num_cores: int,
        seed_offset: int,
        can_authorize_privileges: bool,
        memsize: Optional[int],
        num_bbs: Optional[int],
    ):
        self.design_name = design_name
        self.num_cores = num_cores
        self.seed_offset = seed_offset
        self.can_authorize_privileges = can_authorize_privileges

        self.callback_lock = threading.Lock()
        self.newly_finished_tests = 0
        self.curr_round_id = 0
        self.all_times_to_detection = []
        self.rtl_timeouts = 0
        self.z3_timeouts = 0
        self.tested_programs = 0

        self.memsize: Optional[int] = memsize
        self.num_bbs: Optional[int] = num_bbs

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

    def test_done_callback(
        self, ret, timed_out: bool = False
    ):
        with self.callback_lock:
            self.newly_finished_tests += 1
            if timed_out:
                self.z3_timeouts += 1
            elif ret is None:
                self.rtl_timeouts += 1
                self.tested_programs += 1
            elif isinstance(ret, str):
                self.rtl_timeouts += 1
                self.tested_programs += 1
            else:
                self.tested_programs += 1

    def genelf_callback(self, ret):
        with self.callback_lock:
            self.newly_finished_tests += 1

    def start(self):
        assert self.num_cores > 0

        console = self.create_table()

        for _ in range(self.num_cores):
            self._apply_test()

        try:
            while True:
                time.sleep(2)
                with self.callback_lock:
                    if self.newly_finished_tests > 0:
                        self.update_table(console)
                        for _ in range(self.newly_finished_tests):
                            self._apply_test()
                        self.newly_finished_tests = 0
        except KeyboardInterrupt:
            logging.info("Terminating pool...")
            self.pool.terminate()
            self.pool.join()

    def gen_specific_elf(self):
        """generates an elf with a specific random seed"""
        target_dir = os.path.join(runparams.PATH_TO_TMP, "manyelfs")
        # Ensure that the output directory exists.
        os.makedirs(target_dir, exist_ok=True)
        test_params = self._gen_test_instance(self.seed_offset)
        logging.info(f"Generating single elf: {test_params.instance_to_str()}")
        out_path = _gen_elf(test_params, target_dir)
        logging.info(f"Saved elf at: {out_path}")

    def fuzz_single(self):
        """Fuzzes a single elf"""
        test_params = self._gen_test_instance(self.seed_offset)
        logging.info(f"Fuzzing single elf: {test_params.instance_to_str()}")
        fuzz_single_from_descriptor(test_params, self.log_file_path)

    def gen_many_elfs(self, num_elfs: int):
        """generates num_elfs elf testcases"""
        logging.info(f"Generating {num_elfs} using {self.num_cores} host cores")

        target_dir = os.path.join(runparams.PATH_TO_TMP, "manyelfs")
        # Ensure that the output directory exists.
        os.makedirs(target_dir, exist_ok=True)
        # Gen the program descriptors.
        test_params = [self._gen_test_instance(i) for i in range(num_elfs)]
        workloads = [(test_params[i], target_dir) for i in range(num_elfs)]
        with mp.Pool(
            self.num_cores,
            initializer=signal.signal,
            initargs=(signal.SIGINT, signal.SIG_IGN),
        ) as pool:
            pbar = tqdm(total=num_elfs)
            for _ in pool.imap_unordered(_gen_elf_unpack, workloads):
                pbar.update(1)
            pbar.close()

    def _apply_gen_elf(self, outdir: str):
        """Calls _gen_elf asynchronously"""
        test_params = self._gen_test_instance(
            self.seed_offset + self.process_instance_id
        )
        self.pool.apply_async(
            _gen_elf,
            args=(test_params, outdir),
            callback=self.genelf_callback,
        )
        self.process_instance_id += 1

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
            except Exception as e:
                # Handle other exceptions
                print(f"Exception in async task: {e}")
                self.test_done_callback(None)

        # Run the timeout handling in a separate thread
        threading.Thread(target=handle_result, daemon=True).start()

    def _gen_test_instance(self, random_seed: int):
        """Generates a new test instance given a random seed"""
        test_params = gen_new_test_instance(
            self.design_name,
            random_seed,
            self.can_authorize_privileges,
            self.memsize,
            self.num_bbs,
        )
        return test_params

    def update_table(self, console: Console):
        # Clear the console and recreate the table with updated data
        console.clear()
        updated_table = Table(title="Fuzz Design Progress")
        updated_table.add_column("Design Name", justify="center")
        updated_table.add_column("#Cores", justify="center")
        updated_table.add_column("Tested Programs", justify="center")
        updated_table.add_column("#Crashes", justify="center")
        updated_table.add_column("#Z3 Timeouts", justify="center")
        updated_table.add_row(
            self.design_name,
            str(self.num_cores),
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
        table.add_column("Tested Programs", justify="center")
        table.add_column("#Crashes", justify="center")
        table.add_column("#Z3 Timeouts", justify="center")
        console.clear()
        console.print(table)
        return console
