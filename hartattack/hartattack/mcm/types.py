

from typing import Tuple

HartId = int
Addr = int
InstrCoord = Tuple[int, int]
StepRange = Tuple[int, int]
MemOrdering = list[InstrCoord]
PoIdx = int
Node = tuple[HartId, PoIdx]
