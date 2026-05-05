#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "${SCRIPT_DIR}/env.sh"

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <design_name>"
    exit 1
fi

design_name="$1"

# Build the Docker container
docker build\
 --network host\
 --build-arg HARTATTACK_CORES="$HARTATTACK_CORES"\
 --build-arg USER_ID="$(id -u)"\
 --build-arg GROUP_ID="$(id -g)"\
 --build-arg WORKDIR="$WORKDIR"\
 -f "$WORKDIR"/docker/Dockerfile."$design_name" \
 -t "$design_name":v1\
 "$WORKDIR"/docker

echo "Docker container built successfully."
