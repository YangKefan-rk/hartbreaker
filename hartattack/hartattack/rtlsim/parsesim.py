# Copyright 2026 Flavien Solt, Quentin Bordier ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only


from typing import TYPE_CHECKING
import re
from ..params import (
    MAX_NUM_PICKABLE_INTREGS,
    MAX_NUM_PICKABLE_FLOATREGS,
    get_designparams,
)
from ..riscv import FpuState, IntReg, FloatReg
from ..states import IntRegState

if TYPE_CHECKING:
    from states import CoreState
    from mcm import MCMState
    from ..proggen import TestCaseGenerator
    from ..params import TestParams
import os

"""
To parse the simulation output, I always rely on the fact that instructions
writing to register 30 is always for dumping register content, except the first
2 instructions of the initial basic block, which initializes this register.

Similarly, we use register 29 to dump fpu reg vals

This is a sound assumption for the moment, as RDEP_MASK_REG[0] is reserved already,
so it will never be used as a destination register.
"""


def check_regs(
    received_regvals: tuple[dict[int, list[int]], dict[int, list[int]]],
    testcase_generator: "TestCaseGenerator",
    test_params: "TestParams",
    expected_regvals: tuple[dict[int, list[int]], dict[int, list[int]]],
):
    """
    Parse the output of the simulator and checks that the register values match
    our expections from the spike run
    """
    expected_intregvals, expected_floatregvals = expected_regvals
    received_intregvals, received_floatregvals = received_regvals

    reg_mismatch: list[str] = []
    # Compare the expected vs. received registers
    for hartid, core in testcase_generator.corestates.items():
        intregs = list(IntReg)[:MAX_NUM_PICKABLE_INTREGS]
        floatregs = list(FloatReg)
        for reg in intregs:
            if core.intregpickstate.get_regstate(
                reg, allow_nonpickable=True
            ) != IntRegState.FREE or (
                "xiangshan" in test_params.design_name and reg == IntReg.a0
            ):
                continue
            expected_val = expected_intregvals[hartid][reg.value]
            received_val = received_intregvals[hartid][reg.value]
            if expected_val != received_val:
                err_str = "Register mismatch core {} (x{}) for params: {}\n State: {}. Expected {}, got {}".format(
                    hartid,
                    reg.value,
                    test_params.instance_to_str(),
                    core.intregpickstate.get_regstate(reg, allow_nonpickable=True),
                    hex(expected_val),
                    hex(received_val),
                )
                reg_mismatch.append(err_str)

        if core.hartstate.mstatus_fs != FpuState.Off:
            for freg in floatregs:
                expected_val = expected_floatregvals[hartid][freg.value]
                received_val = received_floatregvals[hartid][freg.value]
                if expected_val != received_val:
                    err_str = "Register mismatch core {} (f{}) for params: {}. Expected {}, got {}".format(
                        hartid,
                        freg.value,
                        test_params.instance_to_str(),
                        hex(expected_val),
                        hex(received_val),
                    )
                    reg_mismatch.append(err_str)

    return reg_mismatch


def parse_sim_output(
    design_name: str,
    sim_output: str,
    corestates: dict[int, "CoreState"],
    mcmstate: "MCMState",
) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    """Given the design name, parse the verilator simulation output"""
    sim_output_l = sim_output.split("\n")
    allregdump = ({}, {})  # int_reg_dump, fp_reg_dump
    if "boomrocket" in design_name:
        allregdump = parse_boomrocket(sim_output_l, corestates, mcmstate)
    elif "rocket" in design_name:
        allregdump = parse_rocket_out(sim_output_l, corestates, mcmstate)
    elif "boom" in design_name:
        allregdump = parse_boom_out(sim_output_l, corestates, mcmstate)
    elif "cheshire" in design_name:
        allregdump = parse_cheshire(sim_output_l, corestates)
    elif "xiangshan" in design_name:
        allregdump = parse_xiangshan(sim_output_l, corestates)
    elif "toooba" in design_name:
        allregdump = parse_toooba(sim_output_l, corestates, mcmstate)
    elif "naxriscv" in design_name:
        allregdump = parse_naxriscv(sim_output_l, corestates, mcmstate)
    elif "vexiiriscv" in design_name:
        allregdump = parse_naxriscv(sim_output_l, corestates, mcmstate)
    else:
        raise ValueError(f"Design {design_name} not supported")

    return allregdump


def parse_naxriscv(
    sim_output: list[str], corestates: dict[int, "CoreState"], mcmstate: "MCMState"
) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    """
    Parse the output of the naxriscv core simulation"""

    load_pcs = mcmstate.get_all_load_addrs()
    int_reg_dump: dict[int, list[int]] = {}
    float_reg_dump: dict[int, list[int]] = {}
    int_parsing_done: dict[int, bool] = {}
    float_parsing_done: dict[int, bool] = {}
    for hartid in corestates.keys():
        int_reg_dump[hartid] = []
        float_reg_dump[hartid] = []
        int_parsing_done[hartid] = False
        if corestates[hartid].hartstate.mstatus_fs != FpuState.Off:
            float_parsing_done[hartid] = False
        else:
            float_parsing_done[hartid] = True

    for commit_idx, commit in enumerate(sim_output):
        # Currently, we do not check final regvals on naxriscv
        _intreg_done = all(int_parsing_done.values())
        _float_done = all(float_parsing_done.values())

        # Match PC from 'rv commit' lines: rv commit $hartid $pc_hex
        commit_match = re.match(r"rv commit (\d+) ([0-9a-fA-F]+)", commit)
        if commit_match:
            hartid = int(commit_match.group(1))
            pc_val = int(commit_match.group(2), 16)
            if pc_val in load_pcs:
                # Search upwards for rv load com <hartid> <commit_id>
                load_com_idx = None
                load_commit_id = None
                for prev_idx in range(commit_idx - 1, -1, -1):
                    prev_line = sim_output[prev_idx]
                    load_com_match = re.match(r"rv load com (\d+) (\d+)", prev_line)
                    if load_com_match is None:
                        continue
                    is_right_hartid = int(load_com_match.group(1)) == hartid
                    if is_right_hartid:
                        load_com_idx = prev_idx
                        load_commit_id = int(load_com_match.group(2))
                        break
                assert load_com_idx is not None, (
                    f"No rv load com found for commit at idx {commit_idx}"
                )
                # Search upwards for rv load exe <hartid> <same commit_id>
                load_exe_val = None
                for exe_idx in range(load_com_idx - 1, -1, -1):
                    exe_line = sim_output[exe_idx]
                    load_exe_match = re.match(
                        r"rv load exe (\d+) (\d+) \d+ ([0-9a-fA-F]+) ([0-9a-fA-F]+)",
                        exe_line,
                    )
                    if load_exe_match is None:
                        continue
                    is_right_hartid = int(load_exe_match.group(1)) == hartid
                    is_right_commitid = int(load_exe_match.group(2)) == load_commit_id
                    if is_right_hartid and is_right_commitid:
                        # The last hex value is the loaded value
                        groups = load_exe_match.groups()
                        load_exe_val = int(groups[-1], 16)
                        break
                assert load_exe_val is not None, (
                    f"No rv load exe found for rv load com at idx {load_com_idx}"
                )
                mcmstate.outcome[pc_val] = load_exe_val

    return int_reg_dump, float_reg_dump


def parse_toooba(
    sim_output: list[str], corestates: dict[int, "CoreState"], mcmstate: "MCMState"
) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    """
    Parse the output of the toooba core simulation"""

    load_pcs = mcmstate.get_all_load_addrs()
    int_reg_dump: dict[int, list[int]] = {}
    float_reg_dump: dict[int, list[int]] = {}
    int_parsing_done: dict[int, bool] = {}
    float_parsing_done: dict[int, bool] = {}
    for hartid in corestates.keys():
        int_reg_dump[hartid] = []
        float_reg_dump[hartid] = []
        int_parsing_done[hartid] = False
        if corestates[hartid].hartstate.mstatus_fs != FpuState.Off:
            float_parsing_done[hartid] = False
        else:
            float_parsing_done[hartid] = True

    for commit in reversed(sim_output):
        intreg_done = all(int_parsing_done.values())
        float_done = all(float_parsing_done.values())

        pc_match = re.search(r"PC:0x([0-9a-fA-F]+)", commit)
        if pc_match:
            pc_val = int(pc_match.group(1), 16)
            if pc_val in load_pcs:
                output = re.search(r"wb:0x([0-9a-fA-F]+)", commit)
                assert output
                output_val = int(output.group(1), 16)
                mcmstate.outcome[pc_val] = output_val

        if not intreg_done:
            is_rd_vals = re.findall(r"instr:0x0([0-1][0-9a-f])00f33", commit)
            if is_rd_vals:
                # Try to match the hex value after 'wb:0x'
                wb_match = re.search(r"wb:0x([0-9a-fA-F]+)", commit)
                if wb_match:
                    rd_vals = [wb_match.group(1)]
        if not float_done:
            # Match FPU register dump instruction pattern or wb: hex value
            is_frd_vals = re.findall(r"instr:0xe20[0-9a-f][08]ed3", commit)
            if is_frd_vals:
                # Try to match the hex value after 'wb:0x'
                wb_match = re.search(r"wb:0x([0-9a-fA-F]+)", commit)
                if wb_match:
                    frd_vals = [wb_match.group(1)]

        if not intreg_done and is_rd_vals:
            hartid = re.search(r"core:? (\d+):?", commit)
            assert hartid
            hartid = int(hartid.group(1), 16)
            if not int_parsing_done[hartid]:
                rd_val = int(rd_vals[0], 16)
                int_reg_dump[hartid].insert(0, rd_val)
                if len(int_reg_dump[hartid]) == MAX_NUM_PICKABLE_INTREGS:
                    int_parsing_done[hartid] = True

        if not float_done and is_frd_vals:
            hartid = re.search(r"core:? (\d+):?", commit)
            assert hartid
            hartid = int(hartid.group(1), 16)
            if not float_parsing_done[hartid]:
                frd_val = int(frd_vals[0], 16)
                float_reg_dump[hartid].insert(0, frd_val)
                if len(float_reg_dump[hartid]) == MAX_NUM_PICKABLE_FLOATREGS:
                    float_parsing_done[hartid] = True

    return int_reg_dump, float_reg_dump


def parse_boomrocket(
    sim_output: list[str], corestates: dict[int, "CoreState"], mcmstate: "MCMState"
) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    boom_intregs, boom_floatregs = parse_boom_out(sim_output, corestates, mcmstate)
    rocket_intregs, rocket_floatregs = parse_rocket_out(
        sim_output, corestates, mcmstate
    )

    int_reg_dump = {0: rocket_intregs[0], 1: boom_intregs[1]}
    float_reg_dump = {0: rocket_floatregs[0], 1: boom_floatregs[1]}

    return int_reg_dump, float_reg_dump


def parse_rocket_out(
    sim_output: list[str], corestates: dict[int, "CoreState"], mcmstate: "MCMState"
) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    """
    Parse the output of the rocket core simulation which has the following
    format:

    C"hartid": "time" ["valid"] pc=["pc"] W["rd"="val"]["wrenx"] R["rs1"="val"]
    R["rs2"="val"] inst=["ins"] DASM("ins")

    We start iterating at the bottom of the list and break when the desired
    number of registers is found

    Parameters:
        num_int_regs (int): Number of integer registers dumped
        num_fp_regs (int): Number of floating point registers dumped
        sim_output (list[str]): List of strings containing the rocket core
            simulation output

    Returns:
        tuple[list, list]: Tuple containing the integer register dump and the
            floating point register dump
    """

    load_pcs = mcmstate.get_all_load_addrs()
    int_reg_dump: dict[int, list[int]] = {}
    float_reg_dump: dict[int, list[int]] = {}
    int_parsing_done: dict[int, bool] = {}
    float_parsing_done: dict[int, bool] = {}
    for hartid in corestates.keys():
        int_reg_dump[hartid] = []
        float_reg_dump[hartid] = []
        int_parsing_done[hartid] = False
        if corestates[hartid].hartstate.mstatus_fs != FpuState.Off:
            float_parsing_done[hartid] = False
        else:
            float_parsing_done[hartid] = True

    for commit in reversed(sim_output):
        intreg_done = all(int_parsing_done.values())
        float_done = all(float_parsing_done.values())

        pc_match = re.search(r"pc=\[([0-9a-fA-F]+)\]", commit)
        if pc_match:
            pc_val = int(pc_match.group(1), 16)
            if pc_val in load_pcs:
                output = re.search(r"W\[r\s*[0-9]+=([0-9a-fA-F]+)\]", commit)
                assert output
                output_val = int(output.group(1), 16)
                mcmstate.outcome[pc_val] = output_val

        if not intreg_done:
            rd_vals = re.findall(r"W\[r30=([0-9a-fA-F]+)\]", commit)
        if not float_done:
            frd_vals = re.findall(r"W\[r29=([0-9a-fA-F]+)\]", commit)

        if not intreg_done and rd_vals:
            hartid = re.match(r"C(\d+):", commit)
            assert hartid
            hartid = int(hartid.group(1), 16)
            if hartid not in corestates.keys():
                continue  # skip stress core
            if not int_parsing_done[hartid]:
                rd_val = int(rd_vals[0], 16)
                int_reg_dump[hartid].insert(0, rd_val)
                if len(int_reg_dump[hartid]) == MAX_NUM_PICKABLE_INTREGS:
                    int_parsing_done[hartid] = True

        if not float_done and frd_vals:
            hartid = re.match(r"C(\d+):", commit)
            assert hartid
            hartid = int(hartid.group(1), 16)
            if hartid not in corestates.keys():
                continue  # skip stress core
            if not float_parsing_done[hartid]:
                frd_val = int(frd_vals[0], 16)
                float_reg_dump[hartid].insert(0, frd_val)
                if len(float_reg_dump[hartid]) == MAX_NUM_PICKABLE_FLOATREGS:
                    float_parsing_done[hartid] = True

    return int_reg_dump, float_reg_dump


def parse_boom_out(
    sim_output: list[str], corestates: dict[int, "CoreState"], mcmstate: "MCMState"
) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    """
    Parse the output of the rocket core simulation which has the following format:

    C"hartid": "time" ["valid"] pc=["pc"] W["rd"="val"]["wrenx"] R["rs1"="val"]
    R["rs2"="val"] inst=["ins"] DASM("ins")

    We start iterating at the bottom of the list and break when the desired
    number of registers is found

    Parameters:
        num_int_regs (int): Number of integer registers dumped
        num_fp_regs (int): Number of floating point registers dumped
        sim_output (list[str]): List of strings containing the rocket core
            simulation output

    Returns:
        tuple[list, list]: Tuple containing the integer register dump and the
            floating point register dump
    """

    load_pcs = mcmstate.get_all_load_addrs()
    int_reg_dump: dict[int, list[int]] = {}
    float_reg_dump: dict[int, list[int]] = {}
    int_parsing_done: dict[int, bool] = {}
    float_parsing_done: dict[int, bool] = {}
    for hartid in corestates.keys():
        int_reg_dump[hartid] = []
        float_reg_dump[hartid] = []
        int_parsing_done[hartid] = False
        if corestates[hartid].hartstate.mstatus_fs != FpuState.Off:
            float_parsing_done[hartid] = False
        else:
            float_parsing_done[hartid] = True

    for commit in reversed(sim_output):
        intreg_done = all(int_parsing_done.values())
        float_done = all(float_parsing_done.values())

        # Extract PC: first hex number after 'core N:'
        pc_match = re.match(r"core \d+: \d+ (0x[0-9a-fA-F]+)", commit)
        if pc_match:
            pc_val = int(pc_match.group(1), 16)
            if pc_val in load_pcs:
                output = re.search(r"[fx]\s*\d+\s(0x[0-9a-fA-F]+)", commit)
                assert output
                output_val = int(output.group(1), 16)
                mcmstate.outcome[pc_val] = output_val

        if not intreg_done:
            match_int = re.match(r"core (\d+): .* x30 (0x[0-9a-fA-F]+)", commit)
        if not float_done:
            match_float = re.match(r"core (\d+): .* x29 (0x[0-9a-fA-F]+)", commit)

        if not intreg_done and match_int:
            hartid = int(match_int.group(1))
            rd_val = int(match_int.group(2), 16)
            if not int_parsing_done[hartid]:
                int_reg_dump[hartid].insert(0, rd_val)
                if len(int_reg_dump[hartid]) == MAX_NUM_PICKABLE_INTREGS:
                    int_parsing_done[hartid] = True

        if not float_done and match_float:
            hartid = int(match_float.group(1))
            frd_val = int(match_float.group(2), 16)
            if not float_parsing_done[hartid]:
                float_reg_dump[hartid].insert(0, frd_val)
                if len(float_reg_dump[hartid]) == MAX_NUM_PICKABLE_FLOATREGS:
                    float_parsing_done[hartid] = True

    return int_reg_dump, float_reg_dump


def parse_cheshire(
    sim_output: list[str],
    corestates: dict[int, "CoreState"],
) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    """
    Parse the output of the cheshire core simulation which has the following format:

    each core has a log file:
    3 0x000000000200001a (0x4801) x16 0x0000000000000000

    Parameters:
        num_int_regs (int): Number of integer registers dumped
        num_fp_regs (int): Number of floating point registers dumped
        sim_output (list[str]): List of strings containing the rocket core
            simulation output

    Returns:
        tuple[list, list]: Tuple containing the integer register dump and the
            floating point register dump
    """

    log_files = [
        re.match(r".* (trace_hart_(\d+)_commit_(\d+).log)", line)
        for line in sim_output
        if re.match(r".* trace_hart_(\d+)_commit_(\d+).log", line)
    ]

    int_reg_dump: dict[int, list[int]] = {}
    float_reg_dump: dict[int, list[int]] = {}
    design_sim_dir = get_designparams.get_design_simulator("cheshire")
    for log_file in log_files:
        assert log_file
        intreg_done = False
        flotreg_done = False
        hartid = int(log_file.group(2))
        int_reg_dump[hartid] = []
        float_reg_dump[hartid] = []
        if corestates[hartid].hartstate.mstatus_fs == FpuState.Off:
            flotreg_done = True
        commit_log_path = f"{design_sim_dir}/{log_file.group(1)}"

        with open(commit_log_path, "r") as log:
            for line in reversed(list(log)):
                match_int = re.match(r".* x30 (0x[0-9a-fA-F]+)", line)
                match_float = re.match(r".* x29 (0x[0-9a-fA-F]+)", line)

                if not intreg_done and match_int:
                    rd_val = int(match_int.group(1), 16)
                    int_reg_dump[hartid].insert(0, rd_val)
                    if len(int_reg_dump[hartid]) == MAX_NUM_PICKABLE_INTREGS:
                        intreg_done = True

                if not flotreg_done and match_float:
                    frd_val = int(match_float.group(1), 16)
                    float_reg_dump[hartid].insert(0, frd_val)
                    if len(float_reg_dump[hartid]) == MAX_NUM_PICKABLE_FLOATREGS:
                        flotreg_done = True

        os.remove(commit_log_path)
        log_file = f"trace_hart_{hartid}_{int(log_file.group(3))}.log"
        log_path = f"{design_sim_dir}/{log_file}"
        os.remove(log_path)

    return int_reg_dump, float_reg_dump


def parse_xiangshan(
    sim_output: list[str],
    corestates: dict[int, "CoreState"],
) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    int_reg_dump: dict[int, list[int]] = {}
    float_reg_dump: dict[int, list[int]] = {}
    curr_hartid = 0
    parse_floatreg = False
    parse_intreg = False
    for idx, line in enumerate(sim_output):
        match = re.match(r"Core (\d+): .*", line)
        if match:
            curr_hartid = int(match.group(1))
            int_reg_dump[curr_hartid] = []
            float_reg_dump[curr_hartid] = []
        elif "---- Intger Registers ------" in line:
            parse_intreg = True
        elif "---- Float Registers -----" in line:
            parse_floatreg = True
            parse_intreg = False
        elif "fcsr" in line:
            parse_floatreg = False
        elif parse_intreg:
            matches = re.findall(r"[a-z0-9]+: (0x[0-9a-fA-F]+)", line)
            int_reg_dump[curr_hartid].extend(int(match, 16) for match in matches)
        elif parse_floatreg:
            matches = re.findall(r"[a-z0-9]+: (0x[0-9a-fA-F]+)", line)
            float_reg_dump[curr_hartid].extend(int(match, 16) for match in matches)

    return int_reg_dump, float_reg_dump
