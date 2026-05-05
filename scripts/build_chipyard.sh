#!/bin/bash
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "${SCRIPT_DIR}/env.sh"

IMAGE_NAME="chipyard-build"

echo $WORKDIR

# Build context is docker/ (chipyard customizations live in docker/chipyard/)
docker build \
  --network host \
  --build-arg HARTATTACK_CORES="${HARTATTACK_CORES}" \
  --build-arg USER_ID="$(id -u)" \
  --build-arg GROUP_ID="$(id -g)" \
  -f "$WORKDIR"/docker/Dockerfile.chipyard \
  -t "$IMAGE_NAME" \
  "$WORKDIR"/docker

# Extract simulator binaries from the image
echo "Extracting simulator binaries..."
container_id=$(docker create "$IMAGE_NAME")

for design_dir in dualrocket dualboomv3 dualboomv4 tripplerocket trippleboomv3 trippleboomv4; do
  mkdir -p "${HARTATTACK_SIMULATORS_DIR}/${design_dir}"
  docker cp "$container_id":/output/"$design_dir"/. "${HARTATTACK_SIMULATORS_DIR}/${design_dir}"/
done

docker rm "$container_id" > /dev/null

echo "Simulators extracted to ${HARTATTACK_SIMULATORS_DIR}"
echo "  - dualrocket/"
echo "  - dualboomv3/"
echo "  - dualboomv4/"
echo "  - tripplerocket/"
echo "  - trippleboomv3/"
echo "  - trippleboomv4/"
