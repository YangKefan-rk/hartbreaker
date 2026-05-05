#!/bin/sh

# Check if we are inside a Docker container
if [ "$HARTATTACK_ENV_SOURCED" != "yes" ]; then
    echo "Running in docker container"
    ./scripts/run_docker.sh "$(realpath "$0")" "$@"
    exit 0
fi

##
# Design repositories TODO this should be local, and build using this docker
# image, locally !
##

echo "Cloning the repositories!"

##
# CHIPYARD
##

# Get the repo
cd "${DESIGN_DIR}" \
&& git clone https://github.com/ucb-bar/chipyard.git
# Init the repo submodules
cd "${DESIGN_DIR}"/chipyard \
&& git checkout HEAD \
&& scripts/init-submodules-no-riscv-tools.sh -f
# Make the stock rocket design
cd "${DESIGN_DIR}"/chipyard/sims/verilator \
&& make

# TODO MANUAL
# - add supervisor mode for rocket
# - add commitlogs for rocket and boom
# - making custom abstractconfigs which remove useless stuff like
#
# Modified files:
# ./chipyard/generators/rocket-chip/src/main/scala/rocket/Configs.scala
# ./chipyard/generators/chipyard/src/main/scala/config/BoomConfigs.scala
# ./chipyard/generators/boom/src/main/scala/v4/common/config-mixins.scala
# ./chipyard/generators/chipyard/src/main/scala/config/RocketConfigs.scala
# ./chipyard/generators/chipyard/src/main/scala/config/AbstractConfigCustom.scala
# ./chipyard/generators/rocket-chip/src/main/scala/tile/Core.scala
