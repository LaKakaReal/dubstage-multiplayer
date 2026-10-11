"""Minimaler RAR-4-Schreiber (nur "gespeichert", ohne Kompression) fuer Tests.

Es gibt kein freies Werkzeug, das RAR schreibt - fuer die Tests reicht das
Speicherformat, das jedes Entpackprogramm lesen kann.
"""

import struct
import zlib


def _head(htype, flags, body):
    size = 7 + len(body)
    data = struct.pack("<BHH", htype, flags, size) + body
    crc = zlib.crc32(data) & 0xFFFF
    return struct.pack("<H", crc) + data


def write_rar4(path, files):
    """files: {"ordner/name.ext": bytes}"""
    out = [b"Rar!\x1a\x07\x00", _head(0x73, 0x0000, b"\x00" * 6)]
    for name, data in files.items():
        raw = name.replace("/", "\\").encode("ascii")
        body = struct.pack("<IIBIIBBHI", len(data), len(data), 2,
                           zlib.crc32(data) & 0xFFFFFFFF,
                           0x00210000,            # DOS-Zeit 1980-01-01
                           20, 0x30, len(raw), 0x20) + raw
        out.append(_head(0x74, 0x8000, body))   # LONG_BLOCK: Daten folgen
        out.append(data)
    out.append(_head(0x7B, 0x4000, b""))
    with open(path, "wb") as f:
        f.write(b"".join(out))
    return path
