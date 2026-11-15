#!/usr/bin/env python3
"""Renderiza "fotos" del lobby con las texturas y modelos reales de los jars.

    python3 lobby/render_fotos.py [ruta/al/client-1.20.1.jar]

Rasterizador por software (numpy): lee blockstates + modelos JSON de vanilla y
de los mods, aplica rotaciones y texturas. Los bloques con renderizador
especial (carteles, estandartes) se aproximan. Luz de día, sin sombras.
"""
import glob
import io
import json
import math
import os
import sys
import zipfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generar_lobby as g  # noqa: E402  (construye el lobby al importarse)

REPO = os.path.dirname(HERE)
CLIENT_GUESSES = [
    "~/.local/share/com.jonaykb.kb-mc-launcher/versions/1.20.1/1.20.1.jar",
    "~/.var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/libraries/com/mojang/minecraft/1.20.1/minecraft-1.20.1-client.jar",
]


class Assets:
    def __init__(self, jars):
        self.zips = [zipfile.ZipFile(j) for j in jars]
        self.cache = {}

    def read(self, path):
        for z in self.zips:
            try:
                return z.read(path)
            except KeyError:
                pass
        return None

    def json(self, path):
        if path not in self.cache:
            d = self.read(path)
            self.cache[path] = json.loads(d) if d else None
        return self.cache[path]


def rl(s, kind):
    ns, p = s.split(":", 1) if ":" in s else ("minecraft", s)
    return f"assets/{ns}/{kind}/{p}"


class Models:
    def __init__(self, assets):
        self.a = assets
        self.textures = {}
        self.tex_list = []
        self.model_cache = {}

    def texture(self, name):
        if name not in self.textures:
            data = self.a.read(rl(name, "textures") + ".png")
            if data is None:
                arr = np.zeros((16, 16, 4), np.uint8)
                arr[..., 0], arr[..., 2], arr[..., 3] = 255, 255, 255
                arr[::2, ::2, :3] = 0
            else:
                im = Image.open(io.BytesIO(data)).convert("RGBA")
                w, h = im.size
                if h > w:
                    im = im.crop((0, 0, w, w))
                arr = np.array(im)
            self.textures[name] = len(self.tex_list)
            self.tex_list.append(arr)
        return self.textures[name]

    def model(self, name):
        if name in self.model_cache:
            return self.model_cache[name]
        name = name if ":" in name else "minecraft:" + name
        d = self.a.json(rl(name, "models") + ".json")
        if d is None:
            self.model_cache[name] = (None, {})
            return self.model_cache[name]
        elements, textures = None, {}
        if "parent" in d and not d["parent"].startswith("builtin"):
            elements, textures = self.model(d["parent"])
            textures = dict(textures)
        textures.update(d.get("textures", {}))
        if "elements" in d:
            elements = d["elements"]
        self.model_cache[name] = (elements, textures)
        return self.model_cache[name]

    def resolve(self, textures, ref, depth=0):
        while ref.startswith("#") and depth < 10:
            ref = textures.get(ref[1:], "missingno")
            depth += 1
        return ref


def pick_models(assets, name, props):
    bs = assets.json(rl(name, "blockstates") + ".json")
    if bs is None:
        return []
    if "variants" in bs:
        best = None
        for key, v in bs["variants"].items():
            ok = True
            for kv in filter(None, key.split(",")):
                k, val = kv.split("=")
                if k in props and props[k] != val:
                    ok = False
                    break
            if ok:
                best = v
                break
        if best is None:
            best = next(iter(bs["variants"].values()))
        return [best[0] if isinstance(best, list) else best]
    out = []
    for part in bs.get("multipart", []):
        w = part.get("when")
        if w is None or match_when(w, props):
            a = part["apply"]
            out.append(a[0] if isinstance(a, list) else a)
    return out


def match_when(w, props):
    if "OR" in w:
        return any(match_when(c, props) for c in w["OR"])
    if "AND" in w:
        return all(match_when(c, props) for c in w["AND"])
    for k, v in w.items():
        if props.get(k, "false" if k in ("north", "south", "east", "west", "up") else None) not in str(v).split("|"):
            return False
    return True


DIRS = {"north": (0, 0, -1), "south": (0, 0, 1), "west": (-1, 0, 0), "east": (1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0)}


def face_quad(f, a, b):
    x1, y1, z1 = a
    x2, y2, z2 = b
    return {
        "north": [(x2, y2, z1), (x1, y2, z1), (x1, y1, z1), (x2, y1, z1)],
        "south": [(x1, y2, z2), (x2, y2, z2), (x2, y1, z2), (x1, y1, z2)],
        "west": [(x1, y2, z1), (x1, y2, z2), (x1, y1, z2), (x1, y1, z1)],
        "east": [(x2, y2, z2), (x2, y2, z1), (x2, y1, z1), (x2, y1, z2)],
        "up": [(x1, y2, z1), (x2, y2, z1), (x2, y2, z2), (x1, y2, z2)],
        "down": [(x1, y1, z2), (x2, y1, z2), (x2, y1, z1), (x1, y1, z1)],
    }[f]


def default_uv(f, a, b):
    x1, y1, z1 = a
    x2, y2, z2 = b
    return {
        "down": [x1, 16 - z2, x2, 16 - z1], "up": [x1, z1, x2, z2],
        "north": [16 - x2, 16 - y2, 16 - x1, 16 - y1], "south": [x1, 16 - y2, x2, 16 - y1],
        "west": [z1, 16 - y2, z2, 16 - y1], "east": [16 - z2, 16 - y2, 16 - z1, 16 - y1],
    }[f]


def rot_elem(p, r):
    ox, oy, oz = r["origin"]
    ang = math.radians(r["angle"])
    c, s = math.cos(ang), math.sin(ang)
    x, y, z = p[0] - ox, p[1] - oy, p[2] - oz
    ax = r["axis"]
    if ax == "x":
        y, z = y * c - z * s, y * s + z * c
    elif ax == "y":
        x, z = x * c + z * s, -x * s + z * c
    else:
        x, y = x * c - y * s, x * s + y * c
    return (x + ox, y + oy, z + oz)


def rot_block(p, rx, ry):
    x, y, z = p[0] - 8, p[1] - 8, p[2] - 8
    for _ in range((rx // 90) % 4):
        y, z = z, -y
    for _ in range((ry // 90) % 4):
        x, z = -z, x
    return (x + 8, y + 8, z + 8)


def rot_dir(d, rx, ry):
    x, y, z = d
    for _ in range((rx // 90) % 4):
        y, z = z, -y
    for _ in range((ry // 90) % 4):
        x, z = -z, x
    return (x, y, z)


FACING_RY = {"north": 0, "east": 90, "south": 180, "west": 270}
LEAF_TINT = np.array([0x61, 0x99, 0x61]) / 255.0


def fake_model(name, props):
    """Geometría aproximada para bloques con renderizador especial."""
    short = name.split(":")[1]
    tex = "minecraft:block/dark_oak_planks"
    els = None
    ry = 0
    if short.endswith("wall_sign"):
        els = [([0, 4.5, 14], [16, 12.5, 16], tex)]
        ry = FACING_RY[props.get("facing", "north")]
    elif short.endswith("hanging_sign"):
        els = [([1, 0, 7], [15, 10, 9], "minecraft:block/spruce_planks"),
               ([3, 10, 8], [4, 16, 8.1], "minecraft:block/chain"), ([12, 10, 8], [13, 16, 8.1], "minecraft:block/chain")]
    elif short.endswith("_sign"):
        els = [([0, 7, 7.25], [16, 15, 8.75], "minecraft:block/spruce_planks"),
               ([7.25, 0, 7.25], [8.75, 7, 8.75], "minecraft:block/spruce_log")]
    elif short.endswith("wall_banner"):
        els = [([1, -14, 14.5], [15, 14, 15.5], "minecraft:block/blue_wool"),
               ([0, 14, 13.5], [16, 15.5, 15.5], "minecraft:block/dark_oak_planks"),
               ([5, -8, 14.4], [11, 4, 14.5], "minecraft:block/white_wool")]
        ry = FACING_RY[props.get("facing", "north")]
    elif short.endswith("_banner"):
        els = [([1, 4, 7.5], [15, 30, 8.5], "minecraft:block/blue_wool"),
               ([5, 12, 8.5], [11, 24, 8.6], "minecraft:block/white_wool"),
               ([7.5, 0, 7.5], [8.5, 32, 8.5], "minecraft:block/dark_oak_planks")]
    if els is None:
        return None
    elements = [{"from": a, "to": b, "faces": {f: {"texture": t} for f in DIRS}} for a, b, t in els]
    return [(elements, {}, 0, ry)]


def opaque(name):
    return g.full(name) and not any(t in name for t in ("leaves", "glass", "ice", "spawner"))


EMISSIVE = ("lantern", "glowstone", "shroomlight", "froglight", "sea_lantern", "end_rod", "campfire", "candle",
            "fairy_lights", "wall_light", "floor_light", "chandelier")


def build_triangles(M, assets, blocks, extra_ground, light):
    tris, uvs, tids, shades, nights = [], [], [], [], []
    LW, LH, LD = light.shape
    warm = np.array([1.0, 0.82, 0.58])
    moon = np.array([0.30, 0.38, 0.58])
    sun = np.array([0.35, 0.85, 0.4])
    sun /= np.linalg.norm(sun)

    def emit(pos, quad, uvq, tid, normal, tint=None, glow=False):
        n = np.array(normal, float)
        nn = np.linalg.norm(n)
        n = n / nn if nn else n
        base = {1: 1.0, -1: 0.5}.get(round(n[1]), None)
        shade = 0.62 + 0.38 * max(0.0, float(n @ sun))
        if round(n[1]) == -1:
            shade = 0.5
        col = np.array([shade] * 3) if tint is None else shade * tint
        p = [(pos[0] + q[0] / 16, pos[1] + q[1] / 16, pos[2] + q[2] / 16) for q in quad]
        cxq = sum(q[0] for q in p) / 4 + n[0] * 0.3
        cyq = sum(q[1] for q in p) / 4 + n[1] * 0.3
        czq = sum(q[2] for q in p) / 4 + n[2] * 0.3
        li, lj, lk = int(math.floor(cxq)), int(math.floor(cyq)), int(math.floor(czq))
        lv = light[li, lj, lk] if 0 <= li < LW and 0 <= lj < LH and 0 <= lk < LD else 0
        if glow:
            ncol = (np.array([1.0, 1.0, 1.0]) if tint is None else tint) * 1.05
        else:
            b = (lv / 15.0) ** 1.4
            base_c = np.array([1.0, 1.0, 1.0]) if tint is None else tint
            ncol = base_c * (moon * (0.25 + 0.2 * max(0.0, float(n[1]))) + warm * b * 1.15) * (0.7 + 0.3 * shade)
        for (i, j, k) in ((0, 1, 2), (0, 2, 3)):
            tris.append((p[i], p[j], p[k]))
            uvs.append((uvq[i], uvq[j], uvq[k]))
            tids.append(tid)
            shades.append(col)
            nights.append(ncol)

    def get_name(x, y, z):
        if (x, y, z) in blocks:
            return blocks[(x, y, z)][0]
        if y == g.OY and (x, z) in extra_ground:
            return "minecraft:snow_block"
        return "minecraft:air"

    items = [(p, b[0], b[1]) for p, b in blocks.items() if b[0] != "minecraft:air"]
    items += [((x, g.OY, z), "minecraft:snow_block", {}) for (x, z) in extra_ground]
    for (x, y, z), name, props in items:
        if opaque(name) and all(opaque(get_name(x + d[0], y + d[1], z + d[2])) for d in DIRS.values()):
            continue
        variants = fake_model(name, props)
        if variants is None:
            variants = []
            for v in pick_models(assets, name, props):
                els, texs = M.model(v["model"])
                variants.append((els, texs, v.get("x", 0), v.get("y", 0)))
        tint = LEAF_TINT if "leaves" in name and name.startswith("minecraft:") else None
        glow = any(t in name for t in EMISSIVE) and props.get("lit", "true") != "false"
        for els, texs, rx, ry in variants:
            if not els:
                continue
            for e in els:
                a, b = e["from"], e["to"]
                for f, fd in e.get("faces", {}).items():
                    cf = fd.get("cullface")
                    if cf:
                        d = rot_dir(DIRS[cf], rx, ry)
                        if opaque(get_name(x + d[0], y + d[1], z + d[2])):
                            continue
                    quad = face_quad(f, a, b)
                    if "rotation" in e:
                        quad = [rot_elem(q, e["rotation"]) for q in quad]
                    quad = [rot_block(q, rx, ry) for q in quad]
                    u1, v1, u2, v2 = fd.get("uv", default_uv(f, a, b))
                    uvc = [(u1, v1), (u2, v1), (u2, v2), (u1, v2)]
                    k = (fd.get("rotation", 0) // 90) % 4
                    uvc = [uvc[(i - k) % 4] for i in range(4)]
                    tref = fd.get("texture", "")
                    tname = M.resolve(texs, tref) if texs else tref
                    tid = M.texture(tname)
                    nrm = np.cross(np.subtract(quad[1], quad[0]), np.subtract(quad[3], quad[0]))
                    t = tint if ("tintindex" in fd and tint is not None) else None
                    emit((x, y, z), quad, uvc, tid, -nrm, t, glow)
    return (np.array(tris, np.float64), np.array(uvs, np.float64), np.array(tids, np.int32),
            np.array(shades, np.float64), np.array(nights, np.float64))


def look_at(cam, target):
    f = np.subtract(target, cam).astype(float)
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return r, u, f


def render(scene, M, cam, target, out, w=1280, h=720, fov=70, ss=2, night=False):
    tris, uvs, tids, shades, nights = scene
    if night:
        shades = nights
    cam = (cam[0] + g.M, cam[1] + g.OY, cam[2] + g.M)
    target = (target[0] + g.M, target[1] + g.OY, target[2] + g.M)
    W2, H2 = w * ss, h * ss
    r, u, f = look_at(cam, target)
    rel = tris - np.array(cam)
    cx, cy, cz = rel @ r, rel @ u, rel @ f
    near = 0.15
    keep = (cz > near).all(axis=1)
    focal = (W2 / 2) / math.tan(math.radians(fov) / 2)
    sx = W2 / 2 + focal * cx / np.where(cz > near, cz, 1)
    sy = H2 / 2 - focal * cy / np.where(cz > near, cz, 1)
    inv = 1.0 / np.where(cz > near, cz, 1)
    color = np.zeros((H2, W2, 3), np.float64)
    zbuf = np.zeros((H2, W2), np.float64)  # 1/z, mayor = más cerca
    yy = np.linspace(0, 1, H2)[:, None]
    if night:
        sky = (np.array([0.01, 0.015, 0.05]) * (1 - yy) + np.array([0.06, 0.08, 0.16]) * yy)
    else:
        sky = (np.array([0.62, 0.72, 0.86]) * (1 - yy) + np.array([0.86, 0.89, 0.94]) * yy)
    color[:] = sky[:, None, :]
    if night:
        rs = np.random.RandomState(7)
        n_st = W2 * H2 // 900
        sy_, sx_ = rs.randint(0, H2 * 2 // 3, n_st), rs.randint(0, W2, n_st)
        color[sy_, sx_] = np.clip(rs.rand(n_st, 1) * 0.8 + 0.2, 0, 1)
    texs = M.tex_list
    for i in np.nonzero(keep)[0]:
        x0, y0 = sx[i], sy[i]
        minx, maxx = int(max(0, math.floor(x0.min()))), int(min(W2 - 1, math.ceil(x0.max())))
        miny, maxy = int(max(0, math.floor(y0.min()))), int(min(H2 - 1, math.ceil(y0.max())))
        if minx > maxx or miny > maxy:
            continue
        ax, bx, cxx = x0
        ay, by, cyy = y0
        area = (bx - ax) * (cyy - ay) - (by - ay) * (cxx - ax)
        if abs(area) < 1e-9:
            continue
        px = np.arange(minx, maxx + 1) + 0.5
        py = (np.arange(miny, maxy + 1) + 0.5)[:, None]
        w0 = ((bx - px) * (cyy - py) - (by - py) * (cxx - px)) / area
        w1 = ((cxx - px) * (ay - py) - (cyy - py) * (ax - px)) / area
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not m.any():
            continue
        iz = inv[i]
        z = w0 * iz[0] + w1 * iz[1] + w2 * iz[2]
        zb = zbuf[miny:maxy + 1, minx:maxx + 1]
        m &= z > zb
        if not m.any():
            continue
        uv = uvs[i]
        uu = (w0 * uv[0, 0] * iz[0] + w1 * uv[1, 0] * iz[1] + w2 * uv[2, 0] * iz[2]) / z
        vv = (w0 * uv[0, 1] * iz[0] + w1 * uv[1, 1] * iz[1] + w2 * uv[2, 1] * iz[2]) / z
        t = texs[tids[i]]
        th, tw = t.shape[:2]
        ti = np.clip((vv / 16 * th).astype(int), 0, th - 1)
        tj = np.clip((uu / 16 * tw).astype(int), 0, tw - 1)
        tx = t[ti, tj]
        m &= tx[..., 3] > 100
        if not m.any():
            continue
        zb[m] = z[m]
        color[miny:maxy + 1, minx:maxx + 1][m] = tx[..., :3][m] / 255.0 * shades[i]
    # niebla suave
    dist = np.where(zbuf > 0, 1 / np.maximum(zbuf, 1e-9), 1e9)
    fog = np.clip((dist - 90) / 160, 0, 0.7)[..., None] if not night else np.clip((dist - 160) / 300, 0, 0.45)[..., None]
    skyc = np.broadcast_to(sky[:, None, :], color.shape)
    color = np.where(zbuf[..., None] > 0, color * (1 - fog) + skyc * fog, color)
    img = Image.fromarray((np.clip(color, 0, 1) * 255).astype(np.uint8))
    if ss > 1:
        img = img.resize((w, h), Image.LANCZOS)
    img.save(out)
    print("  ", os.path.relpath(out, REPO))


# cámaras en coordenadas de la ciudadela (0..100); nombre_noche => foto nocturna
SHOTS = {
    "01_vista_aerea": ((175, 85, 195), (50, 4, 45), 55),
    "02_llegada_barbacana": ((50, 5, 140), (50, 10, 100), 70),
    "03_entrada_foso": ((88, 38, 148), (50, 3, 100), 55),
    "04_foso_helado": ((102, 0.7, 96), (102, 1, 45), 70),
    "05_puerto_drakkars": ((105, 9, 2), (122, 4, 50), 70),
    "06_drakkar_cerca": ((112, 4, 82), (121, 6, 68), 72),
    "07_vista_desde_spawn": ((50, 2.6, 87), (50, 15, 48), 80),
    "08_salon_interior": ((67, 8.5, 22), (30, 7, 22), 80),
    "09_noche_aerea": ((175, 85, 195), (50, 4, 45), 55),
    "10_noche_puerta": ((50, 5, 140), (50, 10, 100), 70),
    "11_noche_plaza": ((50, 2.6, 87), (50, 15, 48), 80),
    "12_noche_puerto": ((105, 9, 2), (122, 4, 50), 70),
    "13_noche_salon": ((67, 8.5, 22), (30, 7, 22), 80),
    "14_noche_taberna": ((37, 6, 69), (16, 4, 59), 75),
}


def main():
    client = (sys.argv[1] if len(sys.argv) > 1 else "") or next(
        (os.path.expanduser(p) for p in CLIENT_GUESSES if os.path.exists(os.path.expanduser(p))), None)
    if not client:
        sys.exit("No encuentro el client jar de 1.20.1; pásalo como argumento")
    mods = [glob.glob(os.path.join(REPO, "mods", pat))[0] for pat in
            ("fantasyfurniture-*.jar", "Quark-*.jar", "supplementaries-*.jar")]
    assets = Assets(mods + [client])
    M = Models(assets)
    ground = {(x, z) for x in range(-60, g.W + 60) for z in range(-60, g.D + 60)
              if not (0 <= x < g.W and 0 <= z < g.D)}
    print("construyendo geometría...")
    light = g.compute_light()
    scene = build_triangles(M, assets, g.blocks, ground, light)
    print(f"  {len(scene[0])} triángulos, {len(M.tex_list)} texturas")
    out = os.path.join(HERE, "salida", "fotos")
    os.makedirs(out, exist_ok=True)
    only = sys.argv[2:] if len(sys.argv) > 2 else SHOTS
    for name in only:
        cam, tgt, fov = SHOTS[name]
        render(scene, M, cam, tgt, os.path.join(out, name + ".png"), fov=fov, night="noche" in name)


if __name__ == "__main__":
    main()
