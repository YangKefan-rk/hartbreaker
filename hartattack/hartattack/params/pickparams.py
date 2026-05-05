

from ..riscv import ExceptionCause
from ..instgen import ISAInstrClass
from .config_loader import get_instruction_weights, get_exception_weights

# Load configuration from TOML file
# These can be overridden by setting the HARTATTACK_CONFIG environment variable
# to point to a custom configuration file

ISAINSTRCLASS_INITIAL_BOOSTERS = get_instruction_weights()
EXCEPTION_OP_TYPE_INITIAL_BOOSTERS = get_exception_weights()
