#!/bin/bash
# Copyright 2026 Quentin Bordier, ETH Zurich.
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "${SCRIPT_DIR}/env.sh"

IMAGE_NAME="toooba-build"

# Build context is docker/ (toooba customizations live in docker/toooba/)
docker build \
  --network host \
  --build-arg HARTATTACK_CORES="${HARTATTACK_CORES}" \
  --build-arg USER_ID="$(id -u)" \
  --build-arg GROUP_ID="$(id -g)" \
  -f "$WORKDIR"/docker/Dockerfile.toooba \
  -t "$IMAGE_NAME" \
  "$WORKDIR"/docker

# Extract simulator binaries from the image
echo "Extracting simulator binaries..."
container_id=$(docker create "$IMAGE_NAME")

mkdir -p "${HARTATTACK_SIMULATORS_DIR}/toooba-2core"
mkdir -p "${HARTATTACK_SIMULATORS_DIR}/toooba-3core"
docker cp "$container_id":/output/toooba-2core/. "${HARTATTACK_SIMULATORS_DIR}/toooba-2core"/
docker cp "$container_id":/output/toooba-3core/. "${HARTATTACK_SIMULATORS_DIR}/toooba-3core"/

docker rm "$container_id" > /dev/null

echo "Simulators extracted to ${HARTATTACK_SIMULATORS_DIR}"
echo "  - toooba-2core/ (exe_HW_sim + elf_to_hex + cfg.json)"
echo "  - toooba-3core/ (exe_HW_sim + elf_to_hex + cfg.json)"
