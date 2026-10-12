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
