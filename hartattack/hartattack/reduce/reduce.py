# Copyright 2026 Flavien Solt, Quentin Bordier ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only
# from ..instgen import ISAInstrClass
from ..riscv import IntReg, ILEN, Ordering
from ..params import (
    RELOCATOR_REG,
    TERMSIG,
    SEMAPHORE_1,
    TOHOST_ADDR,
    CORESYNC_ADDR_REG,
)
from ..instgen import (
    ISAInstrClass,
    ImmRdInstr,
    RegImmInstr,
    IntStoreInstr,
    IntLoadInstr,
    JALInstr,
    RawDataWord,
    R12DInstr,
    BranchInstr,
    AmoInstr,
    WfiInstr,
)
from ..asm import li_into_reg
from ..genelf import gen_elf_from_bbs
from ..rtlsim import runtest_simulator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..states import CoreState, FuzzerState
    from ..proggen import TestCaseGenerator
    from ..params import TestParams


# Algorithm to reduce testcases that trigger non-termiantion, currently does not
# support:
# - Register mismatch bugs
# - Designs with more/less that 2 cores


def reduce_back(testcase_generator: "TestCaseGenerator", test_params: "TestParams"):
    print(f"Reducing {test_params.instance_to_str()}")

    fuzzerstate = testcase_generator.fuzzerstate
    fuzzerstate.final_bb_instrs = _gen_finalblock_noregdump(test_params, True)
    reduction_over = False
    while True:
        interrupt_point = [False] * test_params.num_harts
        for core_id, core in testcase_generator.corestates.items():
            while not interrupt_point[core_id]:
                # Remove the last block and save it
                prev_block = core.basic_blocks.pop()
                prev_block_startaddr = core.bb_start_addrs.pop()

                # Check if the current block waits or send an interrupt
                curr_bb_id = len(core.basic_blocks) - 1
                for bb_type, bb_id in core.interrupt_locs:
                    if curr_bb_id == bb_id:
                        print(bb_type)
                        if bb_type == ISAInstrClass.WFI_TRAP:
                            core.basic_blocks.append(prev_block)
                            core.bb_start_addrs.append(prev_block_startaddr)
                            interrupt_point[core_id] = True
                            break
                        elif bb_type == ISAInstrClass.SEND_INTERRUPT:
                            core.basic_blocks.append(prev_block)
                            core.bb_start_addrs.append(prev_block_startaddr)
                            interrupt_point[core_id] = True
                            break

                if not interrupt_point[core_id]:
                    # Connect thw new last block to the final block
                    _connect_testcase_to_fianlblock(core, fuzzerstate)
                    testcase_generator.prepare_testcase_for_rtl(test_params)
                    rtl_elfpath = gen_elf_from_bbs(
                        testcase_generator, False, "reduce", test_params
                    )
                    output = runtest_simulator(
                        testcase_generator,
                        test_params,
                        rtl_elfpath,
                    )
                    print("removed a block")
                    if output is not None:
                        print(f"reached first successful execution, stop reduction")
                        core.basic_blocks.append(prev_block)
                        core.bb_start_addrs.append(prev_block_startaddr)
                        testcase_generator.prepare_testcase_for_rtl(test_params)
                        rtl_elfpath = gen_elf_from_bbs(
                            testcase_generator, False, "reduced", test_params
                        )
                        print(f"Output elf in {rtl_elfpath}")
                        return

        # If both core form a send/wait pair, we pop both before continuing
        assert all(interrupt_point)
        for id, core in testcase_generator.corestates.items():
            print(f"pop block in core {id}")
            # We must remove the interrupt send/wait as well as the current
            # block, as we cannot afford to randomly trap
            prev_block1 = core.basic_blocks.pop()
            prev_block2 = core.basic_blocks.pop()
            prev_block_startaddr1 = core.bb_start_addrs.pop()
            prev_block_startaddr2 = core.bb_start_addrs.pop()
            _connect_testcase_to_fianlblock(core, fuzzerstate)
            output = runtest_simulator(
                testcase_generator,
                test_params,
                rtl_elfpath,
            )
            print("removed a block")
            if output is not None:
                print(output)
                print(f"reached first successful execution, stop reduction")
                core.basic_blocks.append(prev_block1)
                core.basic_blocks.append(prev_block2)
                core.bb_start_addrs.append(prev_block_startaddr1)
                core.bb_start_addrs.append(prev_block_startaddr2)
                testcase_generator.prepare_testcase_for_rtl(test_params)
                rtl_elfpath = gen_elf_from_bbs(
                    testcase_generator, False, "reduced", test_params
                )
                print(f"Output elf in {rtl_elfpath}")
                return
    pass


def _connect_testcase_to_fianlblock(corestate: "CoreState", fuzzerstate: "FuzzerState"):
    last_bb_addr = (
        corestate.bb_start_addrs[-1] + (len(corestate.basic_blocks[-1]) - 1) * ILEN
    )
    print(corestate.basic_blocks[-1][len(corestate.basic_blocks[-1]) - 1])
    final_bb_addr = fuzzerstate.get_final_bb_base_addr()
    imm = final_bb_addr - last_bb_addr
    corestate.basic_blocks[-1][-1] = JALInstr("jal", IntReg.zero, imm, is_absolute=True)


def _gen_finalblock_noregdump(test_params: "TestParams", is_rtl: bool):
    ret = []
    is_rv64 = test_params.is_rv64
    int_store = "sd" if is_rv64 else "sw"
    int_load = "ld" if is_rv64 else "lw"

    if test_params.num_harts > 1:
        offset = SEMAPHORE_1 - CORESYNC_ADDR_REG[1]
        ret.append(
            RegImmInstr("addi", IntReg.gp, CORESYNC_ADDR_REG[0], offset, is_rv64)
        )
        ret.append(RegImmInstr("addi", IntReg.ra, IntReg.zero, 1, is_rv64))
        ret.append(
            AmoInstr("amoadd.w", IntReg.sp, IntReg.gp, IntReg.ra, Ordering.Seq, None)
        )
        ret.append(IntLoadInstr(int_load, IntReg.sp, IntReg.gp, 0, None, is_rv64))
        ret.append(
            RegImmInstr("addi", IntReg.ra, IntReg.zero, test_params.num_harts, is_rv64)
        )
        ret.append(BranchInstr("beq", IntReg.ra, IntReg.sp, 3 * ILEN, True, is_rv64))
        # write and wait for non polling cores
        ret.append(WfiInstr())
        ret.append(JALInstr("jal", IntReg.zero, -ILEN))

    if is_rtl:
        _gen_termination_sequence(test_params.design_name, ret, int_store, is_rv64)
    else:
        _gen_termination_sequence("spike", ret, int_store, is_rv64)

    return ret


def _gen_termination_sequence(
    design_name: str, ret: list, int_store: str, is_rv64: bool
):
    match design_name:
        case "cheshire":
            lui_imm, _ = li_into_reg(0x3000000)  # cheshire scratch reg number 2
            ret.append(ImmRdInstr("lui", IntReg.ra, lui_imm, is_rv64))
            ret.append(RegImmInstr("addi", IntReg.sp, IntReg.zero, TERMSIG, is_rv64))
            ret.append(IntStoreInstr(int_store, IntReg.ra, IntReg.sp, 8, None, is_rv64))
            ret.append(JALInstr("jal", IntReg.zero, 0))  # Loop until term
        case "xiangshan":
            ret.append(ImmRdInstr("lui", IntReg.a0, 0, is_rv64))
            ret.append(RawDataWord(0x0005006B))  # xstrap rs0(a0)
            ret.append(JALInstr("jal", IntReg.zero, 0))
        case _:
            offset_val = TOHOST_ADDR - RELOCATOR_REG[1]
            lui_imm, _ = li_into_reg(offset_val)
            ret.append(ImmRdInstr("lui", IntReg.ra, lui_imm, is_rv64))
            ret.append(R12DInstr("add", IntReg.ra, IntReg.ra, RELOCATOR_REG[0]))
            ret.append(RegImmInstr("addi", IntReg.sp, IntReg.zero, TERMSIG, is_rv64))
            ret.append(IntStoreInstr(int_store, IntReg.ra, IntReg.sp, 0, None, is_rv64))
            ret.append(JALInstr("jal", IntReg.zero, -ILEN))  # Loop back to store tohost
