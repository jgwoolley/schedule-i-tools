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
