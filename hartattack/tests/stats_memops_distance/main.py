

from hartattack.instgen import ISAInstrClass
import hartattack.runparams as rp
from hartattack.proggen import TestCaseGenerator
from hartattack.fuzzfromdescriptor import gen_new_test_instance
from hartattack.instgen import (
    IntStoreInstr,
    IntLoadInstr,
    FloatStoreInstr,
    FloatLoadInstr,
    PlaceholderProducerInstr0,
    PlaceholderProducerInstr1,
    PlaceholderConsumerInstr,
    PlaceholderPreConsumerInstr,
)
import matplotlib.pyplot as plt
from typing import TYPE_CHECKING, Optional
from tqdm import tqdm
import multiprocessing as mp
import signal
import os
import sys

if TYPE_CHECKING:
    from hartattack.params import TestParams
    from hartattack.instgen import RVInstr

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


class MemopDistStats:
    def __init__(self) -> None:
        self.all_distances: list[int] = []
        # Each program store the memop count per step, per hart
        self.memop_count: list[int] = []
        self.num_instr: list[int] = []
        self.num_prod: list[int] = []

    def average_distance(self):
        if not self.all_distances:
            return 0
        return sum(self.all_distances) / len(self.all_distances)

    def std_distance(self):
        if not self.all_distances:
            return 0
        mean = self.average_distance()
        variance = sum((x - mean) ** 2 for x in self.all_distances) / len(
            self.all_distances
        )
        return variance**0.5

    def get_distance_probabilities(self):
        """Calculate the probability of each distance value."""
        if not self.all_distances:
            return {}, []

        # Count occurrences of each distance
        distance_counts = {}
        for dist in self.all_distances:
            distance_counts[dist] = distance_counts.get(dist, 0) + 1

        # Convert to probabilities
        total = len(self.all_distances)
        distance_probs = {
            dist: count / total for dist, count in distance_counts.items()
        }

        # Sort by distance for plotting
        sorted_distances = sorted(distance_probs.keys())
        sorted_probs = [distance_probs[d] for d in sorted_distances]

        return sorted_distances, sorted_probs


def _gen_elf_worker_wrapper(test_params: "TestParams"):
    """Generates an ELF and computes the distance between all its memory
    operations. Returns results instead of using shared variables.
    """

    def get_num_prod(bbs: list[list["RVInstr"]]):
        PLACEHOLDERS = (
            PlaceholderProducerInstr0,
            PlaceholderProducerInstr1,
            PlaceholderConsumerInstr,
            PlaceholderPreConsumerInstr,
        )
        ret = 0
        for bb_instr in bbs:
            for instr in bb_instr:
                if isinstance(instr, PLACEHOLDERS):
                    ret += 1
        return ret

    def get_stats(
        first_memop_coord: tuple[int, int],
        last_memop_coord: tuple[int, int],
        bbs: list[list["RVInstr"]],
    ):
        MEMOPS = (IntStoreInstr, IntLoadInstr, FloatStoreInstr, FloatLoadInstr)
        curr_count = 0
        distances = []
        curr_distance: Optional[int] = None
        first_bb_idx, first_instr_idx = first_memop_coord
        last_bb_idx = last_memop_coord[0]
        for bb_idx in range(first_bb_idx, last_bb_idx + 1):
            bb_instrs = bbs[bb_idx]
            if bb_idx == first_bb_idx:
                start_instr_idx = first_instr_idx
            else:
                start_instr_idx = 0
            end_instr_idx = len(bb_instrs) - 1
            for instr_idx in range(start_instr_idx, end_instr_idx + 1):
                if curr_distance is not None:
                    curr_distance += 1
                if (bb_idx, instr_idx) == last_memop_coord:
                    return curr_count, distances
                if isinstance(bb_instrs[instr_idx], MEMOPS):
                    curr_count += 1
                    if curr_distance is not None:
                        distances.append(curr_distance)
                    curr_distance = 0
        assert False

    import signal as _sig

    def _timeout_handler(signum, frame):
        raise TimeoutError()

    all_counts: list[int] = []
    all_distances: list[int] = []
    test_params.prng.seed(test_params.randseed)

    _sig.signal(_sig.SIGALRM, _timeout_handler)
    _sig.alarm(10)  # 10s timeout
    try:
        testcase_generator = TestCaseGenerator(test_params)
        testcase_generator.gen_program(test_params)
    except (TimeoutError, Exception):
        _sig.alarm(0)
        return ([], [], 0, 0)
    _sig.alarm(0)

    # Count the distance between the memory operations of a step
    for step in testcase_generator.mcmstate.steps:
        for hartid, memop in step.step_memops.items():
            if len(memop) < 2:
                continue
            first_memop_coord = list(memop.keys())[0]
            last_memop_coord = list(memop.keys())[-1]
            instrs = testcase_generator.corestates[hartid].basic_blocks
            count, distances = get_stats(first_memop_coord, last_memop_coord, instrs)
            all_counts.append(count)
            all_distances += distances
    num_prod = 0
    for core in testcase_generator.corestates.values():
        num_prod += get_num_prod(core.basic_blocks)

    return (
        all_counts,
        all_distances,
        num_prod,
        testcase_generator.get_total_fuzzing_instrs(),
    )


def gen_many_elfs(design_name: str, num_cores: int, num_elfs: int):
    """Parallelize the ELF file generation, keeping num_cores workers always busy"""
    # Gen the program descriptors.
    test_params = [gen_new_test_instance(design_name, i, True) for i in range(num_elfs)]
    # Use normal generation method - no manual weight setting
    print(f"Starting ELF generation on {num_cores} processes.")

    all_memop_count = []
    all_instr_distance = []
    all_num_prod = []
    all_num_instr = []

    with mp.Pool(
        num_cores, initializer=signal.signal, initargs=(signal.SIGINT, signal.SIG_IGN)
    ) as pool:
        # Use imap_unordered to keep all workers busy until completion
        for memop_counts, distances, num_prod, num_instr in tqdm(
            pool.imap_unordered(_gen_elf_worker_wrapper, test_params),
            total=num_elfs,
            desc="Processing ELFs",
        ):
            all_memop_count.extend(memop_counts)
            all_instr_distance.extend(distances)
            all_num_prod.append(num_prod)
            all_num_instr.append(num_instr)

    stats = MemopDistStats()
    stats.memop_count = all_memop_count
    stats.all_distances = all_instr_distance
    stats.num_instr = all_num_instr
    stats.num_prod = all_num_prod
    return stats


def plot(stats: MemopDistStats):
    """Plot probability distribution of distances between memops."""
    distances, probabilities = stats.get_distance_probabilities()

    if not distances:
        print("No distances to plot!")
        return

    # Apply cutoff: only show distances with probability >= 0.1% (0.001)
    PROB_CUTOFF = 0.001
    filtered_data = [
        (d, p) for d, p in zip(distances, probabilities) if p >= PROB_CUTOFF
    ]

    if not filtered_data:
        print("No distances above cutoff threshold!")
        return

    filtered_distances, filtered_probabilities = zip(*filtered_data)
    num_filtered = len(distances) - len(filtered_distances)
    total_prob_filtered = sum(p for p in probabilities if p < PROB_CUTOFF)

    # Calculate median (50th percentile) from original data
    sorted_all_distances = sorted(stats.all_distances)
    median_distance = sorted_all_distances[len(sorted_all_distances) // 2]

    plt.figure(figsize=(3.5, 1.5))

    # Create bar plot
    plt.bar(filtered_distances, filtered_probabilities, color=colors[0])

    plt.xlabel("Memory Operations Distance (instructions)")
    plt.ylabel("Probability")
    plt.xlim(left=0)
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.join(script_dir, "memop_dist_probability.pdf")
    plt.savefig(pdf_path, format="pdf", dpi=300, bbox_inches="tight")
    print(f"Plot saved to {pdf_path}")


def main():
    if len(sys.argv) != 4:
        raise Exception("Usage: python3 main.py <design_name> <num_elfs> <num_cores>")
    design_name = str(sys.argv[1])
    num_elfs = int(sys.argv[2])
    num_cores = int(sys.argv[3])

    # Generate ELFs using normal generation method (no manual weight setting)
    stats = gen_many_elfs(design_name, num_cores, num_elfs)

    # Plot the probability distribution
    plot(stats)


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
