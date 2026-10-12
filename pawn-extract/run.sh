#!/bin/sh
# Entrypoint: optionally download the game with SteamCMD, then extract the pawn shop data to $OUT.
set -eu

GAME=${GAME:-/game}
OUT=${OUT:-/out}
WORK=${WORK:-/tmp/pawn-work}
APP_ID=${APP_ID:-3164500}                 # Schedule I
BRANCH=${BRANCH:-public}                  # must be an IL2CPP branch: public, beta or default-previous
STEAMCMD=${STEAMCMD:-/opt/steamcmd/steamcmd.sh}
IL2CPPDUMPER=${IL2CPPDUMPER:-/opt/il2cppdumper/Il2CppDumper.dll}
PY=${PY:-/opt/venv/bin/python3}
SCRIPTS=${SCRIPTS:-/opt/pawn}

if [ -n "${STEAM_USER:-}" ]; then
    # The game has no anonymous depot, so this needs an account that owns it.
    # With no STEAM_PASS, SteamCMD prompts for the password and Steam Guard code (run with -it).
    echo ">> Downloading app $APP_ID ($BRANCH) to $GAME as $STEAM_USER"
    "$STEAMCMD" +@sSteamCmdForcePlatformType windows +force_install_dir "$GAME" \
        +login "$STEAM_USER" ${STEAM_PASS:+"$STEAM_PASS"} \
        +app_update "$APP_ID" -beta "$BRANCH" validate +quit
fi

META="$GAME/Schedule I_Data/il2cpp_data/Metadata/global-metadata.dat"
if [ ! -f "$GAME/GameAssembly.dll" ] || [ ! -f "$META" ]; then
    echo "No IL2CPP game files in $GAME." >&2
    echo "Set STEAM_USER to download them, or mount an existing install at $GAME." >&2
    echo "(The 'alternate' Steam branches are Mono builds and will not work here.)" >&2
    exit 1
fi

mkdir -p "$OUT/disasm" "$WORK"

echo ">> Il2CppDumper"
dotnet "$IL2CPPDUMPER" "$GAME/GameAssembly.dll" "$META" "$WORK" > "$WORK/il2cppdumper.log" 2>&1 || true
if [ ! -s "$WORK/dump.cs" ] || [ ! -s "$WORK/script.json" ]; then
    cat "$WORK/il2cppdumper.log" >&2
    echo "Il2CppDumper failed" >&2
    exit 1
fi
cp "$WORK/dump.cs" "$OUT/dump.cs"

echo ">> Disassembling the pawn shop methods"
dis() { "$PY" "$SCRIPTS/disasm.py" "$GAME/GameAssembly.dll" "$WORK/script.json" "$1" > "$OUT/disasm/$2.txt"; }
dis 'PawnShopInterface\$\$GetItemValue$' GetItemValue
dis 'PawnShopInterface\$\$RoundOffer$' RoundOffer
dis 'PawnShopInterface\$\$Awake$' Awake
dis 'PawnShopInterface.*NegotiationRoutine.*MoveNext$' NegotiationRoutine
dis 'ShopListing\$\$get_Price$' ShopListing_get_Price
dis '^System\.String\$\$GetLegacyNonRandomizedHashCode$' String_GetHashCode

echo ">> Reading item, store and curve data from the asset files"
"$PY" "$SCRIPTS/extract.py" "$GAME/Schedule I_Data" "$WORK/dump.cs" > "$OUT/data.json"
"$PY" "$SCRIPTS/build_items.py" "$OUT/data.json" > "$OUT/items.js"

"$PY" - "$GAME" > "$OUT/version.txt" <<'PYEOF'
import hashlib, re, sys
game = sys.argv[1]
ggm = open(game + "/Schedule I_Data/globalgamemanagers", "rb").read()
ver = re.search(rb"\x00(\d+\.\d+\.\d+f\d+)\x00", ggm)
unity = re.search(rb"(20\d\d\.\d+\.\d+[abfp]\d+)", ggm)
print("game version:", ver.group(1).decode() if ver else "unknown")
print("unity version:", unity.group(1).decode() if unity else "unknown")
for f in ("GameAssembly.dll", "Schedule I_Data/il2cpp_data/Metadata/global-metadata.dat"):
    print("sha256", hashlib.sha256(open(game + "/" + f, "rb").read()).hexdigest(), f)
PYEOF

cat "$OUT/version.txt"
echo ">> Done. Output in $OUT:"
ls -l "$OUT" "$OUT/disasm"
