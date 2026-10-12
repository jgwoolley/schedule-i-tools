# Downloads Schedule I with SteamCMD and extracts the pawn shop data used by public/index.html.
#
#   docker build -t pawn-extract .
#   docker run --rm -it -e STEAM_USER=<account that owns the game> \
#       -v schedule1-game:/game -v schedule1-steam:/root/Steam -v "$PWD/out:/out" pawn-extract
#
# See ../README.md for the other ways to run it. Not yet built or run anywhere.
FROM --platform=linux/amd64 ubuntu:24.04

ARG IL2CPPDUMPER_VERSION=6.7.46
ARG UNITYPY_VERSION=1.25.4

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates curl unzip binutils \
        python3 python3-venv \
        dotnet-runtime-8.0 \
        lib32gcc-s1 \
 && rm -rf /var/lib/apt/lists/*

# SteamCMD (32-bit binary, hence lib32gcc-s1)
RUN mkdir -p /opt/steamcmd \
 && curl -fsSL https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz | tar -xz -C /opt/steamcmd

# Il2CppDumper targets .NET 6; DOTNET_ROLL_FORWARD lets it run on the .NET 8 runtime
RUN curl -fsSL -o /tmp/i2d.zip \
        https://github.com/Perfare/Il2CppDumper/releases/download/v${IL2CPPDUMPER_VERSION}/Il2CppDumper-net6-v${IL2CPPDUMPER_VERSION}.zip \
 && unzip -q /tmp/i2d.zip -d /opt/il2cppdumper && rm /tmp/i2d.zip \
 && sed -i 's/"RequireAnyKey": true/"RequireAnyKey": false/' /opt/il2cppdumper/config.json
ENV DOTNET_ROLL_FORWARD=LatestMajor

RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir UnityPy==${UNITYPY_VERSION}

COPY disasm.py readfloat.py extract.py build_items.py run.sh /opt/pawn/
RUN chmod +x /opt/pawn/run.sh

VOLUME ["/game", "/out", "/root/Steam"]
ENTRYPOINT ["/opt/pawn/run.sh"]
