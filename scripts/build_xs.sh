#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "${SCRIPT_DIR}/env.sh"

IMAGE_NAME="xs-build"

# Build context is docker/ (xiangshan customizations live in docker/xiangshan/)
docker build \
  --network host \
  --build-arg HARTATTACK_CORES="${HARTATTACK_CORES}" \
  --build-arg USER_ID="$(id -u)" \
  --build-arg GROUP_ID="$(id -g)" \
  -f "$WORKDIR"/docker/Dockerfile.xs \
  -t "$IMAGE_NAME" \
  "$WORKDIR"/docker

# Extract simulator binaries from the image
echo "Extracting simulator binaries..."
container_id=$(docker create "$IMAGE_NAME")

mkdir -p "${HARTATTACK_SIMULATORS_DIR}/xiangshan"
docker cp "$container_id":/output/xiangshan/. "${HARTATTACK_SIMULATORS_DIR}/xiangshan"/

docker rm "$container_id" > /dev/null

echo "Simulators extracted to ${HARTATTACK_SIMULATORS_DIR}"
echo "  - xiangshan/ (emu + riscv64-nemu-interpreter-dual-so + cfg.json)"
