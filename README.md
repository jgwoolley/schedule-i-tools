# Nf3t's Schedule I Tools

A pawn shop calculator and save file viewer for Schedule I. Everything runs in the browser; nothing is uploaded.

## Using it

Open `public/index.html` in a browser, or serve the `public/` folder (for example `npx http-server public`) if you
want the installable PWA parts (service worker, offline caching) to work; those need http(s), not a `file://` path.

Drop a zip of a `SaveGame_N` folder on the page to fill in the day and see the save's stats. The page remembers the
last save, tab, section, day and known players in the browser's localStorage. Steam IDs are only ever read from a save
the visitor loads; none are stored in this repository.

| Tab | Sections |
|---|---|
| Pawn Shop | Best item to buy and pawn, Price one item, Multiplier calendar |
| Save Stats | Overview, Save, Money, Rank, Empire, Products, Activity, Quests, Cartel, Player |
| Compare Players | Leaderboard, Counters, Progress flags, Carrying, Wearing. Enabled only when the save has two or more players |
| Known Players | Steam IDs found in the saves loaded in this browser, each linked to its Steam profile, with an editable nickname used as the player's label elsewhere |
| Game Data | Items, Stores, How the pawn price works |
| Work in Progress | Placeholder cards for planned tools, each marked as needing only save data or further game code analysis |

## Build / deploy

`npm run build` writes `public/build.json` (build time and commit link), which the page shows in its footer as
"Built ... ago. View commit (abc1234)". It is meant to run in CI; without it the footer stays empty.

Pushing to `main` runs `.github/workflows/deploy.yml`, which builds and deploys `public/` to GitHub Pages.
One-time setup: repository Settings -> Pages -> Source: "GitHub Actions".

## Project layout

- `public/` - the site (everything that gets deployed): `index.html`, `icon.svg`, `manifest.json`, `sw.js`
- `scripts/` - the Node script run by `npm run build`
- `.github/workflows/` - the GitHub Pages deploy pipeline
- `pawn-extract/` - Dockerfile and scripts that download the game and extract the data the page uses

# How the pawn shop data was produced

This records how the pawn shop numbers in `public/index.html` were worked out, so it can be redone after a game update.
Nothing here was checked against the running game; everything comes from reading the game files.

## Game build this was done against

| | |
|---|---|
| Game version | 0.4.7f12 (from `Schedule I_Data/globalgamemanagers`) |
| Unity | 2022.3.62f2, IL2CPP, metadata version 31 (reported as 31.1 by Cpp2IL) |
| `GameAssembly.dll` sha256 starts | `61829050e56ca180` |
| `global-metadata.dat` sha256 starts | `e775c97da277da8e` |
| Test save | a save zip from game version 0.4.6f13, `ElapsedDays` 138 |

The game is an IL2CPP build: there is no C# to decompile, only native x64 code plus a metadata file
that holds the class, field and method names.

## Software used

| Tool | Version | Used for | Source |
|---|---|---|---|
| Il2CppDumper | v6.7.46 (`Il2CppDumper-net6-v6.7.46.zip`) | `dump.cs` (classes, field offsets, method addresses) and `script.json` (symbol names for the disassembly) | https://github.com/Perfare/Il2CppDumper/releases |
| .NET runtime | 10.0.12 (SDK 10.0.401) | Running Il2CppDumper. It targets .NET 6, so it needs `DOTNET_ROLL_FORWARD=LatestMajor` on a newer runtime | https://dotnet.microsoft.com |
| GNU objdump | binutils 2.42 | Disassembling `GameAssembly.dll` | `apt install binutils` |
| Python | 3.12.3 | The helper scripts below | |
| UnityPy | 1.25.4 | Reading the Unity asset files | `pip install UnityPy` |
| Node.js | 22.23.3 | Only to test the page's JavaScript outside a browser | |
| Cpp2IL | 2022.1.0-pre-release.21 (Linux build) | Optional. Used once to browse class names; Il2CppDumper's `dump.cs` covers the same ground | https://github.com/SamboyCoding/Cpp2IL/releases |

All of this ran on Linux against the Windows game files. No game code is executed.

## Steps

`GAME` is the game folder (the one containing `GameAssembly.dll`). The four scripts are in the appendix.

### 1. Dump names and addresses

```sh
unzip Il2CppDumper-net6-v6.7.46.zip -d i2d
# in i2d/config.json set "RequireAnyKey": false so it does not wait for a keypress
mkdir out
DOTNET_ROLL_FORWARD=LatestMajor dotnet i2d/Il2CppDumper.dll \
    "$GAME/GameAssembly.dll" \
    "$GAME/Schedule I_Data/il2cpp_data/Metadata/global-metadata.dat" out
```

This writes `out/dump.cs`, `out/script.json`, `out/stringliteral.json`.

### 2. Find the code

Searching `dump.cs` for "Pawn" finds `ScheduleOne.UI.PawnShopInterface`. Its relevant methods:
`GetItemValue`, `RoundOffer`, `UpdateValueRangeLabels`, `Awake`, and the coroutine
`<<StartNegotiation>g__NegotiationRoutine|65_0>d.MoveNext`.

### 3. Disassemble and read it

```sh
python3 disasm.py "$GAME/GameAssembly.dll" out/script.json 'PawnShopInterface\$\$' list
python3 disasm.py "$GAME/GameAssembly.dll" out/script.json 'PawnShopInterface\$\$GetItemValue$'
python3 disasm.py "$GAME/GameAssembly.dll" out/script.json 'PawnShopInterface\$\$RoundOffer$'
python3 disasm.py "$GAME/GameAssembly.dll" out/script.json 'NegotiationRoutine.*MoveNext'
```

How to read the output:

- `[reg+0xNN]` is a field access; look up the offset in `dump.cs` under the class (and its base classes).
- `call QWORD PTR [rax+0xNNN]` is a virtual call. The vtable starts at `0x138` and each slot is 16 bytes,
  so `0x158` is slot 2 (`GetHashCode`) and `0x178` is slot 4. `dump.cs` prints `Slot: N` next to each virtual method.
- A line annotated `; @0x2e5cb40` loads a float constant. Read it with
  `python3 readfloat.py "$GAME/GameAssembly.dll" 0x2e5cb40`.
- `System.String.GetHashCode` has the same address as `GetLegacyNonRandomizedHashCode`, which is how
  the hash is known to be the deterministic one.

### 4. Extract the data

```sh
python3 -m venv venv && venv/bin/pip install UnityPy
venv/bin/python3 extract.py "$GAME/Schedule I_Data" out/dump.cs > data.json
python3 build_items.py data.json > items.js
```

`data.json` holds the pawn shop's `RandomCurve` keyframes, every item definition, and every store listing.
`items.js` is the `SHOPS` / `ITEMS` block that gets pasted into `public/index.html`. If the curve changes,
update the `CURVE` constant in the page by hand from `data.json`.

### 5. Write the page and test it

`public/index.html` is one file with inline JavaScript and no dependencies. The multiplier was compared with a
separate Python implementation (36 item/day pairs, no mismatches). The page itself was exercised in jsdom
(tabs, section picker, dropping a save zip, reload persistence, build footer), not in a real browser.

## What the code does

Reconstructed from `PawnShopInterface.GetItemValue` (RVA `0x9f7ad0`):

```csharp
float GetItemValue(ItemInstance item) {
    var def = item.Definition as StorableItemDefinition;
    float value = def.BasePurchasePrice * def.ResellMultiplier * item.Quantity;

    // the test compiles as (Name[0] + Name.Length) > 1, which is always true
    string key = (item.Name[0] + item.Name.Length > 1) ? item.Name[1].ToString() : "A";
    int hash = (key + TimeManager.Instance.ElapsedDays).GetHashCode();

    float x = Mathf.Lerp(0.5f, 2f, Mathf.InverseLerp(int.MinValue, int.MaxValue, hash));
    float mult = RandomCurve.Evaluate(x);
    Console.Log("Value multiplier: " + x + " -> " + mult);
    return value * mult;
}
```

The shop's opening offer is `RoundOffer(sum of GetItemValue over the five pawn slots)`.

Details that matter when reimplementing:

- **Fields.** `BaseItemInstance.Quantity` 0x10, `BaseItemDefinition.Name` 0x18, `StorableItemDefinition.BasePurchasePrice` 0x78,
  `StorableItemDefinition.ResellMultiplier` 0x94, `TimeManager.ElapsedDays` 0x12C, `PawnShopInterface.RandomCurve` 0x58.
- **Float constants.** 0.5, 1.5 and 1.0 for the lerp and clamp; -2147483648.0 and 2.3283064e-10 (1/2^32) for the inverse lerp.
  The arithmetic is 32-bit float, so the page uses `Math.fround`.
- **Hash.** Mono's legacy string hash: `h1 = h2 = 5381`; even-index characters go into `h1 = h1*33 ^ c`, odd-index
  into `h2 = h2*33 ^ c`; result `h1 + h2*1566083941`, all in 32-bit signed arithmetic.
- **Curve.** Four keyframes (time, value, inSlope, outSlope), unweighted, so plain cubic Hermite:
  (0.5, 0.5, 1.0, 1.0185316), (0.9569855, 0.9654541, 1.0185316, 0.5162295), (1.6529340, 1.3247232, 0.5162295, 1.9456722), (2.0, 2.0, 1.9456722, 0.0).
- **RoundOffer.** No rounding up to 25; then nearest 5 up to 100, 10 up to 1,000, 50 up to 10,000, 100 up to 100,000,
  500 up to 1,000,000, else 1,000. Each comparison is "less than or equal".
- **Item name.** `Name` is virtual. Clothing appends " (Colour)" and products append packaging, but neither changes the second character.
- **What the slots accept.** `Awake` adds two filters to each slot: legal status must be Legal (0), and the item ID must not be `cash`.
- **Day number.** `ElapsedDays` starts at 0 in the default save, and weekday is `ElapsedDays % 7` with 0 = Monday.

### Consequence: the item barely matters, and the day repeats

The second letter of the name only feeds `h1`, which is swamped by `h2 * 1566083941`. Across all 204 items the
multiplier differs by less than 0.0001 on any given day (checked for days 0 to 2999). So every item gets
effectively the same multiplier each day.

For the same reason only some digits of the day number matter:

| Day range | Multiplier depends on |
|---|---|
| 0 to 9 | the day |
| 10 to 99 | the tens digit only (constant for ten days in a row) |
| 100 to 999 | the hundreds and ones digits (a ten-day cycle within each hundred) |
| 1000 to 9999 | the thousands and tens digits |

Example: day 138 gives 1.935, and so do 108, 118, 128, 148 ... 198.

## Check against store prices

A store's price is `ShopListing.Price` (RVA `0xaaf2b0`): `OverridePrice ? OverriddenPrice : Item.BasePurchasePrice`.
`extract.py` reads every `ShopInterface` in the main scene (`level1`; `level2` is the tutorial map) and resolves each listing to its item.

Results for this build:

- 12 shops, 258 listings, every listing resolved to an item.
- No listing uses `OverridePrice`, so every store price equals the item's `BasePurchasePrice`. Zero mismatches.
- Of the 204 pawnable items, 167 are sold in a store. The other 37 (skateboards, some clothing, Friendly Notes, RDX, Bomb, Sewer Key and others) are not.
- 18 items can pawn for more than their store price on a good day, because their resell multiplier is above 0.5:
  the six artworks (1.0), Gold Bar and Golden Toilet (0.9), the watches, chains and three wines (0.8), Persian Rug and Grandfather Clock (0.75), Jukebox (0.6).
  The artworks and Golden Toilet have a stock of 1 at the boutique.

## Save files

A save is a folder of JSON files (`SaveGame_N/...`), on Windows under
`%USERPROFILE%\AppData\LocalLow\TVGS\Schedule I\Saves\<steam id>\`. Under Proton (Linux, Steam Deck) the same path sits inside
`~/.local/share/Steam/steamapps/compatdata/3164500/pfx/drive_c/users/steamuser/`; the page lists the Flatpak and macOS (CrossOver, Whisky) locations too. The day is `ElapsedDays` in `Time.json`.
The page reads a zip in the browser: it walks the zip's central directory, finds the entry ending in `/Time.json`,
and inflates it with the browser's built-in `DecompressionStream('deflate-raw')`. It also reads `OrganisationName` from `Game.json` for display.

## Docker: download the game and extract in one step

`pawn-extract/` holds a Dockerfile that packages steps 1, 3 and 4. It installs SteamCMD, Il2CppDumper,
the .NET 8 runtime, objdump, Python and UnityPy, and at run time downloads the Windows build of the game
and writes the extracted data to `/out`.

The image has not been built or run: no Docker was available where it was written. The four Python scripts
were run against the 0.4.7f12 game files before being packaged; `run.sh` was only syntax-checked and run as far as its
"no game files" error.

Schedule I (Steam app 3164500, depot 3164501) has no dedicated server and no anonymous depot, so SteamCMD
needs a Steam account that owns the game. The download is about 6.4 GB.

```sh
cd pawn-extract
docker build -t pawn-extract .

# download with SteamCMD, then extract (prompts for password and Steam Guard code)
docker run --rm -it -e STEAM_USER=your_account \
    -v schedule1-game:/game -v schedule1-steam:/root/Steam -v "$PWD/out:/out" pawn-extract

# or use a copy of the game you already have, with no Steam login
docker run --rm -v "/path/to/Schedule I:/game:ro" -v "$PWD/out:/out" pawn-extract
```

- The `schedule1-game` volume keeps the download, so later runs only fetch what changed.
  The `schedule1-steam` volume keeps the login token, so later runs usually skip the Steam Guard prompt.
- Credentials are only used at run time and are never written into the image. `STEAM_PASS` can be set
  for unattended runs, but it is then visible in the container's environment and in `docker inspect`.
- `BRANCH` selects the Steam branch: `public` (default), `beta` or `default-previous`. The `alternate*`
  branches are Mono builds, which this IL2CPP pipeline cannot read.

Output in `out/`:

| File | Contents |
|---|---|
| `items.js` | The `SHOPS` / `ITEMS` block to paste into `public/index.html` |
| `data.json` | Curve keyframes, all item definitions, all store listings. Update `CURVE` in the page from this if it changed |
| `disasm/*.txt` | Annotated disassembly of `GetItemValue`, `RoundOffer`, `Awake`, the negotiation coroutine, `ShopListing.get_Price` and the string hash, to compare with "What the code does" above |
| `dump.cs` | Il2CppDumper's class dump |
| `version.txt` | Game and Unity version, and hashes of the two input files |

### An easier way to check the formula

The `alternate` Steam branch is a Mono build of the same game. Its `Schedule I_Data/Managed/Assembly-CSharp.dll`
can be opened in ILSpy or dnSpy to read `PawnShopInterface.GetItemValue` as real C#, with no disassembly.
This was found after the work above and has not been tried.

## Not verified

- Nothing was compared with offers seen in the game.
- The rounding helper called by `RoundOffer` was assumed to round halves to even (Unity's `Mathf.Round`); it was not traced.
- Haggling (`EvaluateCounter`, the anger meter) was not analysed.
- The test save is from 0.4.6f13 and the analysed game files are 0.4.7f12.

## Redoing this after a game update

1. Rerun steps 1, 3 and 4.
2. Compare the `GetItemValue` and `RoundOffer` disassembly with the description above. Constant addresses and method RVAs will move; the shape should not.
3. `extract.py` depends on the field order of `BaseItemDefinition`, `ItemDefinition`, `StorableItemDefinition`, `ShopInterface`, `ShopListing` and `PawnShopInterface` in `dump.cs`. If a field was added or removed, update the matching read in the script. A wrong layout usually shows up as a "bad string length" error or absurd prices.
4. Paste the new `items.js` into the page, and update `CURVE` if it changed.

## Appendix: scripts

### disasm.py

```python
#!/usr/bin/env python3
"""Disassemble IL2CPP methods by name, annotated with Il2CppDumper symbols.

usage: disasm.py <GameAssembly.dll> <Il2CppDumper script.json> <method name regex> [list]
  e.g. disasm.py GameAssembly.dll out/script.json 'PawnShopInterface\\$\\$GetItemValue$'
Add "list" to print only the matching names and addresses.
Do not name this file dis.py: that shadows a Python standard library module.
"""
import json, sys, subprocess, re, bisect

DLL, SCRIPT, PATTERN = sys.argv[1:4]
BASE = 0x180000000   # PE image base; script.json addresses are RVAs

j = json.load(open(SCRIPT))
meth = {m["Address"]: m["Name"] for m in j["ScriptMethod"]}
data = {}
for m in j["ScriptString"]: data[m["Address"]] = "STR " + repr(m["Value"])
for m in j["ScriptMetadata"]: data[m["Address"]] = "META " + m["Name"]
for m in j["ScriptMetadataMethod"]: data[m["Address"]] = "METHOD " + m["Name"]
addrs = sorted(meth)

def dis(a):
    i = bisect.bisect_right(addrs, a)
    end = addrs[i] if i < len(addrs) else a + 0x400
    out = subprocess.run(["objdump", "-d", "-M", "intel", "--no-show-raw-insn",
                          f"--start-address={BASE+a:#x}", f"--stop-address={BASE+end:#x}", DLL],
                         capture_output=True, text=True).stdout
    for l in out.splitlines():
        m = re.match(r"\s*([0-9a-f]+):\s+(.*)", l)
        if not m: continue
        ins, ann = m.group(2), ""
        for x in re.findall(r"0x([0-9a-f]{9,})", ins):
            r = int(x, 16) - BASE
            if r in meth: ann += "  ; " + meth[r]
            elif r in data: ann += "  ; " + data[r]
            elif "xmm" in ins: ann += "  ; @" + hex(r)   # float constant: read 4 bytes at this RVA
        ins = re.sub(r"\s+#.*", "", ins)
        print(f"{int(m.group(1),16)-BASE:x}: {ins}{ann}")

for a, n in sorted((a, n) for a, n in meth.items() if re.search(PATTERN, n)):
    print(f"==== {n} @ {a:#x}")
    if len(sys.argv) < 5: dis(a)
```

### readfloat.py

```python
#!/usr/bin/env python3
"""Read float32 constants from a PE file by RVA.  usage: readfloat.py <GameAssembly.dll> 0x2e5cb40 [...]"""
import struct, sys
f = open(sys.argv[1], "rb").read()
pe = struct.unpack_from("<I", f, 0x3c)[0]
nsec, optsize = struct.unpack_from("<H", f, pe + 6)[0], struct.unpack_from("<H", f, pe + 20)[0]
secs = [struct.unpack_from("<IIII", f, pe + 24 + optsize + 40 * i + 8) for i in range(nsec)]  # vsize, vaddr, rawsize, rawptr
for arg in sys.argv[2:]:
    rva = int(arg, 16)
    for vsize, vaddr, _, rawptr in secs:
        if vaddr <= rva < vaddr + vsize:
            print(arg, struct.unpack_from("<f", f, rawptr + rva - vaddr)[0])
```

### extract.py

```python
#!/usr/bin/env python3
"""Pull pawn-shop data out of the Schedule I asset files.

usage: extract.py "<game>/Schedule I_Data" <Il2CppDumper output dir>/dump.cs > data.json

The game ships without type trees, so MonoBehaviours are parsed by hand:
fields appear in declaration order (base class first), 4-byte aligned after
every bool and string. Field order comes from dump.cs.
"""
import UnityPy, struct, re, json, sys, collections

DATA, DUMP = sys.argv[1], sys.argv[2]
MAIN_SCENE = "level1"          # level2 is the tutorial copy of the map

parent = {}
for line in open(DUMP, encoding="utf8"):
    m = re.match(r"^(?:public|internal|private)[\w ]*? class ([\w.<>`]+) : ([\w.<>`]+)", line)
    if m:
        parent[m.group(1)] = m.group(2)

def derives(cls, base):
    while cls:
        if cls == base:
            return True
        cls = parent.get(cls)
    return False

class Reader:
    def __init__(self, b): self.b, self.p = b, 0
    def i32(self): v = struct.unpack_from("<i", self.b, self.p)[0]; self.p += 4; return v
    def f32(self): v = struct.unpack_from("<f", self.b, self.p)[0]; self.p += 4; return v
    def pptr(self): v = struct.unpack_from("<iq", self.b, self.p); self.p += 12; return v
    def boolean(self): v = self.b[self.p]; self.p += 4; return bool(v)
    def string(self):
        n = self.i32()
        if not 0 <= n <= 100000: raise ValueError("bad string length")
        v = self.b[self.p:self.p + n].decode("utf8"); self.p = (self.p + n + 3) & ~3; return v

def target(obj, ptr):
    """Resolve a PPtr (fileID, pathID) to (asset file name, pathID)."""
    fid, pid = ptr
    af = obj.assets_file
    name = af.name if fid == 0 else af.externals[fid - 1].path.split("/")[-1]
    return (name.lower(), pid)

env = UnityPy.load(DATA)
scripts = {(o.assets_file.name.lower(), o.path_id): o.read().m_ClassName
           for o in env.objects if o.type.name == "MonoScript"}

items, shops, curve = {}, [], None
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    r = Reader(o.get_raw_data())
    try:
        r.pptr(); r.boolean(); script = r.pptr(); r.string()   # m_GameObject, m_Enabled, m_Script, m_Name
    except Exception:
        continue
    cls = scripts.get(target(o, script))
    if cls is None:
        continue

    if derives(cls, "StorableItemDefinition"):
        # BaseItemDefinition
        name, item_id = r.string(), r.string(); r.string(); r.pptr()       # Name, ID, Description, Icon
        r.i32(); r.i32(); r.boolean(); r.pptr(); legal = r.i32()            # Category, StackLimit, UsableInFilters, EquippableData, legalStatus
        # ItemDefinition
        r.boolean(); r.i32(); r.pptr(); r.pptr(); r.pptr()                  # AvailableInDemo, EquipMode, Equippable, CustomItemUI, CustomInfoContent
        # StorableItemDefinition
        price = r.f32()                                                     # BasePurchasePrice
        for _ in range(r.i32()): r.i32()                                    # ShopCategories
        r.boolean(); r.i32(); r.i32()                                       # RequiresLevelToPurchase, RequiredRank{Rank,Tier}
        resell = r.f32()                                                    # ResellMultiplier
        items[(o.assets_file.name.lower(), o.path_id)] = dict(
            name=name, id=item_id, cls=cls, legal=legal, price=price, resell=round(resell, 4))

    elif derives(cls, "ShopInterface") and o.assets_file.name == MAIN_SCENE:
        shop, code = r.string(), r.string(); r.string(); r.i32(); r.boolean()   # ShopName, ShopCode, ShopDescription, PaymentType, ShowCurrencyHint
        listings = []
        for _ in range(r.i32()):                                             # List<ShopListing>
            r.string(); item = target(o, r.pptr())                           # name, Item
            override, overridden = r.boolean(), r.f32()                      # OverridePrice, OverriddenPrice
            r.boolean(); r.i32(); r.i32(); r.boolean(); r.string()           # LimitedStock, DefaultStock, RestockRate, TieStockToNumberVariable, StockVariableName
            r.boolean(); r.string(); r.boolean(); r.f32()                    # TrackPurchases, PurchasedQuantityVariableName, EnforceMinimumGameCreationVersion, MinimumGameCreationVersion
            r.boolean(); r.boolean(); r.p += 16                              # CanBeDelivered, UseIconTint, IconTint
            r.boolean(); r.string()                                          # ConditionalVisibility, ConditionalVisibilityVariableName
            listings.append((item, overridden if override else None))
        shops.append((shop, code, listings))

    elif cls == "PawnShopInterface":
        r.pptr()                                                             # PawnShopNPC; then RandomCurve: count + 28-byte keyframes
        keys = [struct.unpack_from("<ffffiff", r.b, r.p + 28 * i) for i in range(r.i32())]
        curve = [list(k[:4]) for k in keys]                                  # time, value, inSlope, outSlope

# store price per item = ShopListing.Price = OverridePrice ? OverriddenPrice : Item.BasePurchasePrice
stores = collections.defaultdict(list)
for shop, code, listings in shops:
    for ref, override in listings:
        it = items[ref]
        stores[it["id"]].append(dict(shop=shop, code=code, price=it["price"] if override is None else override))

json.dump(dict(curve=curve, items=sorted(items.values(), key=lambda i: i["name"]), stores=stores),
          sys.stdout, indent=1, ensure_ascii=False)
```

### build_items.py

```python
#!/usr/bin/env python3
"""Turn extract.py's data.json into the SHOPS / ITEMS block pasted into public/index.html.
usage: build_items.py data.json > items.js"""
import json, sys
d = json.load(open(sys.argv[1], encoding="utf8"))
num = lambda v: int(v) if v == int(v) else v
rows = []
for i in d["items"]:
    # pawn slots only accept legalStatus == Legal (0) and reject "cash"; "... effects" are internal dummy items
    if i["legal"] != 0 or i["id"] == "cash" or i["name"].endswith(" effects"):
        continue
    stores = d["stores"].get(i["id"], [])
    bad = [s for s in stores if s["price"] != i["price"]]
    if bad:
        print("WARNING: store price differs from BasePurchasePrice:", i["name"], bad, file=sys.stderr)
    rows.append([i["name"], num(i["price"]), num(i["resell"]), sorted({s["shop"] for s in stores})])
shops = sorted({s for r in rows for s in r[3]})
for r in rows:
    r[3] = [shops.index(s) for s in r[3]]
print("const SHOPS = " + json.dumps(shops, ensure_ascii=False) + ";")
print("const ITEMS = " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";", end="")
```
