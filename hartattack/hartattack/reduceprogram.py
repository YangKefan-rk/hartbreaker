# Copyright 2026 Flavien Solt, Quentin Bordier ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only


from .reduce import reduce_back
from .fuzzfromdescriptor import (
    gen_new_test_instance,
    gen_fuzzerstate_elf_expectedvals,
)


class ReduceProgram:
    def __init__(
        self,
        design_name: str,
        prng_seed: int,
        can_authorize_privileges: bool,
    ):
        self.design_name = design_name
        self.prng_seed = prng_seed
        self.can_authorize_privileges = can_authorize_privileges

    def reduce_testcase(self):
        "Initializes the testcase to reduce, reduce the back and then the front"
        self._gen_test_params()
        self._gen_testcase_states()
        self._reduce_back()
        pass

    def _gen_test_params(self):
        "Returns the test params for the desired testcase instance"
        self.test_params = gen_new_test_instance(
            self.design_name, self.prng_seed, self.can_authorize_privileges
        )

    def _gen_testcase_states(self):
        "Generates the states for the testcase"
        self.testcase_generator = gen_fuzzerstate_elf_expectedvals(self.test_params)

    def _reduce_back(self):
        reduce_back(self.testcase_generator, self.test_params)
