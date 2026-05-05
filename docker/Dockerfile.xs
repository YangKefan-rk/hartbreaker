FROM base:v1

ENV DEBIAN_FRONTEND=noninteractive

ARG HARTATTACK_CORES=16

# XiangShan-specific dependencies
RUN apt-get update && apt-get install -y \
time proxychains4 shadowsocks-libev llvm libreadline6-dev libsdl2-dev \
sqlite3 libsqlite3-dev zstd libzstd-dev \
&& rm -rf /var/lib/apt/lists/*

# Install mill (XiangShan build tool)
RUN sh -c "curl -L https://github.com/com-lihaoyi/mill/releases/download/0.12.5/0.12.5 > /usr/local/bin/mill && chmod +x /usr/local/bin/mill"

# Install Verilator v5.040 with clang (as required by xs-env)
RUN git clone https://github.com/verilator/verilator \
&& cd verilator \
&& git checkout v5.040 \
&& autoconf \
&& ./configure CC=clang CXX=clang++ LINK=clang++ \
&& make -j ${HARTATTACK_CORES} \
&& make install

# Clone xs-env at the exact commit used by this project
RUN git clone https://github.com/OpenXiangShan/xs-env.git /xs-env \
&& cd /xs-env \
&& git checkout 4faefd3a57632d71fbbff21a191a9dcba376d456

# Clone XiangShan and NEMU at the exact commits used by this project
RUN git clone https://github.com/OpenXiangShan/XiangShan.git /xs-env/XiangShan \
&& cd /xs-env/XiangShan \
&& git checkout 16ae9ddcda54fc9a2fddffad73174cf793ac7814 \
&& git submodule update --init --recursive

RUN git clone https://github.com/OpenXiangShan/NEMU.git /xs-env/NEMU \
&& cd /xs-env/NEMU \
&& git checkout 53bcb5686f8fd05248ae98546b7dc04bdca1bbb0

# Set xs-env environment variables
ENV NEMU_HOME=/xs-env/NEMU
ENV NOOP_HOME=/xs-env/XiangShan
ENV AM_HOME=/xs-env/nexus-am
ENV DRAMSIM3_HOME=/xs-env/DRAMsim3

# Apply NEMU patch and build the dual-core difftest shared object
COPY xiangshan/patches/NEMU.patch /tmp/NEMU.patch
RUN cd /xs-env/NEMU && git apply /tmp/NEMU.patch

RUN cd /xs-env/NEMU \
&& mkdir -p resource/gcpt_restore/src resource/gcpt_restore/build \
&& touch resource/gcpt_restore/src/restore_rom_addr.h \
&& touch resource/gcpt_restore/build/gcpt.bin \
&& make riscv64-dual-xs-ref_defconfig \
&& make -j ${HARTATTACK_CORES}

# Build the XiangShan emulator (dual-core)
WORKDIR /xs-env/XiangShan
RUN make emu CONFIG=DefaultConfig NUM_CORES=2 DISABLE_PERF=1 CXX=clang++ -j ${HARTATTACK_CORES}

# Copy cfg.json into the image
COPY xiangshan/cfg/ /tmp/cfg/

# Stage output binaries
RUN mkdir -p /output/xiangshan \
&& cp build/emu /output/xiangshan/ \
&& cp /xs-env/NEMU/build/riscv64-nemu-interpreter-so /output/xiangshan/riscv64-nemu-interpreter-dual-so \
&& cp /tmp/cfg/xiangshan.json /output/xiangshan/cfg.json
