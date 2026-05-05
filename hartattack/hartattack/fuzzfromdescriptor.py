# Copyright 2026 Flavien Solt, Quentin Bordier ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only


# This script executes the fuzzer to find faulting programs.

from functools import wraps
from multiprocessing.context import TimeoutError
from multiprocessing.pool import ThreadPool
from typing import Optional
from random import Random
from threading import Lock
import os
import time
import traceback
from . import runparams
from .params import PROBA_AUTHORIZE_PRIVILEGES, TestParams
from .proggen import TestCaseGenerator
from .rtlsim import runtest_simulator, check_regs, parse_sim_output
from .genelf import gen_elf_from_bbs
from .preisasim import spike_resolution

LOG2_MEMSIZE_UPPERBOUND = 20
NUM_MAX_BBS_UPPERBOUND = 200


def timeout(seconds):
    def timeout_wrapper(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            try:
                pool = ThreadPool(processes=1)
                result = pool.apply_async(func, args, kwargs)
                return result.get(timeout=seconds)
            except TimeoutError:
                return None

        return wrapped

    return timeout_wrapper


def gen_new_test_instance(
    design_name: str,
    randseed: int,
    can_authorize_privileges: bool,
    memsize: Optional[int] = None,
    num_bbs: Optional[int] = None,
    fixed_priv: bool = False,
    custom_boosters = None
):
    """Creates a TestParam instance. Each test param instance is a program
    descriptor.

    Parameters:
        design_name: the name of the design on which the testcase is meant
            to run
        randseed: the integer used to seed the pseudo random number
            generator
        can_authorize_privileges: set to true if we allow the testcase to
            switch to lower priviledge levels
        spike_ns_per_instr: the approximate time needed to execute an
            instruction on spike.
        medeleg_mask: The set of supported exceptions that can be
            deleguated by the current design
        memsize: If True, sets the memory size
        num_bbs: If true, sets the number of basic
            blocks allowed
        fixed_priv: If True, set the privilege level to that of
            the can_authorize_privileges parameter
    """

    local_random = Random(randseed)

    if memsize is None:
        memsize = local_random.randrange(1 << 19, 1 << LOG2_MEMSIZE_UPPERBOUND)
        memsize = memsize & ~0x3  # Ensure 4-byte alignment
    if num_bbs is None:
        num_bbs = local_random.randrange(70, NUM_MAX_BBS_UPPERBOUND)
    if can_authorize_privileges and not fixed_priv:
        can_authorize_privileges = local_random.random() < PROBA_AUTHORIZE_PRIVILEGES

    assert memsize % 4 == 0, "memory size must be word alligned"

    test_params = TestParams(
        design_name,
        memsize,
        randseed,
        num_bbs,
        can_authorize_privileges,
        local_random,
        custom_boosters=custom_boosters
    )

    return test_params

def gen_fuzzerstate_elf_expectedvals(test_params: TestParams) -> "TestCaseGenerator":
    """The main function for a single fuzzer run. It creates a new fuzzer state,
    populates it with basic blocks, and then runs the spike resolution. It does
    not run the RTL simulation.

    Returns:
        (testcase_generator, rtl_elfpath, expected_regvals, genprog_time,
        spike_resol_time, genelf_time) where expected_regval is a list of
        expected reg values
    """
    if __debug__:
        assert test_params.nmax_bbs is None or test_params.nmax_bbs > 0

    start = time.time()
    success = False
    n_retry = 0
    while not success:
        test_params.prng.seed(test_params.randseed + n_retry)
        testcase_generator = TestCaseGenerator(test_params)
        success = testcase_generator.gen_program(test_params)
        if not success:
            n_retry += 1

    testcase_generator.seconds_spent_in_gen_bbs = time.time() - start

    # spike resolution
    start = time.time()
    testcase_generator.expected_regvals = spike_resolution(
        testcase_generator, test_params
    )
    testcase_generator.seconds_spent_in_spike_resol = time.time() - start

    start = time.time()
    # This is typically quite short
    testcase_generator.prepare_testcase_for_rtl(test_params)
    testcase_generator.rtl_elfpath = gen_elf_from_bbs(
        testcase_generator, False, "rtl", test_params, is_rtl=True
    )
    testcase_generator.seconds_spent_in_gen_elf = time.time() - start

    return testcase_generator


###
# Exposed function
###


def run_rtl(
    test_params: TestParams,
    nmax_instrs: Optional[int] = None,
):
    if nmax_instrs:
        test_params.set_nmax_instructions(nmax_instrs)

    testcase_generator = gen_fuzzerstate_elf_expectedvals(test_params)

    start = time.time()
    success, exec_out = runtest_simulator(
        testcase_generator,
        test_params,
        testcase_generator.rtl_elfpath,
    )
    testcase_generator.seconds_spent_in_rtl_sim = time.time() - start

    start = time.time()
    if success:
        received_regvals = parse_sim_output(
            test_params.design_name,
            exec_out,
            testcase_generator.corestates,
            testcase_generator.mcmstate,
        )
        if runparams.FUZZ_MCM:
            testcase_generator.validate_output(test_params)
        reg_mismatch = []
        # FIXME we do not check the final register values on naxriscv
        if testcase_generator.are_regs_polluted() or test_params.design_name in (
            "naxriscv",
            "vexiiriscv",
        ):
            reg_mismatch = []
        elif not runparams.NO_FINAL_CHECK:
            reg_mismatch = check_regs(
                received_regvals,
                testcase_generator,
                test_params,
                testcase_generator.expected_regvals,
            )
        is_success = not bool(reg_mismatch)
        rtl_msg = "\n  ".join(reg_mismatch)
    else:
        is_success = False
        rtl_msg = f"timeout for testcase: {test_params.instance_to_str()}\n {exec_out}"

    testcase_generator.seconds_spent_verifying_output = time.time() - start

    if runparams.REMOVE_TMPFILES and is_success:
        os.remove(testcase_generator.rtl_elfpath)
    else:
        # print("rtl elfpath", testcase_generator.rtl_elfpath)
        pass

    if not is_success:
        raise Exception(rtl_msg)
    return testcase_generator


_log_file_lock = Lock()


@timeout(seconds=60 * 60 * 2)
def fuzz_single_from_descriptor(
    test_params: TestParams,
    log_file_path: Optional[str] = None,
):
    try:
        testcase_generator = run_rtl(test_params)
        return testcase_generator
    except Exception as e:
        error_message = "Failed test_run_rtl_single for params:\n memsize: {}, design_name: {}, randseed: {}, nmax_bbs: {}, authorize_privileges: {} -- ({}, {}, {}, {}, {})\n{}".format(
            test_params.memsize,
            test_params.design_name,
            test_params.randseed,
            test_params.nmax_bbs,
            test_params.authorize_privileges,
            test_params.memsize,
            test_params.design_name,
            test_params.randseed,
            test_params.nmax_bbs,
            test_params.authorize_privileges,
            traceback.format_exc(),
        )
        if log_file_path:
            with _log_file_lock:
                with open(log_file_path, "a") as log_file:
                    log_file.write(error_message + "\n")
        return error_message
