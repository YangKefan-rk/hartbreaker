# Copyright 2026 Flavien Solt, Quentin Bordier ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only


# This script is responsible for running the RTL simulations from ..the fuzzer.

from typing import TYPE_CHECKING, Optional
from psutil import Process
import shutil
import tempfile
import os
import subprocess
import time
import uuid
from .. import runparams
from ..params import (
    EXTRA_TOHOST_INSTR,
    MAX_CYCLES_PER_INSTR,
    SETUP_CYCLES,
    get_designparams,
    SimulatorEnum,
)

if TYPE_CHECKING:
    from ..proggen import TestCaseGenerator
    from ..params import TestParams


# Runs the test and checks for matching.
# @param expected_regvals a pair of iterables of expected int regvals, and float
#  regvals.
# @param override_num_instrs if not None, then use this value instead of the
#  number of instructions in fuzzerstate.instr_objs_seq. Used when pruning to
#  shorten a bit the timeout.
# @return (is_success: bool, msg: str)
def runtest_simulator(
    testcase_generator: "TestCaseGenerator",
    test_params: "TestParams",
    elfpath: str,
    override_num_instrs: Optional[int] = None,
):
    num_instrs = (
        override_num_instrs
        if override_num_instrs
        else testcase_generator.get_total_fuzzing_instrs()
        + len(testcase_generator.fuzzerstate.init_bb_instrs)
    )
    match test_params.simulator:
        case SimulatorEnum.CHIPYARD:
            is_stop_successful, exec_out = _runsim_chipyard(
                test_params.design_name,
                # TODO need to account for state preserving loops
                (num_instrs + EXTRA_TOHOST_INSTR) * MAX_CYCLES_PER_INSTR + SETUP_CYCLES,
                elfpath,
            )
        case SimulatorEnum.CHESHIRE:
            is_stop_successful, exec_out = _runsim_cheshire(
                test_params.design_name,
                (num_instrs + EXTRA_TOHOST_INSTR) * MAX_CYCLES_PER_INSTR + SETUP_CYCLES,
                elfpath,
            )
        case SimulatorEnum.XIANGSHAN:
            is_stop_successful, exec_out = _runsim_xiangshan(
                test_params.design_name,
                num_instrs,
                elfpath,
            )
        case SimulatorEnum.TOOOBA:
            is_stop_successful, exec_out = _runsim_toooba(
                test_params.design_name,
                num_instrs,
                elfpath,
            )
        case SimulatorEnum.NAXRISCV:
            is_stop_successful, exec_out = _runsim_naxriscv(
                test_params.design_name,
                num_instrs,
                elfpath,
            )
        case SimulatorEnum.VEXIIRISCV:
            is_stop_successful, exec_out = _runsim_vexiiriscv(
                test_params.design_name,
                num_instrs,
                elfpath,
            )
        case _:
            raise NotImplementedError(f"Unknown simulator {test_params.simulator}")

    # Check successful stop and cause
    assert exec_out
    if not is_stop_successful:
        return False, exec_out
    return True, exec_out


def _runsim_naxriscv(
    design_name: str,
    simlen: int,
    elfpath: str,
):
    """
    WARNING naxriscv only works with some specific version of the tools, so
    we launch it in the dedicated docker container. Modifying that script may
    break stuff in weird ways.
    """
    if runparams.FUZZ_MCM:
        num_cores = 3  # FIXME naxriscv number of cores
    elif runparams.FUZZ_INTERRUPT:
        num_cores = 2
    else:
        raise NotImplementedError
    sim_args = (
        "--withFloat "
        "--withDouble "
        "--withRvc "
        "--xlen 64 "
        "--no-rvls "
        f"--nax-count {num_cores} "
        "--trace "
        "--pass-symbol pass "
    )
    # Inside the container, the elf is mounted at /elf/<basename>
    elf_basename = os.path.basename(elfpath)
    elf_container_path = f"/elf/{elf_basename}"
    elf_path = f"--load-elf {elf_container_path}"
    sim_paths = "--workspace-path /output --workspace-name . --workspace-output-dir logs "
    # Compose the command to run inside the container
    # chmod at the end so the host user can clean up the temp dir
    sbt_cmd = f'sbt -Dsbt.watch.mode=polling -Dsbt.io.implicit-unsafe-opt-in.required=true "runMain naxriscv.platform.tilelinkdemo.SocSim {sim_args} {sim_paths} {elf_path}"'
    script_or_command = f'{sbt_cmd}; chmod -R 777 /output' # make sure /output can be cleaned up

    # Run in a subprocess with --rm so the container is always cleaned up
    elf_dir = os.path.dirname(os.path.abspath(elfpath))
    elf_name = os.path.splitext(elf_basename)[0]

    # Use a temp dir under HARTATTACK_DATADIR so the path is valid on the
    # host (the naxriscv container is a sibling via the Docker socket, not
    # nested, so /tmp inside the run container is invisible to it).
    with tempfile.TemporaryDirectory(dir=os.environ.get("HARTATTACK_DATADIR", None)) as tmp_dir:
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{elf_dir}:/elf:Z",
            "-v", f"{tmp_dir}:/output:Z",
            "naxriscv:v1",
            "bash", "-c", script_or_command,
        ]

        timed_out = False
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=60 * 10,  # 10 minutes timeout
            )
            log_output = result.stdout + result.stderr
        except subprocess.TimeoutExpired as e:
            timed_out = True
            log_output = (e.stdout or b"").decode("utf-8", errors="replace") + (e.stderr or b"").decode("utf-8", errors="replace")

        if timed_out:
            return False, f"simulation timed out\n{log_output}"
        if "TEST PASS" not in log_output:
            return False, f"NO TEST PASS: {log_output}"

        # Read tracer.log from the mounted output (written by sbt inside container)
        tracer_path = os.path.join(tmp_dir, "logs", elf_name, "tracer.log")
        if os.path.exists(tracer_path):
            with open(tracer_path, "r") as f:
                return True, f.read()
        return False, f"tracer.log not found at {tracer_path}\ntmp_dir contents: \n{log_output}"

def _runsim_vexiiriscv(
    design_name: str,
    simlen: int,
    elfpath: str,
):
    """
    WARNING naxriscv onl;y works with some specific version of the tools, so
    we launch it in the dedicated docker container. Modifiying that script may
    break stuff in weird ways
    """
    design_simdir = get_designparams.get_design_simulator_dir(design_name)
    design_dir = os.environ.get("DESIGN_DIR")
    if design_dir is None:
        raise EnvironmentError("DESIGN_DIR environment variable is not set.")
    vex_dir = f"{design_dir}/VexiiRiscv"
    workdir = os.environ.get("WORKDIR")
    if workdir is None:
        raise EnvironmentError("WORKDIR environment variable is not set.")
    if runparams.FUZZ_MCM:
        num_cores = 3
    elif runparams.FUZZ_INTERRUPT:
        num_cores = 2
    else:
        raise NotImplementedError
    sim_args = (
        "--sim-peripheral "
        "--regfile-async "
        "--with-rvm "
        "--with-rva "
        "--with-rvc "
        "--with-rvd "
        "--allow-bypass-from=0 "
        "--performance-counters=0 "
        "--fetch-l1 "
        "--fetch-l1-ways=4 "
        "--lsu-l1 "
        "--lsu-l1-ways=4 "
        "--with-lsu-bypass "
        "--relaxed-branch "
        "--with-supervisor "
        "--fetch-l1-ways=4 "
        "--fetch-l1-mem-data-width-min=64 "
        "--lsu-l1-ways=4 "
        "--lsu-l1-mem-data-width-min=64 "
        "--xlen=64 "
        "--fma-reduced-accuracy "
        "--fpu-ignore-subnormal "
        "--with-btb "
        "--with-ras "
        "--with-gshare "
        "--fetch-l1-hardware-prefetch=nl "
        "--fetch-l1-refill-count=2 "
        "--fetch-l1-mem-data-width-min=128 "
        "--lsu-l1-mem-data-width-min=128 "
        "--lsu-software-prefetch "
        "--lsu-hardware-prefetch rpt "
        "--performance-counters 9 "
        "--lsu-l1-store-buffer-ops=32 "
        "--lsu-l1-refill-count 4 "
        "--lsu-l1-writeback-count 4 "
        "--lsu-l1-store-buffer-slots=4 "
        "--relaxed-div "
        "--reset-vector 2147483648 "
        "--l2-bytes=524288 "
        "--l2-ways=4 "
        "--litedram-width=128 "
        "--memory-region=268435456,131072,rwx,p "
        "--memory-region=2147483648,1073741824,rwxc,m "
        "--with-jtag-tap "
        "--lsu-l1-coherency "
        "--max-ipc "
        "--decoders=2 "
        "--lanes=2 "
        "--trace-rvls "
        "--trace-konata "
        "--trace-spike "
        "--trace-wave "
        "--reset-vector=0x80000000 "
        "--pass-symbol=pass "
    )
    sim_params = f"--cpu-count={num_cores} --load-elf {elfpath}"
    # Compose the command to run inside the container
    cmdline = f'sbt "runMain vexiiriscv.soc.litex.SocSim {sim_args} {sim_params}"'

    design_simdir = get_designparams.get_design_simulator_dir(design_name)
    sim_path = f"{design_simdir}/Soc/test"

    # Honor JAVA_HOME if the user set one (vexiiriscv historically needs JDK 8);
    # otherwise rely on the system Java already on PATH.
    env = os.environ.copy()
    java_home = env.get("JAVA_HOME")
    if java_home:
        env["PATH"] = f"{java_home}/bin:" + env["PATH"]

    # Run simulation
    exec_out = ""
    try:
        result = subprocess.run(
            cmdline,
            shell=True,
            text=True,
            capture_output=True,
            timeout=60 * 28,  # 28 minutes timeout
            env=env,
            cwd=vex_dir
        )
        exec_out = result.stdout
    except subprocess.TimeoutExpired:
        pass

    if "[success]" in exec_out:
        log_path = f"{vex_dir}/simWorkspace/Soc/test/tracer.log"
        with open(log_path, "r") as f:
            trace_contents = f.read()
        return True, trace_contents
    else:
        return False, f"failure"


def _runsim_toooba(
    design_name: str,
    simlen: int,
    elfpath: str,
):
    "run a toooba simulation."
    design_sim_bin = get_designparams.get_design_simulator(design_name)
    design_simdir = get_designparams.get_design_simulator_dir(design_name)

    # Create a temporary directory for this process
    with tempfile.TemporaryDirectory() as temp_dir:
        # Copy simulator and elf2hex binary in temporary directory
        temp_sim_bin = os.path.join(temp_dir, os.path.basename(design_sim_bin))
        shutil.copy2(design_sim_bin, temp_sim_bin)
        elf_to_hex_src = os.path.join(design_simdir, "elf_to_hex")
        elf_to_hex_dst = os.path.join(temp_dir, "elf_to_hex")
        shutil.copy2(elf_to_hex_src, elf_to_hex_dst)

        # Turn ELF in Mem.hex
        subprocess.run(
            [
                "./elf_to_hex",
                elfpath,
                "Mem.hex",
            ],
            text=True,
            capture_output=True,
            cwd=temp_dir,
        )

        # Run simulation
        timed_out = [False]
        try:
            exec_out = subprocess.run(
                [
                    "./{}".format(os.path.basename(design_sim_bin)),
                    "+v1",
                    "+tohost",
                ],
                text=True,
                capture_output=True,
                cwd=temp_dir,
                timeout=240,
            )
        except subprocess.TimeoutExpired:
            timed_out[0] = True

    if timed_out[0]:
        return False, "simulation timed out"
    if not "PASS" in exec_out.stdout:
        print(exec_out.stderr)
        return False, "something went wrong"
    return True, exec_out.stdout


def _runsim_chipyard(
    design_name,
    simlen,
    elfpath,
    coveragepath=None,
    get_rfuzz_coverage_mask=False,
):
    """Runs a simulation of a chipyard SoC"""
    if __debug__:
        assert coveragepath is None or not get_rfuzz_coverage_mask

    design_sim_bin = get_designparams.get_design_simulator(design_name)

    exec_out = subprocess.run(
        [
            design_sim_bin,
            elfpath,
            "+verbose",
            f"+max-cycles={simlen}",
            f"+loadmem={elfpath}",
        ],
        text=True,
        capture_output=True,
    )

    if not "*** PASSED ***" in exec_out.stderr:
        if "timeout" in exec_out.stderr:
            err_msg = "Reached max cycles"
        else:
            err_msg = exec_out.stdout
        return False, err_msg
    return True, exec_out.stderr


def _runsim_cheshire(
    design_name: str,
    simlen: int,
    elfpath: str,
):
    """Runs a simulation of the cheshire SoC"""
    design_sim_dir = get_designparams.get_design_simulator(design_name)
    cmdline = ["vsim", "-c", "-do", "run.tcl"]
    env = os.environ.copy()
    host_core_id = Process().cpu_num()
    env.update(
        {
            "BOOTMODE": str(0),
            "PRELMODE": str(3),
            "BINARY": elfpath,
            "CHESHIRE_UID": str(host_core_id),
        }
    )

    # We expect the simulation to take at most 4*simlen + 20 seconds.
    exec_out = subprocess.run(
        cmdline,
        cwd=design_sim_dir,
        env=env,
        check=False,
        text=True,
        capture_output=True,
        timeout=min(4 * simlen + 20, 1800),
    ).stdout

    if not "SUCCESS" in exec_out:
        return False, None
    return True, exec_out


def _runsim_xiangshan(
    design_name: str,
    numinstr: int,
    elfpath: str,
):
    """Runs a simulation of the XiangShan SoC"""
    design_sim_bin = get_designparams.get_design_simulator(design_name)
    design_simdir = get_designparams.get_design_simulator_dir(design_name)
    cmdline = f"{design_sim_bin} -i {elfpath} --diff={design_simdir}/riscv64-nemu-interpreter-dual-so --ram-size=4MB"

    # Run simulation
    timed_out = [False]
    exec_out = ""
    start = time.time()
    try:
        result = subprocess.run(
            cmdline,
            shell=True,
            check=True,
            capture_output=True,
            timeout=60 * 90,  # 45 minutes timeout
        ).stdout
        exec_out = result.decode("utf-8")
    except subprocess.TimeoutExpired:
        timed_out[0] = True

    if timed_out[0] == True:
        return False, f"timed out after {time.time() - start} seconds"
    elif "ERROR" in exec_out or not "HIT GOOD TRAP" in exec_out or "ABORT" in exec_out:
        return False, "error happend"
    else:
        return True, exec_out
