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
