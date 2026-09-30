"""Meshes of one placement — a model of several meshes (no Blender dependency).

The game draws every atomic of a map model with the matrix of its IPL row:
the atomic's own frame is dropped (SA CFileLoader::SetRelatedModelInfoCB
0x537150 — RpAtomicSetFrame(atomic, RwFrameCreate()); re3 / reVC
FileLoader.cpp SetRelatedModelInfoCB). So the meshes of one DFF standing
together — the intact and the damaged part of a breakable (bar_barrier10_L0
+ bar_barrier10_dam), III/VC LOD levels (…_l0, …_l1) — are ONE placement:
one ``inst`` row, one IDE row, one model name.
"""

import re

# The Import tab's «same placement» (ops/img_ops _find_placed).
SPOT_POS_TOL = 1e-3
SPOT_DOT_MIN = 0.9999


def group_instances(items, pos_tol=SPOT_POS_TOL, dot_min=SPOT_DOT_MIN):
    """Meshes standing as one placement.

    *items* — ``(key, model_id, (x, y, z), (w, x, y, z))``. Returns lists of
    keys, every key once, in input order: the same model id, positions within
    *pos_tol* and ``|q·q'| ≥ dot_min`` (q and −q are one rotation). Chains
    join (a~b, b~c → one list)."""
    n = len(items)
    parent = list(range(n))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def unit(q):
        s = sum(c * c for c in q) ** 0.5
        return tuple(c / s for c in q) if s > 1e-9 else None

    rots = [unit(it[3]) for it in items]
    by_mid = {}
    for i, it in enumerate(items):
        by_mid.setdefault(int(it[1]), []).append(i)
    t2 = pos_tol * pos_tol
    for idx in by_mid.values():
        if len(idx) < 2:
            continue
        idx.sort(key=lambda i: items[i][2][0])
        for a in range(len(idx)):
            i = idx[a]
            pi, qi = items[i][2], rots[i]
            for b in range(a + 1, len(idx)):
                j = idx[b]
                pj, qj = items[j][2], rots[j]
                if pj[0] - pi[0] > pos_tol:
                    break
                if (qi is None or qj is None
                        or sum((u - v) ** 2 for u, v in zip(pi, pj)) > t2
                        or abs(sum(u * v for u, v in zip(qi, qj))) < dot_min):
                    continue
                ri, rj = root(i), root(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)
    groups = {}
    for i in range(n):
        groups.setdefault(root(i), []).append(items[i][0])
    return list(groups.values())


# A mesh named after its DFF frame: the damaged part «…_dam» (SA
# GetNameAndDamage 0x5370A0) and a LOD level «…_L0» (SA: _L0; re3 / reVC
# GetNameAndLOD: _l<digit>) belong to the model without that tail.
_NODE_TAIL = re.compile(r'_(?:dam|l\d+)$', re.IGNORECASE)
_DAM_TOKEN = re.compile(r'_dam(?![a-z])', re.IGNORECASE)


def game_model_name(name):
    """*name* without a trailing ``_dam`` / ``_L<digits>`` (any case):
    bar_barrier10_L0 → bar_barrier10, sand_josh1_dam → sand_josh1;
    lodfoo, road_l0x stay. A name that is nothing but the tail stays."""
    name = name or ''
    return _NODE_TAIL.sub('', name) or name


def is_damage_part(name):
    """The damaged part of a breakable (SA ``…_dam`` atomic): «_dam» as a
    word — bar_barrier10_dam, …_dam_DFF, …_dam.001 — not «_damper»."""
    return bool(_DAM_TOKEN.search(name or ''))
