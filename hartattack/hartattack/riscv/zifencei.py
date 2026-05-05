

from .rvprotoinstrs import *

ZIFENCEI_OPCODE_FENCEI = 0b0001111


# @return uint32_t
def zifencei_fencei(imm: int):
    return instruc_itype(ZIFENCEI_OPCODE_FENCEI, 0b0, 0b001, 0b0, imm)
