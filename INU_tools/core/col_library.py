"""
COL libraries inside IMG archives — model records as raw bytes.

A ``.col`` entry is a run of records: ``COLL``/``COL2``/``COL3``/``COL4``,
u32 size of the rest of the record, 22-byte model name, u16 model id, body.
The game reads records until the first unknown header, so a library can be
edited record by record: only the touched model's bytes change, every other
model stays byte for byte.

No Blender dependency — pure Python.
"""

import struct

COL_MAGIC = (b'COLL', b'COL2', b'COL3', b'COL4')


def col_chunks(data):
    """[(start, end, model name, model_id)] of the records at the head of
    *data* (stops at the first unknown or truncated record)."""
    out, pos = [], 0
    while pos + 32 <= len(data) and data[pos:pos + 4] in COL_MAGIC:
        size = struct.unpack_from('<I', data, pos + 4)[0]
        end = pos + 8 + size
        if end > len(data):
            break
        name = data[pos + 8:pos + 30].split(b'\x00', 1)[0].decode('ascii', 'replace')
        mid = struct.unpack_from('<H', data, pos + 30)[0]
        out.append((pos, end, name, mid))
        pos = end
    return out


def col_splice(data, name, make):
    """Records of model *name* (any case) → ``make(model_id)`` bytes, or
    dropped when it returns None. Returns ``(records, matched, left)``: the
    new library, how many records matched, how many records it holds.

    Other records are kept byte for byte. The sector padding after the last
    record is NOT kept: VC drops a whole library whose tail past the records
    is 2056 bytes or more, and the IMG writer pads the entry again anyway."""
    out, n, left = [], 0, 0
    for s, e, nm, mid in col_chunks(data):
        if nm.lower() == name.lower():
            n += 1
            new = make(mid)
            if new:
                out.append(new)
                left += 1
        else:
            out.append(data[s:e])
            left += 1
    return b''.join(out), n, left


def col_index(reader):
    """{model name (lower): [.col entry names]} of an open ``ImgReader`` —
    which library of the archive holds each model (record headers only)."""
    idx = {}
    for e in reader.entries:
        if not e.name.lower().endswith('.col') or not e.size:
            continue
        for _s, _e, nm, _mid in col_chunks(reader.read(e.name) or b''):
            lst = idx.setdefault(nm.lower(), [])
            if e.name not in lst:
                lst.append(e.name)
    return idx
