# Quick Start

## Using an existing design

1. Source the environment:

   ```bash
   source ./scripts/all.sh
   ```

2. List available designs:

   ```bash
   ls $HARTATTACK_SIMULATORS_DIR
   ```

3. Run a fuzzing campaign:

   ```bash
   python3 hartattack/main.py <design_name> --num-cores 4
   ```

4. Generate a single test ELF (useful for debugging):

   ```bash
   python3 hartattack/main.py <design_name> --gensingle 42
   ```

5. Fuzz a single seed (generate + simulate + compare):

   ```bash
   python3 hartattack/main.py <design_name> --fuzzsingle 42 --keep-tmpfiles
   ```

   Use `--keep-tmpfiles` to inspect the generated ELF and simulation outputs.

6. Disassemble a generated ELF:

   ```bash
   rvdump path/to/generated.elf
   ```

## Adding a new design

### Design requirements

A new design needs three things:

1. **Simulation termination** -- A way to stop simulation from the program (typically by writing to a `.tohost` register).
2. **Program loading** -- A way to load ELF programs into the simulator's memory.
3. **Commit trace output** -- A trace of committed instructions with register/memory values (particularly for memory operations).

The framework expects the design to use:
- The standard CLINT address of `0x2000000` (or a custom one specified in `cfg.json`)
- The standard `.tohost` register for simulation termination

### Step-by-step

#### 1. Create a simulator configuration

Add a directory under `simulators/` with your design name. Inside it, create a `cfg.json` following the format of existing designs. This file specifies the simulator binary, number of harts, CLINT address, and trace format.

#### 2. Register the simulator

In `params/test_params.py`, add your design to the `SimulatorEnum` class:

```python
class SimulatorEnum(Enum):
    # ...existing entries...
    MY_DESIGN = "my_design"
```

Then add a case in the design-name matching logic:

```python
case "my_design":
    self.simulator = SimulatorEnum.MY_DESIGN
```

#### 3. Add simulation and parsing support

In `rtlsim/fuzzsim.py`, add a function to invoke your simulator. The function should:
- Accept the ELF path and simulation parameters
- Launch the simulator binary (path read from `cfg.json`)
- Return the simulation output (commit log)

In `rtlsim/parsesim.py`, add a parser for your simulator's commit log format. The parser must extract:
- Final register values for each hart
- Memory store operations (address, value, size)
- Exception and interrupt events

#### 4. Handle non-standard configurations

If your design does not use the standard CLINT address, specify the correct address in `cfg.json`. The framework reads it from there and adapts the generated programs automatically.

To debug address differences between Spike and your RTL design, use the `--debug-rtl` flag to generate an ELF with Spike's device addresses. This lets you compare Spike and RTL execution of the same binary.

### Verifying your integration

1. Generate a test ELF and check it loads correctly:

   ```bash
   python3 hartattack/main.py my_design --gensingle 1 --keep-tmpfiles
   ```

2. Fuzz a single seed to verify the full pipeline:

   ```bash
   python3 hartattack/main.py my_design --fuzzsingle 1
   ```

3. Run a short fuzzing campaign:

   ```bash
   python3 hartattack/main.py my_design --num-cores 2
   ```
