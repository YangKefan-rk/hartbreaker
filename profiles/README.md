# Four-hart Rocket generation profile

`simulators/quadrocket/cfg.json` describes the four Rocket harts and their ISA,
boot, and CLINT parameters. The simulator binary named in that file is **not**
part of this repository. For full RTL fuzzing, build the matching Chipyard
`QuadRocketDifftestSConfig` and install its simulator separately.

From the repository root, after installing HartBreaker and RISC-V toolchain
dependencies, use an output directory outside the source checkout:

```sh
source scripts/env.sh
export HARTATTACK_SIMULATORS_DIR="$PWD/simulators"
export HARTATTACK_CONFIG="$PWD/profiles/quadrocket-supported.toml"
export HARTATTACK_DATADIR=/absolute/path/to/hartbreaker-output
python3 hartattack/main.py quadrocket --gensingle 58000000 --num-cores 1 \
  --authorize-privileges False --num-bbs 32 --fuzz-mcm \
  --verify-memory-trace dat
python3 hartattack/main.py quadrocket --gensingle 59000000 --num-cores 1 \
  --authorize-privileges False --num-bbs 32
```

The Dat3M mode also requires a configured `DAT3M_HOME`. `--num-cores 1`
selects one **host generation worker**; the four target harts come from
`cfg.json`. The supported TOML differs from HartBreaker's default only by
setting the generated `EXCEPTION` weight to zero. These commands do not enable
`--fuzz-interrupts` or privileged-mode transitions. The supported profile does
not establish support for HartBreaker's unrestricted default generation, trap
or interrupt validation, nor does generating an ELF establish an RTL or
Difftest-S `Pass`.
