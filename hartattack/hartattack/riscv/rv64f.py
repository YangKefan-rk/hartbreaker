

from .rvprotoinstrs import *

RV64F_OPCODE_FCVT = 0b1010011

# All functions return uint32_t


def rv64f_fcvtls(rd: int, rs1: int, rm: int):
    return instruc_rtype(RV64F_OPCODE_FCVT, rd, rm, rs1, 0b00010, 0b1100000)


def rv64f_fcvtlus(rd: int, rs1: int, rm: int):
    return instruc_rtype(RV64F_OPCODE_FCVT, rd, rm, rs1, 0b00011, 0b1100000)


def rv64f_fcvtsl(rd: int, rs1: int, rm: int):
    return instruc_rtype(RV64F_OPCODE_FCVT, rd, rm, rs1, 0b00010, 0b1101000)


def rv64f_fcvtslu(rd: int, rs1: int, rm: int):
    return instruc_rtype(RV64F_OPCODE_FCVT, rd, rm, rs1, 0b00011, 0b1101000)
