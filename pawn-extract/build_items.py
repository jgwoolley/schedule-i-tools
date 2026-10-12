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
