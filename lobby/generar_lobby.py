#!/usr/bin/env python3
"""Genera el lobby del servidor como estructura vanilla (.nbt) + vista previa.

Ciudadela nórdica de invierno (101 x 101 bloques): murallas con torres de
tejados nevados, puerta monumental con las letras KB, avenida, plaza con un
árbol de invierno gigante, gran palacio del jarl con dos torres, taberna,
herrería, mercado, círculo de piedras para el waystone y lago helado con agujas
de hielo. Usa Fantasy's Furniture (set Nordic + decoraciones), Supplementaries
y Quark además de vanilla.

    python3 lobby/generar_lobby.py
    python3 lobby/render_fotos.py      # fotos con texturas reales

Salida (en lobby/salida/):
    kb_lobby_datapack.zip   datapack con data/kb/structures/lobby.nbt
    lobby.nbt               la estructura suelta

Colocar en el mundo (161 x 53 x 161): de pie en el punto que será el centro,
    /function kb_lobby:colocar    (o colocar_90 / colocar_180 / colocar_270)
Pone también el spawn (justo dentro de la puerta, mirando al árbol) y un muro de
barrera alrededor que quita apertura:final. Se puede girar y deshacer: ver
datapack_lobby.py.
Alrededor de la ciudadela: foso helado, muralla exterior con barbacana, puerto
con drakkars al este y bosque. Lleva bloques de luz invisibles (nivel 11).
"""
import gzip
import io
import json
import math
import os
import random
import struct

import datapack_lobby

CORE = 101                    # ciudadela (muralla interior) en coordenadas 0..100
M = 30                        # margen exterior: foso, muralla exterior, puerto y bosque
OY = 3                        # capas bajo el suelo (foso y mar helado)
W, H, D = CORE + 2 * M, 53, CORE + 2 * M   # tamaño real de la estructura
DATA_VERSION = 3465           # 1.20.1
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salida")
rng = random.Random(2026)
SPAWN = (50, 1, 87)           # en coordenadas de la ciudadela; en la estructura: +(M, OY, M)

blocks = {}                   # (x,y,z) -> (name, props(dict), nbt or None)


def ns(name):
    return name if ":" in name else "minecraft:" + name


def S(x, y, z, name, nbt=None, **props):
    """Coloca un bloque. Coordenadas de la ciudadela: (0,0,0) = esquina NO del suelo de la muralla."""
    X, Y, Z = x + M, y + OY, z + M
    if not (0 <= X < W and 0 <= Y < H and 0 <= Z < D):
        return
    blocks[(X, Y, Z)] = (ns(name), {k: str(v).lower() for k, v in props.items()}, nbt)


def fill(x0, y0, z0, x1, y1, z1, name, **props):
    for x in range(min(x0, x1), max(x0, x1) + 1):
        for y in range(min(y0, y1), max(y0, y1) + 1):
            for z in range(min(z0, z1), max(z0, z1) + 1):
                S(x, y, z, name, **props)


def rawget(X, Y, Z):
    b = blocks.get((X, Y, Z))
    return b[0] if b else "minecraft:air"


def get(x, y, z):
    return rawget(x + M, y + OY, z + M)


def is_air(x, y, z):
    return get(x, y, z) == "minecraft:air"


FF = "fantasyfurniture:"
FFN = FF + "nordic/"
FFD = FF + "decorations/"
OPP = {"north": "south", "south": "north", "east": "west", "west": "east"}
DIRV = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


def stone(y=5):
    if y <= 2:
        return rng.choices(["cobblestone", "mossy_cobblestone", "stone_bricks"], [50, 25, 25])[0]
    return rng.choices(["stone_bricks", "cracked_stone_bricks", "mossy_stone_bricks"], [72, 14, 14])[0]


def sign_nbt(lines, hanging=False, color="white", glow=True):
    msgs = [json.dumps({"text": t}, ensure_ascii=False) for t in (lines + ["", "", "", ""])[:4]]
    side = {"messages": msgs, "color": color, "has_glowing_text": ("b", 1 if glow else 0)}
    return {"id": "minecraft:hanging_sign" if hanging else "minecraft:sign",
            "front_text": side, "back_text": side, "is_waxed": ("b", 1)}


SNOWFLAKE = {"id": "minecraft:banner", "Patterns": [
    {"Pattern": "sc", "Color": 0}, {"Pattern": "cr", "Color": 0},
    {"Pattern": "mc", "Color": 11}, {"Pattern": "bo", "Color": 3}]}


def snow_on(x, y, z, p=0.85, lo=1, hi=3):
    if is_air(x, y + 1, z) and rng.random() < p:
        S(x, y + 1, z, "snow", layers=rng.randint(lo, hi))


def lamp_post(x, z, h=3, base=1, arms=None):
    """Farola: pie de piedra, poste de abeto, remate y farolillos colgando de brazos."""
    S(x, base, z, "stone_brick_wall")
    fill(x, base + 1, z, x, base + h, z, "spruce_fence")
    if arms is None:
        S(x, base + h + 1, z, "lantern", hanging=False)
        S(x, base + h + 2, z, "snow", layers=1) if False else None
        return
    S(x, base + h + 1, z, "dark_oak_fence")
    S(x, base + h + 2, z, "dark_oak_slab", type="bottom")
    snow_on(x, base + h + 2, z, 1, 1, 1)
    for (dx, dz) in arms:
        S(x + dx, base + h + 1, z + dz, "dark_oak_fence")
        S(x + dx, base + h, z + dz, "lantern", hanging=True)


def corbel_ring(cells, y, center, mat="stone_brick_stairs", half="top"):
    """Ménsulas: escaleras invertidas mirando hacia el muro."""
    cx, cz = center
    for (x, z) in cells:
        dx, dz = x - cx, z - cz
        f = ("west" if dx > 0 else "east") if abs(dx) >= abs(dz) else ("north" if dz > 0 else "south")
        S(x, y, z, mat, facing=f, half=half, shape="straight")


def banner_pole(x, z, base=1, h=5):
    fill(x, base, z, x, base + h - 1, z, "dark_oak_fence")
    S(x, base + h, z, "blue_banner", nbt=SNOWFLAKE, rotation=rng.choice([0, 8]))


def spruce_tree(cx, cz, height, rmax, base=1, lights=False, trunk=1, first=2, garland=False):
    top = base + height
    for y in range(base, top - 1):
        S(cx, y, cz, "spruce_log", axis="y")
        if trunk > 1 and y < top - height // 3:
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                S(cx + dx, y, cz + dz, "spruce_log", axis="y")
    if trunk > 1:  # raíces
        for dx, dz in ((2, 0), (-2, 0), (0, 2), (0, -2), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            S(cx + dx, base, cz + dz, "spruce_wood", axis="y")
    lo = base + first
    seed = rng.random() * 6
    tier = 3 if rmax > 4 else 2
    for y in range(lo, top + 1):
        t = (top - y) / max(1, top - lo)
        r = rmax * t + 0.6
        phase = (top - y) % tier
        r -= phase * (0.9 if rmax > 4 else 0.7)
        r = max(r, 0.5 if y < top else 0.0)
        ri = int(math.ceil(r)) + 1
        for dx in range(-ri, ri + 1):
            for dz in range(-ri, ri + 1):
                ang = math.atan2(dz, dx)
                rr = r * (0.9 + 0.13 * math.sin(5 * ang + seed + y * 0.7)) if rmax > 3 else r
                if dx * dx + dz * dz <= rr * rr + 0.3 and is_air(cx + dx, y, cz + dz):
                    S(cx + dx, y, cz + dz, "spruce_leaves", persistent=True, distance=1)
                    # puntas de rama que caen en el borde de cada piso
                    if phase == 0 and rmax > 3 and dx * dx + dz * dz > (rr - 1.2) ** 2 and rng.random() < 0.35 \
                            and is_air(cx + dx, y - 1, cz + dz):
                        S(cx + dx, y - 1, cz + dz, "spruce_leaves", persistent=True, distance=1)
    if garland:  # dos guirnaldas en espiral
        for g_i, mat in enumerate(("red_wool", "gold_block")):
            per = 4
            steps = int((top - lo - 2) * per)
            for s in range(steps):
                y = lo + 1 + s / per
                a = s * 0.42 + g_i * math.pi
                yi = int(y)
                t = (top - yi) / max(1, top - lo)
                r = rmax * t + 0.2
                x, z = round(cx + r * math.cos(a)), round(cz + r * math.sin(a))
                for k in (0.0, -0.8):
                    xx, zz = round(cx + (r + k) * math.cos(a)), round(cz + (r + k) * math.sin(a))
                    if get(xx, yi, zz) == "minecraft:spruce_leaves":
                        S(xx, yi, zz, mat)
                        break
    S(cx, top, cz, "spruce_leaves", persistent=True, distance=1)
    cells = [(x, y, z) for x in range(cx - int(rmax) - 3, cx + int(rmax) + 4)
             for z in range(cz - int(rmax) - 3, cz + int(rmax) + 4) for y in range(lo - 1, top + 1)
             if get(x, y, z) == "minecraft:spruce_leaves"]
    if lights:
        for (x, y, z) in cells:
            if y < top - 1 and rng.random() < 0.05 and any(is_air(x + a, y, z + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                S(x, y, z, rng.choice(["shroomlight", "ochre_froglight", "pearlescent_froglight",
                                       "verdant_froglight", "gold_block", "redstone_block", "lapis_block"]))
    for (x, y, z) in cells:
        if get(x, y, z) == "minecraft:spruce_leaves" and is_air(x, y + 1, z) and rng.random() < 0.8:
            S(x, y + 1, z, "snow", layers=rng.choice([1, 1, 2]))
        if lights and get(x, y, z) == "minecraft:spruce_leaves" and is_air(x, y - 1, z) and y - 1 >= base + 2 \
                and rng.random() < 0.16:
            S(x, y - 1, z, "lantern", hanging=True)
    return top


def round_tower(cx, cz, r, h, roof_h, base=1, slits=True, floor_mat="spruce_planks"):
    """Torre redonda: zócalo ensanchado, impostas, ménsulas, galería de madera y
    chapitel cónico acampanado y nevado."""
    R = r + 0.5

    def ring(rad_in, rad_out):
        return [(x, z) for x in range(cx - r - 4, cx + r + 5) for z in range(cz - r - 4, cz + r + 5)
                if rad_in < math.hypot(x - cx, z - cz) <= rad_out]

    for y in range(base, h + 1):
        for x in range(cx - r - 1, cx + r + 2):
            for z in range(cz - r - 1, cz + r + 2):
                d = math.hypot(x - cx, z - cz)
                if d <= R:
                    if d > R - 1.2:
                        if (y - base) % 7 == 6:
                            S(x, y, z, "polished_andesite")       # imposta
                        else:
                            S(x, y, z, stone(y))
                    else:
                        S(x, y, z, "air")
    # zócalo ensanchado (talud)
    for (x, z) in ring(R - 0.2, R + 1):
        fill(x, base, z, x, base + 1, z, rng.choice(["cobblestone", "mossy_cobblestone", "stone_bricks"]))
    corbel_ring(ring(R - 0.2, R + 1), base + 2, (cx, cz), half="bottom")
    # ménsulas + galería de madera volada bajo el chapitel
    corbel_ring(ring(R - 0.2, R + 1), h - 1, (cx, cz))
    for (x, z) in ring(R - 0.2, R + 1):
        S(x, h, z, "spruce_planks")
    for (x, z) in ring(R - 0.2, R + 1):
        d = math.hypot(x - cx, z - cz)
        if d > R + 0.3:
            S(x, h + 1, z, "spruce_fence")
    for x in range(cx - r, cx + r + 1):
        for z in range(cz - r, cz + r + 1):
            if math.hypot(x - cx, z - cz) <= R - 0.5:
                S(x, h, z, floor_mat)
    # postes que sujetan el chapitel
    for k in range(8):
        a = k * math.pi / 4
        x, z = round(cx + (R + 0.4) * math.cos(a)), round(cz + (R + 0.4) * math.sin(a))
        fill(x, h + 1, z, x, h + 2, z, "dark_oak_log", axis="y")
    if slits:
        for yy in range(base + 4, h - 3, 7):
            for dx, dz, f in ((r, 0, "east"), (-r, 0, "west"), (0, r, "south"), (0, -r, "north")):
                S(cx + dx, yy, cz + dz, "glass_pane"); S(cx + dx, yy + 1, cz + dz, "glass_pane")
                S(cx + dx, yy + 2, cz + dz, "chiseled_stone_bricks")
    # chapitel cónico acampanado
    R0 = r + 2.3
    top_y = h + 3 + roof_h
    for k in range(roof_h + 1):
        y = h + 3 + k
        t = k / roof_h
        rk = R0 * (1 - t) ** 1.25
        for x in range(cx - r - 4, cx + r + 5):
            for z in range(cz - r - 4, cz + r + 5):
                d = math.hypot(x - cx, z - cz)
                if d <= rk + 0.01 and (d > rk - 1.6 or k == roof_h):
                    S(x, y, z, rng.choices(["dark_oak_planks", "spruce_planks", "dark_oak_planks"], [70, 15, 15])[0])
        if k == 0:
            for (x, z) in ring(rk - 1, rk + 0.01):
                if (x * 7 + z * 3) % 7 == 0:
                    S(x, y - 1, z, "lantern", hanging=True)
                else:
                    S(x, y - 1, z, "dark_oak_trapdoor", facing="north", half="top", open=False)
    for k in range(roof_h + 1):
        y = h + 3 + k
        for x in range(cx - r - 4, cx + r + 5):
            for z in range(cz - r - 4, cz + r + 5):
                if get(x, y, z) in ("minecraft:dark_oak_planks", "minecraft:spruce_planks"):
                    snow_on(x, y, z, 0.85, 2, 6)
    fill(cx, top_y + 1, cz, cx, top_y + 2, cz, "dark_oak_fence")
    S(cx, top_y + 2, cz, "dark_oak_log", axis="y")
    S(cx, top_y + 3, cz, "blue_banner", nbt=SNOWFLAKE, rotation=0)


def gable_roof(x0, x1, z0, z1, axis, base, mat="dark_oak_planks", snow=True):
    """Tejado escalonado a dos aguas con nieve. axis = dirección de la cumbrera."""
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            off = min(z - z0, z1 - z) if axis == "x" else min(x - x0, x1 - x)
            y = base + off
            gable_edge = (x in (x0, x1)) if axis == "x" else (z in (z0, z1))
            if gable_edge:
                S(x, y, z, "dark_oak_log", axis="x" if axis == "x" else "z") if off else S(x, y, z, mat)
                # tabla de alero (bargeboard) bajo el borde del hastial
                if axis == "x":
                    S(x, y - 1, z, "dark_oak_stairs", facing="east" if x == x0 else "west", half="top", shape="straight")
                else:
                    S(x, y - 1, z, "dark_oak_stairs", facing="south" if z == z0 else "north", half="top", shape="straight")
            else:
                S(x, y, z, rng.choices([mat, "spruce_planks", "dark_oak_planks"], [72, 16, 12])[0])
            if off == 0:
                if axis == "x":
                    S(x, y - 1, z, "dark_oak_stairs", facing="north" if z == z0 else "south", half="top", shape="straight")
                else:
                    S(x, y - 1, z, "dark_oak_stairs", facing="west" if x == x0 else "east", half="top", shape="straight")
                if (x + z) % 5 == 0 and is_air(x, y - 2, z):
                    S(x, y - 2, z, "lantern", hanging=True) if rng.random() < 0.5 else None
    if snow:
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                off = min(z - z0, z1 - z) if axis == "x" else min(x - x0, x1 - x)
                snow_on(x, base + off, z, 0.88, 2, 5)


def gable_fill(axis, fixed, a0, a1, base, wall_top, roof_base, roof_a0, roof_a1, mat="spruce_planks"):
    """Rellena el hastial (triángulo) bajo un tejado. axis: eje del muro hastial."""
    for a in range(a0, a1 + 1):
        top = roof_base + min(a - roof_a0, roof_a1 - a)
        for y in range(wall_top + 1, top):
            if axis == "x":
                S(fixed, y, a, mat)
            else:
                S(a, y, fixed, mat)


def ice_spike(cx, cz, h, r, base=1):
    for y in range(base, base + h):
        t = (y - base) / h
        rr = r * (1 - t) ** 0.9 + 0.3
        ri = int(math.ceil(rr))
        for dx in range(-ri, ri + 1):
            for dz in range(-ri, ri + 1):
                if dx * dx + dz * dz <= rr * rr:
                    S(cx + dx, y, cz + dz, "blue_ice" if rng.random() < 0.3 else "packed_ice")


def path_tile(x, z, edge=False):
    if edge:
        S(x, 0, z, "polished_andesite")
    else:
        S(x, 0, z, rng.choices(["stone_bricks", "cracked_stone_bricks", "mossy_stone_bricks", "cobblestone"],
                               [70, 12, 10, 8])[0])


def window(axis, fixed, a0, a1, y0, y1):
    for a in range(a0, a1 + 1):
        for y in range(y0, y1 + 1):
            if axis == "x":
                S(a, y, fixed, "glass_pane")
            else:
                S(fixed, y, a, "glass_pane")


def framed_window(axis, fixed, a0, a1, y0, y1, out, shutters=True, sill="spruce_stairs", hood=True):
    """Ventana con contraventanas abiertas, alféizar nevado y tejadillo.
    axis: eje a lo largo del muro; out: dirección hacia fuera (north/south/east/west)."""
    window(axis, fixed, a0, a1, y0, y1)
    o = {"north": -1, "south": 1, "west": -1, "east": 1}[out]

    def P(a, y):
        return (a, y, fixed + o) if axis == "x" else (fixed + o, y, a)

    for a in range(a0, a1 + 1):
        x, y, z = P(a, y0 - 1)
        S(x, y, z, sill, facing=OPP[out], half="top", shape="straight")
        snow_on(x, y, z, 0.7, 1, 1)
        if hood:
            x, y, z = P(a, y1 + 1)
            S(x, y, z, "spruce_trapdoor", facing=out, half="bottom", open=False)
    if shutters:
        for a in (a0 - 1, a1 + 1):
            for y in range(y0, y1 + 1):
                x, yy, z = P(a, y)
                S(x, yy, z, "spruce_trapdoor", facing=out, half="bottom", open=True)


def dormer(x, z_front, base_y, out, w=1):
    """Buhardilla en un faldón (cumbrera a lo largo de x). out: north/south."""
    sgn = -1 if out == "north" else 1
    depth = 4
    zs = [z_front - sgn * k for k in range(depth)]
    for z in zs:
        for dx in range(-w - 1, w + 2):
            for y in range(base_y, base_y + 3):
                edge = abs(dx) == w + 1
                if z == z_front or edge:
                    S(x + dx, y, z, "spruce_planks")
                else:
                    S(x + dx, y, z, "air")
    for dx in (-w - 1, w + 1):
        fill(x + dx, base_y, z_front, x + dx, base_y + 2, z_front, "dark_oak_log", axis="y")
    framed_window("x", z_front, x - w, x + w, base_y + 1, base_y + 1, out, shutters=False, hood=False)
    z0, z1 = sorted((z_front + sgn, z_front - sgn * (depth - 1)))
    gable_roof(x - w - 2, x + w + 2, z0, z1, "z", base_y + 3)
    for y in range(base_y + 3, base_y + 3 + w + 2):
        for dx in range(-w - 1 + (y - base_y - 3), w + 2 - (y - base_y - 3)):
            if get(x + dx, y, z_front) == "minecraft:air":
                S(x + dx, y, z_front, "spruce_planks")


def nordic_house(x0, z0, x1, z1, wall_top, door_side, door_pos, base=1):
    """Casa nórdica con cumbrera a lo largo del lado largo. Devuelve y del suelo interior."""
    fill(x0 - 1, 0, z0 - 1, x1 + 1, 0, z1 + 1, "cobblestone")
    fill(x0 + 1, base, z0 + 1, x1 - 1, base, z1 - 1, "spruce_planks")
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if x in (x0, x1) or z in (z0, z1):
                for y in range(base, wall_top + 1):
                    if y <= base + 1:
                        S(x, y, z, stone(5))
                    elif y == wall_top:
                        S(x, y, z, "dark_oak_log", axis="x" if z in (z0, z1) else "z")
                    else:
                        S(x, y, z, "spruce_planks")
    for (x, z) in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
        fill(x, base, z, x, wall_top, z, "dark_oak_log", axis="y")
    # entramado: banda horizontal y riostras
    for x in range(x0 + 1, x1):
        for z in (z0, z1):
            S(x, base + 2, z, "stripped_dark_oak_log", axis="x")
    for z in range(z0 + 1, z1):
        for x in (x0, x1):
            S(x, base + 2, z, "stripped_dark_oak_log", axis="z")
    for x in range(x0 + 4, x1 - 1, 4):
        fill(x, base + 2, z0, x, wall_top, z0, "dark_oak_log", axis="y")
        fill(x, base + 2, z1, x, wall_top, z1, "dark_oak_log", axis="y")
        for z, out in ((z0, "north"), (z1, "south")):
            framed_window("x", z, x - 2, x - 1, base + 3, base + 4, out)
    for z in range(z0 + 4, z1 - 1, 4):
        for x, out in ((x0, "west"), (x1, "east")):
            fill(x, base + 2, z, x, wall_top, z, "dark_oak_log", axis="y")
            framed_window("z", x, z - 2, z - 1, base + 3, base + 4, out)
    # zócalo con talud
    for x in range(x0 - 1, x1 + 2):
        for z in (z0 - 1, z1 + 1):
            S(x, base, z, "stone_brick_stairs", facing="south" if z == z0 - 1 else "north", half="bottom", shape="straight")
    for z in range(z0, z1 + 1):
        for x in (x0 - 1, x1 + 1):
            S(x, base, z, "stone_brick_stairs", facing="east" if x == x0 - 1 else "west", half="bottom", shape="straight")
    long_x = (x1 - x0) >= (z1 - z0)
    if long_x:
        gable_roof(x0 - 1, x1 + 1, z0 - 1, z1 + 1, "x", wall_top)
        for x in (x0, x1):
            gable_fill("x", x, z0 + 1, z1 - 1, base, wall_top, wall_top, z0 - 1, z1 + 1)
    else:
        gable_roof(x0 - 1, x1 + 1, z0 - 1, z1 + 1, "z", wall_top)
        for z in (z0, z1):
            gable_fill("z", z, x0 + 1, x1 - 1, base, wall_top, wall_top, x0 - 1, x1 + 1)
    # puerta (hueco 2 de ancho) con tejadillo, farolillos y escalón
    if door_side in ("east", "west"):
        x = x1 if door_side == "east" else x0
        fill(x, base + 1, door_pos, x, base + 3, door_pos + 1, "air")
        S(x, base, door_pos, "spruce_planks"); S(x, base, door_pos + 1, "spruce_planks")
        sg = 1 if door_side == "east" else -1
        out = x + sg
        S(out, base, door_pos, "spruce_stairs", facing=OPP[door_side], half="bottom", shape="straight")
        S(out, base, door_pos + 1, "spruce_stairs", facing=OPP[door_side], half="bottom", shape="straight")
        S(out, base + 3, door_pos - 1, FFN + "wall_light", facing=door_side)
        S(out, base + 3, door_pos + 2, FFN + "wall_light", facing=door_side)
        for z in range(door_pos - 1, door_pos + 3):
            S(out, base + 4, z, "dark_oak_stairs", facing=OPP[door_side], half="bottom", shape="straight")
            S(out + sg, base + 4, z, "dark_oak_slab", type="bottom") if False else None
            S(out, base + 4 - 1, z, "dark_oak_trapdoor", facing=door_side, half="top", open=False) \
                if z in (door_pos, door_pos + 1) else None
            snow_on(out, base + 4, z, 0.0)
        for z in (door_pos - 1, door_pos + 2):
            S(out, base + 3, z, FFN + "wall_light", facing=door_side)
    else:
        z = z1 if door_side == "south" else z0
        fill(door_pos, base + 1, z, door_pos + 1, base + 3, z, "air")
        out = z + (1 if door_side == "south" else -1)
        S(door_pos - 1, base + 3, out, FFN + "wall_light", facing=door_side)
        S(door_pos + 2, base + 3, out, FFN + "wall_light", facing=door_side)
    return base + 1


# ================================================================ SUELO
for x in range(-M, CORE + M):
    for z in range(-M, CORE + M):
        S(x, -3, z, "stone"); S(x, -2, z, "dirt"); S(x, -1, z, "dirt")
        S(x, 0, z, "snow_block")
        if rng.random() < 0.05:
            S(x, 0, z, rng.choice(["packed_ice", "coarse_dirt", "gravel", "podzol"]))

# ================================================================ MURALLA
C = 50


def inward(x, z):
    """Dirección (facing) que apunta hacia el interior de la ciudadela desde el anillo."""
    dx, dz = x - C, z - C
    if abs(dx) >= abs(dz):
        return "west" if dx > 0 else "east"
    return "north" if dz > 0 else "south"


for x in range(W):
    for z in range(D):
        m = max(abs(x - C), abs(z - C))
        along = z if abs(x - C) >= abs(z - C) else x       # coordenada a lo largo del lienzo
        if 44 <= m <= 46:
            for y in range(1, 10):
                S(x, y, z, stone(y) if not (y == 6 and m == 46) else "polished_andesite")
            S(x, 9, z, "spruce_planks" if m == 45 else "stone_bricks")       # adarve de madera
            if m == 44:
                S(x, 10, z, "stone_brick_wall")
        elif m == 47:
            # matacán: ménsulas + parapeto volado + almenas
            S(x, 8, z, "stone_brick_stairs", facing=inward(x, z), half="top", shape="straight")
            S(x, 9, z, "stone_bricks"); S(x, 10, z, stone(9))
            if along % 3 != 0:
                S(x, 11, z, stone(9)); snow_on(x, 11, z, 0.9, 1, 3)
            else:
                S(x, 11, z, "stone_brick_slab", type="bottom")
            if along % 8 == 4:          # contrafuerte
                fill(x, 1, z, x, 7, z, "stone_bricks")
                S(x, 1, z, "mossy_cobblestone")
            elif along % 8 in (3, 5):
                S(x, 1, z, "cobblestone"); S(x, 2, z, "stone_brick_stairs", facing=inward(x, z), half="bottom",
                                              shape="straight")
            else:
                S(x, 1, z, "stone_brick_stairs", facing=inward(x, z), half="bottom", shape="straight")
        elif m == 48 and along % 8 == 4:
            fill(x, 1, z, x, 3, z, "stone_bricks")
            S(x, 4, z, "stone_brick_stairs", facing=inward(x, z), half="bottom", shape="straight")
            S(x, 1, z, "mossy_cobblestone")
        elif m == 43:
            # cara interior: pilastras de roble oscuro y arcos ciegos
            if along % 10 == 0 and 8 < along < 92:
                fill(x, 1, z, x, 9, z, "dark_oak_log", axis="y")
                S(x, 10, z, "stone_brick_wall")
                f = inward(x, z)
                dx, dz = DIRV[f]
                S(x + dx, 6, z + dz, FFN + "wall_light", facing=f)
            elif along % 10 in (1, 9) and 8 < along < 92:
                S(x, 8, z, "stone_brick_stairs", facing=OPP[inward(x, z)], half="top", shape="straight")
            elif 8 < along < 92 and along % 10 in (4, 5, 6):
                S(x, 1, z, "stone_brick_stairs", facing=inward(x, z), half="bottom", shape="straight")
# faroles en el adarve
for x in range(W):
    for z in range(D):
        if max(abs(x - C), abs(z - C)) == 46 and (x + z) % 9 == 0:
            S(x, 10, z, "lantern", hanging=False)
        elif max(abs(x - C), abs(z - C)) == 45 and (x + z) % 9 == 4 and is_air(x, 10, z):
            S(x, 10, z, "snow", layers=1)

# ================================================================ TORRES DE ESQUINA
for (tx, tz) in ((5, 5), (95, 5), (5, 95), (95, 95)):
    round_tower(tx, tz, 6, 18, 13)

# ================================================================ PUERTA MONUMENTAL
GX0, GX1 = 43, 57
fill(GX0, 1, 91, GX1, 18, 98, "stone_bricks")
for x in range(GX0, GX1 + 1):
    for z in range(91, 99):
        for y in range(1, 19):
            S(x, y, z, stone(y))
gable_roof(GX0 - 1, GX1 + 1, 90, 99, "x", 19)
for x in (GX0, GX1):
    gable_fill("x", x, 91, 98, 1, 18, 19, 90, 99, "spruce_planks")
# arco con dovelas, rastrillo levantado y pilastras
for x in range(45, 56):
    top = 7 + int(math.sqrt(max(0, 5.6 ** 2 - (x - 50) ** 2)))
    for z in range(91, 99):
        fill(x, 1, z, x, top, z, "air")
    for z in (91, 98):
        S(x, top + 1, z, "chiseled_stone_bricks" if x % 2 == 0 else "polished_andesite")
    S(x, top, 94, "iron_bars"); S(x, top - 1, 94, "iron_bars")
    S(x, top, 95, "dark_oak_slab", type="top")
for x in range(45, 56):
    for z in range(91, 99):
        path_tile(x, z, edge=x in (45, 55))
for x in (44, 56):
    for z in (99, 90):
        fill(x, 1, z, x, 11, z, "stone_bricks")
        S(x, 1, z, "mossy_cobblestone")
        S(x, 6, z, "chiseled_stone_bricks")
        S(x, 1, z + (1 if z == 99 else -1), "stone_brick_stairs", facing="north" if z == 99 else "south",
          half="bottom", shape="straight")
for z in (92, 97):
    S(50, 12, z, "chain", axis="y")
    S(50, 11, z, "lantern", hanging=True)
# panel de las letras: fondo de pizarra pulida con marco de roble oscuro
for x in range(45, 56):
    for y in range(13, 19):
        S(x, y, 98, "polished_deepslate")
for x in range(44, 57):
    S(x, 12, 99, "dark_oak_log", axis="x")
    S(x, 19, 99, "dark_oak_log", axis="x") if False else None
for y in range(12, 19):
    S(44, y, 99, "dark_oak_log", axis="y"); S(56, y, 99, "dark_oak_log", axis="y")
S(50, 11, 99, "spruce_hanging_sign", rotation=0, attached=False,
  nbt=sign_nbt(["¡Bienvenido/a!", "KB Server", "Invierno 2026", "Terramity Awakened"], hanging=True, color="light_blue"))
for x in (47, 53):
    S(x, 11, 99, "lantern", hanging=True)
# letras KB en oro
FONT = {"K": ["X..X", "X.X.", "XX..", "X.X.", "X..X"], "B": ["XXX.", "X..X", "XXX.", "X..X", "XXX."]}
for li, ch in enumerate("KB"):
    for row, line in enumerate(FONT[ch]):
        for col, c in enumerate(line):
            if c == "X":
                S(46 + li * 5 + col, 18 - row, 98, "gold_block")
for x in (43, 57):
    S(x, 17, 99, "blue_wall_banner", nbt=SNOWFLAKE, facing="south")
for x in (44, 56):
    S(x, 17, 89, "blue_wall_banner", nbt=SNOWFLAKE, facing="north")
for x in range(45, 56):
    if x != 50:
        S(x, 18, 99, FFD + ("fairy_lights_1" if x % 2 else "fairy_lights_2"), facing="south")
for tx in (37, 63):
    round_tower(tx, 95, 6, 23, 15)
    for y in (9, 15):
        S(tx, y, 88, FFN + "wall_light", facing="north")

# ================================================================ AVENIDA
for z in range(44, 91):
    for x in range(44, 57):
        path_tile(x, z, edge=x in (44, 56))
    if z % 4 == 0:
        S(50, 0, z, "chiseled_stone_bricks")
for z in (84, 89):
    if 44 <= z <= 82 and abs(z - 63) < 20:
        continue
    lamp_post(43, z, 4, arms=[(1, 0)]); lamp_post(57, z, 4, arms=[(-1, 0)])
for z in (86,):
    banner_pole(42, z); banner_pole(58, z)
for (x, z) in ((40, 84), (60, 84)):
    spruce_tree(x, z, 9, 2.6, lights=True)

# ================================================================ PLAZA DEL ÁRBOL GIGANTE
TX, TZ, PR = 50, 63, 19
for x in range(TX - PR - 1, TX + PR + 2):
    for z in range(TZ - PR - 1, TZ + PR + 2):
        d = math.hypot(x - TX, z - TZ)
        if d > PR + 0.5:
            continue
        ang = math.atan2(z - TZ, x - TX)
        radial = min(abs(math.sin(ang - k * math.pi / 4)) for k in range(8)) * d < 0.6
        if d <= 4.6:
            S(x, 0, z, "podzol")
        elif abs(d - PR) < 0.6 or abs(d - 9) < 0.5:
            S(x, 0, z, "polished_andesite")
        elif radial and d > 5:
            S(x, 0, z, "chiseled_stone_bricks")
        elif int(d) % 4 == 0:
            S(x, 0, z, "polished_andesite")
        else:
            path_tile(x, z)
# jardinera elevada
for x in range(TX - 6, TX + 7):
    for z in range(TZ - 6, TZ + 7):
        d = math.hypot(x - TX, z - TZ)
        if 4.6 < d <= 5.6:
            S(x, 1, z, "stone_bricks")
            S(x, 2, z, "stone_brick_slab", type="bottom")
        elif d <= 4.6:
            S(x, 1, z, "podzol")
spruce_tree(TX, TZ, 38, 10.5, base=2, lights=True, trunk=3, first=6, garland=True)
# estrella
SY = 2 + 38 + 1
S(TX, SY, TZ, "glowstone"); S(TX, SY + 1, TZ, "gold_block"); S(TX, SY + 2, TZ, "glowstone")
for f, (dx, dz) in (("east", (1, 0)), ("west", (-1, 0)), ("south", (0, 1)), ("north", (0, -1))):
    S(TX + dx, SY + 1, TZ + dz, "gold_block")
    S(TX + 2 * dx, SY + 1, TZ + 2 * dz, "end_rod", facing=f)
S(TX, SY + 3, TZ, "end_rod", facing="up")
# regalos bajo el árbol
colors = ["red", "blue", "light_blue", "white", "green", "yellow", "purple", "orange"]
for x in range(TX - 5, TX + 6):
    for z in range(TZ - 5, TZ + 6):
        d = math.hypot(x - TX, z - TZ)
        if 1.6 < d <= 4.4 and is_air(x, 2, z):
            r = rng.random()
            if r < 0.4:
                S(x, 2, z, "supplementaries:present_" + rng.choice(colors), packed=True)
            elif r < 0.65:
                S(x, 2, z, FFD + rng.choice(["presents_stack_1", "presents_stack_2"]),
                  facing=rng.choice(list(OPP)), presents=rng.choice([0, 1]))
# bancos en anillo mirando al árbol
for x in range(TX - 16, TX + 17):
    for z in range(TZ - 16, TZ + 17):
        d = math.hypot(x - TX, z - TZ)
        if 13.5 < d <= 14.5:
            ang = math.degrees(math.atan2(z - TZ, x - TX)) % 90
            if 18 < ang < 72:
                dx, dz = x - TX, z - TZ
                facing = ("east" if dx > 0 else "west") if abs(dx) >= abs(dz) else ("south" if dz > 0 else "north")
                S(x, 1, z, "spruce_stairs", facing=facing, half="bottom", shape="straight")
for k in range(12):
    a = math.radians(15 + 30 * k)
    lamp_post(round(TX + 16.5 * math.cos(a)), round(TZ + 16.5 * math.sin(a)), 4)
for k in range(4):
    a = math.radians(45 + 90 * k)
    x, z = round(TX + 11 * math.cos(a)), round(TZ + 11 * math.sin(a))
    S(x, 1, z, FFD + "snowballs", facing="south", snowballs=3)

# ================================================================ PALACIO DEL JARL
HX0, HX1, HZ0, HZ1 = 26, 74, 11, 33     # muros
FLOOR = 3                                # bloque de suelo; se pisa en y=4
WALL_TOP = 15
# zócalo
for x in range(22, 79):
    for z in range(7, 37):
        for y in range(1, FLOOR + 1):
            S(x, y, z, stone(y))
        S(x, 0, z, "cobblestone")
for x in range(38, 63):
    for z in range(37, 41):
        for y in range(1, FLOOR + 1):
            S(x, y, z, stone(y))
# escalinata
for x in range(40, 61):
    S(x, 3, 41, "stone_brick_stairs", facing="north", half="bottom", shape="straight")
    S(x, 2, 41, "stone_bricks"); S(x, 1, 41, "stone_bricks")
    S(x, 2, 42, "stone_brick_stairs", facing="north", half="bottom", shape="straight")
    S(x, 1, 42, "stone_bricks")
    S(x, 1, 43, "stone_brick_stairs", facing="north", half="bottom", shape="straight")
for x in (39, 61):
    for z, top in ((41, 4), (42, 3), (43, 2)):
        fill(x, 1, z, x, top, z, "stone_bricks")
# braseros
for x in (36, 64):
    fill(x, 1, 42, x, 5, 42, "stone_bricks")
    S(x, 6, 42, "campfire", facing="south", lit=True, signal_fire=False)
    for dx, dz, f in ((1, 0, "east"), (-1, 0, "west"), (0, 1, "south"), (0, -1, "north")):
        S(x + dx, 5, 42 + dz, "stone_brick_stairs", facing=OPP[f], half="top", shape="straight")
fill(HX0 + 1, FLOOR, HZ0 + 1, HX1 - 1, FLOOR, HZ1 - 1, "spruce_planks")
for x in range(HX0 + 1, HX1):
    for z in range(HZ0 + 1, HZ1):
        if x in (HX0 + 1, HX1 - 1) or z in (HZ0 + 1, HZ1 - 1, 16, 28):
            S(x, FLOOR, z, "dark_oak_planks")
        elif (x - HX0) % 6 == 0:
            S(x, FLOOR, z, "stripped_spruce_wood", axis="x")
PXS = list(range(HX0, HX1 + 1, 6))       # 26..74
LOW_TOP = FLOOR + 7                      # planta baja de piedra hasta y=10
# muros largos: planta baja de piedra + planta alta de entramado volada 1 bloque
for z, out in ((HZ0, "north"), (HZ1, "south")):
    o = -1 if out == "north" else 1
    zu = z + o
    for x in range(HX0, HX1 + 1):
        for y in range(FLOOR + 1, LOW_TOP + 1):
            S(x, y, z, stone(y) if y < LOW_TOP else "polished_andesite")
        S(x, LOW_TOP, zu, "dark_oak_stairs", facing=OPP[out], half="top", shape="straight")   # ménsulas
        S(x, LOW_TOP + 1, zu, "dark_oak_log", axis="x")
        for y in range(LOW_TOP + 2, WALL_TOP):
            S(x, y, zu, "stripped_spruce_log" if x % 2 else "spruce_planks", **({"axis": "y"} if x % 2 else {}))
        S(x, WALL_TOP, zu, "dark_oak_log", axis="x")
        S(x, LOW_TOP + 1, z, "air"); S(x, LOW_TOP + 1, z, "candle", candles=rng.randint(1, 3), lit=True) \
            if rng.random() < 0.12 else None
    for x in PXS:
        fill(x, LOW_TOP + 1, zu, x, WALL_TOP, zu, "dark_oak_log", axis="y")
        # contrafuerte de piedra
        fill(x, FLOOR + 1, zu, x, LOW_TOP - 2, zu, "stone_bricks")
        S(x, LOW_TOP - 1, zu, "stone_brick_stairs", facing=OPP[out], half="bottom", shape="straight")
        fill(x, FLOOR + 1, zu + o, x, FLOOR + 2, zu + o, "stone_bricks")
        S(x, FLOOR + 3, zu + o, "stone_brick_stairs", facing=OPP[out], half="bottom", shape="straight")
        S(x, FLOOR + 4, zu + o, FFN + "wall_light", facing=out)
    for x in PXS[:-1]:
        # ventanal en arco de la planta baja
        framed_window("x", z, x + 2, x + 4, FLOOR + 2, FLOOR + 5, out, shutters=False, sill="stone_brick_stairs",
                      hood=False)
        S(x + 2, FLOOR + 6, z, "stone_brick_stairs", facing="east", half="top", shape="straight")
        S(x + 3, FLOOR + 6, z, "glass_pane")
        S(x + 4, FLOOR + 6, z, "stone_brick_stairs", facing="west", half="top", shape="straight")
        S(x + 3, FLOOR + 7, z, "chiseled_stone_bricks")
        # ventana de la planta alta con contraventanas
        framed_window("x", zu, x + 2, x + 4, LOW_TOP + 2, LOW_TOP + 3, out)
        # riostras diagonales a los lados
        S(x + 1, LOW_TOP + 4, zu, "dark_oak_stairs", facing="west", half="top", shape="straight")
        S(x + 5, LOW_TOP + 4, zu, "dark_oak_stairs", facing="east", half="top", shape="straight")
# muros hastiales (oeste y este)
for x, out in ((HX0, "west"), (HX1, "east")):
    for z in range(HZ0 - 1, HZ1 + 2):
        for y in range(FLOOR + 1, WALL_TOP + 1):
            if y <= LOW_TOP:
                if HZ0 <= z <= HZ1:
                    S(x, y, z, stone(y) if y < LOW_TOP else "polished_andesite")
            elif y in (LOW_TOP + 1, WALL_TOP):
                S(x, y, z, "dark_oak_log", axis="z")
            else:
                S(x, y, z, "stripped_spruce_log" if z % 2 else "spruce_planks", **({"axis": "y"} if z % 2 else {}))
    for z in (HZ0 - 1, 16, 22, 28, HZ1 + 1):
        fill(x, LOW_TOP + 1, z, x, WALL_TOP, z, "dark_oak_log", axis="y")
    for z0 in (12, 29):
        framed_window("z", x, z0 + 1, z0 + 2, FLOOR + 2, FLOOR + 5, out, shutters=False, sill="stone_brick_stairs",
                      hood=False)
        framed_window("z", x, z0 + 1, z0 + 2, LOW_TOP + 2, LOW_TOP + 3, out)
# tejado principal (cumbrera en z=22) con buhardillas
gable_roof(HX0 - 1, HX1 + 1, HZ0 - 2, HZ1 + 2, "x", WALL_TOP)
RIDGE_Y = WALL_TOP + 13
for x in (HX0, HX1):
    gable_fill("x", x, HZ0 - 1, HZ1 + 1, FLOOR, WALL_TOP, WALL_TOP, HZ0 - 2, HZ1 + 2)
    fill(x, WALL_TOP + 1, 22, x, RIDGE_Y - 1, 22, "dark_oak_log", axis="y")
    for z in range(HZ0, HZ1 + 1):
        S(x, WALL_TOP + 1, z, "dark_oak_log", axis="z")
for x in (32, 44, 56, 68):
    dormer(x, 13, WALL_TOP + 5, "north")
for x in (32, 68):
    dormer(x, 31, WALL_TOP + 5, "south")
# rosetón en el hastial oeste (sobre el trono) y ventana en el este
for z in range(14, 31):
    for y in range(WALL_TOP + 1, RIDGE_Y):
        d = math.hypot(z - 22, y - (WALL_TOP + 5))
        if d <= 4.5:
            S(HX0, y, z, "light_blue_stained_glass_pane" if d > 3.4 else
              ("white_stained_glass_pane" if (z + y) % 2 else "glass_pane"))
        elif d <= 5.4:
            S(HX0, y, z, "dark_oak_planks")
# cuernos nórdicos
for x in (HX0 - 1, HX1 + 1):
    S(x, RIDGE_Y + 1, 22, "dark_oak_log", axis="y")
    S(x, RIDGE_Y + 2, 21, "dark_oak_log", axis="y"); S(x, RIDGE_Y + 2, 23, "dark_oak_log", axis="y")
    S(x, RIDGE_Y + 3, 20, "dark_oak_log", axis="y"); S(x, RIDGE_Y + 3, 24, "dark_oak_log", axis="y")
    S(x, RIDGE_Y + 4, 19, "dark_oak_fence"); S(x, RIDGE_Y + 4, 25, "dark_oak_fence")
# pórtico de entrada (cumbrera a lo largo de z)
PX0, PX1, PZ1 = 42, 58, 39
P_TOP = 17
for x in range(PX0, PX1 + 1):
    for z in range(HZ1 - 1, PZ1 + 1):
        if x in (PX0, PX1) or z == PZ1:
            for y in range(FLOOR + 1, P_TOP + 1):
                if y < LOW_TOP:
                    S(x, y, z, stone(y))
                elif y == LOW_TOP:
                    S(x, y, z, "polished_andesite")
                elif y in (LOW_TOP + 1, P_TOP):
                    S(x, y, z, "dark_oak_log", axis="x" if z == PZ1 else "z")
                else:
                    S(x, y, z, "stripped_spruce_log" if (x + z) % 2 else "spruce_planks",
                      **({"axis": "y"} if (x + z) % 2 else {}))
        elif z > HZ1 - 1 or True:
            S(x, FLOOR, z, "spruce_planks")
            for y in range(FLOOR + 1, P_TOP + 1):
                S(x, y, z, "air")
for (x, z) in ((PX0, PZ1), (PX1, PZ1), (PX0, 36), (PX1, 36)):
    fill(x, LOW_TOP + 1, z, x, P_TOP, z, "dark_oak_log", axis="y")
    # contrafuertes en las esquinas del pórtico
    o = 1 if x == PX1 else -1
    fill(x + o, FLOOR + 1, z, x + o, LOW_TOP - 1, z, "stone_bricks")
    S(x + o, LOW_TOP, z, "stone_brick_stairs", facing="west" if o > 0 else "east", half="bottom", shape="straight")
for x in (PX0, PX1):
    framed_window("z", x, 35, 36, LOW_TOP + 2, LOW_TOP + 4, "east" if x == PX1 else "west")
gable_roof(PX0 - 1, PX1 + 1, HZ1 - 2, PZ1 + 1, "z", P_TOP)
gable_fill("z", PZ1, PX0 + 1, PX1 - 1, FLOOR, P_TOP, P_TOP, PX0 - 1, PX1 + 1)
# puerta grande en arco
for x in range(47, 54):
    top = FLOOR + 7 + int(math.sqrt(max(0, 3.6 ** 2 - (x - 50) ** 2)))
    for z in (HZ1, PZ1):
        fill(x, FLOOR + 1, z, x, top, z, "air")
        S(x, top + 1, z, "dark_oak_planks")
for x in (46, 54):
    fill(x, FLOOR + 1, PZ1, x, FLOOR + 8, PZ1, "dark_oak_log", axis="y")
# rosetón del pórtico
for x in range(PX0 + 1, PX1):
    for y in range(P_TOP + 1, P_TOP + 10):
        d = math.hypot(x - 50, y - (P_TOP + 4))
        if d <= 3.5:
            S(x, y, PZ1, "light_blue_stained_glass_pane" if d > 2.4 else "glass_pane")
        elif d <= 4.4 and get(x, y, PZ1) != "minecraft:air":
            S(x, y, PZ1, "dark_oak_planks")
for x in (44, 56):
    S(x, 14, PZ1 + 1, "blue_wall_banner", nbt=SNOWFLAKE, facing="south")
    S(x, 9, PZ1 + 1, FFN + "wall_light", facing="south")
# porche: columnas de piedra con capitel y tejadillo nevado
for x in (45, 55):
    S(x, FLOOR, 42, "stone_bricks"); S(x, 2, 42, "stone_bricks"); S(x, 1, 42, "stone_bricks")
    S(x, FLOOR + 1, 42, "chiseled_stone_bricks")
    fill(x, FLOOR + 2, 42, x, FLOOR + 6, 42, "stone_brick_wall")
    S(x, FLOOR + 7, 42, "chiseled_stone_bricks")
    for dx, dz, f in ((1, 0, "east"), (-1, 0, "west"), (0, 1, "south"), (0, -1, "north")):
        S(x + dx, FLOOR + 7, 42 + dz, "stone_brick_stairs", facing=OPP[f], half="top", shape="straight")
fill(45, FLOOR + 8, 40, 55, FLOOR + 8, 42, "dark_oak_log", axis="x")
for z in (40, 41, 42):
    S(45, FLOOR + 8, z, "dark_oak_log", axis="z"); S(55, FLOOR + 8, z, "dark_oak_log", axis="z")
gable_roof(44, 56, 40, 43, "x", FLOOR + 9)
for x in range(46, 55):
    S(x, FLOOR + 7, 43, FFD + ("fairy_lights_1" if x % 2 else "fairy_lights_2"), facing="south") \
        if False else None
for x in (47, 50, 53):
    S(x, FLOOR + 7, 41, "chain", axis="y"); S(x, FLOOR + 6, 41, "lantern", hanging=True)
S(50, FLOOR + 11, PZ1 + 1, "spruce_wall_sign", facing="south",
  nbt=sign_nbt(["Gran Salón", "del Jarl", "", "~ entra y caliéntate ~"], color="white"))
for x in range(PX0, PX1 + 1):
    if is_air(x, P_TOP - 1, PZ1 + 1):
        S(x, P_TOP - 1, PZ1 + 1, FFD + ("fairy_lights_1" if x % 2 else "fairy_lights_2"), facing="south")
# estandartes en los postes de la planta alta
for x in PXS[1:-1]:
    if not (PX0 - 1 <= x <= PX1 + 1):
        S(x, WALL_TOP - 1, HZ1 + 2, "blue_wall_banner", nbt=SNOWFLAKE, facing="south")
    S(x, WALL_TOP - 1, HZ0 - 2, "blue_wall_banner", nbt=SNOWFLAKE, facing="north")

# ---- interior del palacio
FY = FLOOR + 1                         # nivel de pisada
for x in range(HX0 + 1, HX1):          # alfombras laterales
    for z in (13, 31):
        S(x, FY, z, FFN + "carpet")
for z in range(HZ1, PZ1):
    for x in (49, 50, 51):
        S(x, FY, z, FFN + "carpet")
for z in range(24, HZ1):
    for x in (49, 50, 51):
        S(x, FY, z, FFN + "carpet")
# columnas y vigas
for x in range(32, 70, 6):
    for z in (15, 29):
        fill(x, FY, z, x, WALL_TOP, z, "dark_oak_log", axis="y")
        S(x, FY, z, "stone_bricks")
for x in PXS:
    fill(x, WALL_TOP + 1, HZ0, x, WALL_TOP + 1, HZ1, "dark_oak_log", axis="z")
    if HX0 < x < HX1:
        fill(x, WALL_TOP + 2, 22, x, RIDGE_Y - 1, 22, "dark_oak_fence")
for z in (15, 29):
    fill(HX0 + 1, WALL_TOP + 1, z, HX1 - 1, WALL_TOP + 1, z, "dark_oak_log", axis="x")
fill(HX0 + 1, RIDGE_Y - 1, 22, HX1 - 1, RIDGE_Y - 1, 22, "dark_oak_log", axis="x")
# basas y capiteles de las columnas
for x in range(32, 70, 6):
    for z in (15, 29):
        for dx, dz, f in ((1, 0, "east"), (-1, 0, "west"), (0, 1, "south"), (0, -1, "north")):
            S(x + dx, FY, z + dz, "stone_brick_stairs", facing=OPP[f], half="bottom", shape="straight")
            S(x + dx, WALL_TOP, z + dz, "dark_oak_stairs", facing=OPP[f], half="top", shape="straight")
            S(x + dx, FY + 4, z + dz, "blue_wall_banner", nbt=SNOWFLAKE, facing=f) if dz and (x // 6) % 2 else None
# galerías altas a ambos lados (balcones sobre las naves laterales)
GY = LOW_TOP
for z0, z1, edge, f_in in ((HZ0 + 1, 15, 15, "south"), (29, HZ1 - 1, 29, "north")):
    for x in range(HX0 + 1, HX1):
        for z in range(z0, z1 + 1):
            if get(x, GY, z) in ("minecraft:air",) or "carpet" in get(x, GY, z):
                S(x, GY, z, "dark_oak_slab", type="top")
        if get(x, GY, edge) != "minecraft:dark_oak_log":
            S(x, GY, edge, "dark_oak_log", axis="x")
            S(x, GY + 1, edge, "dark_oak_fence")
            S(x, GY - 1, edge, "dark_oak_trapdoor", facing=f_in, half="top", open=True) if False else None
    for x in range(HX0 + 3, HX1 - 2, 3):
        S(x, GY + 1, z0 if z0 > HZ0 else HZ0 + 1, "quark:spruce_bookshelf") if False else None
    for x in range(HX0 + 2, HX1 - 1, 6):
        wz = HZ0 + 1 if z0 == HZ0 + 1 else HZ1 - 1
        S(x + 1, GY + 1, wz, FFN + "bench" if False else FFN + "chair", facing="south" if wz == HZ0 + 1 else "north")
        S(x + 2, GY + 1, wz, FFN + "table_small", facing="south")
        S(x + 2, GY + 2, wz, FFD + rng.choice(["book_stack", "nordic_mead_bottles", "venthyr_tomes"]),
          facing="south", **{"books": 2} if False else {})
        S(x + 3, GY + 1, wz, FFN + "chair", facing="south" if wz == HZ0 + 1 else "north")
# hogar central
for x in range(37, 64):
    for z in (21, 23):
        S(x, FY, z, "stone_brick_slab", type="bottom")
    S(x, FLOOR, 22, "cobblestone")
    if 38 <= x <= 62:
        S(x, FLOOR, 22, "campfire" if x % 2 == 0 else "blackstone",
          **({"facing": "south", "lit": True, "signal_fire": False} if x % 2 == 0 else {}))
S(37, FY, 22, "stone_brick_slab", type="bottom"); S(63, FY, 22, "stone_brick_slab", type="bottom")
for x in (44, 56):
    S(x, FY, 22, FFD + "brewing_cauldron", facing="south")
    S(x, FLOOR, 22, "blackstone")
# mesas largas
TABLE_TOP = [
    (FFD + "tankards_honeymead", {"tankards": 1}), (FFD + "nordic_sweetrolls", {"rolls": 2}),
    (FFD + "nordic_mead_bottles", {"bottles": 1}), (FFD + "bowl_mushroom_stew", {}),
    ("candle", {"candles": 3, "lit": True}), (FFD + "nordic_boiled_creme_treats", {"treats": 2}),
    (FFD + "tankards_sweetberry", {"tankards": 0}), (FFD + "royal_platter", {"platter": 6}),
    (FFD + "bowl_beetroot_soup", {}), (FFD + "tankards_milk", {"tankards": 1}),
    (FFD + "royal_food_0", {}), (FFD + "venthyr_chalices", {"chalices": 2}),
]
k = 0
for tz in (18, 26):
    for x in list(range(35, 47)) + list(range(54, 66)):
        S(x, FY, tz, FFN + "table_small", facing="north")
        name, props = TABLE_TOP[k % len(TABLE_TOP)]
        k += 1
        if "candle" not in name:
            props = dict(props, facing=rng.choice(["north", "south"]))
        S(x, FY + 1, tz, name, **props)
        S(x, FY, tz - 1, FFN + "chair", facing="south")
        S(x, FY, tz + 1, FFN + "chair", facing="north")
# lámparas: arañas sobre las mesas y 3 grandes sobre el hogar
for x in range(32, 70, 6):
    for z in (18, 26):
        pass
for x in PXS[1:-1]:
    for z in (18, 26):
        fill(x, WALL_TOP - 1, z, x, WALL_TOP, z, "chain", axis="y")
        S(x, WALL_TOP - 2, z, FFN + "chandelier")
for x in (38, 50, 62):
    fill(x, WALL_TOP - 1, 22, x, RIDGE_Y - 2, 22, "chain", axis="y")
    S(x, WALL_TOP - 2, 22, FFN + "chandelier")
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        fill(x + dx, WALL_TOP - 3, 22 + dz, x + dx, WALL_TOP - 1, 22 + dz, "chain", axis="y")
        S(x + dx, WALL_TOP - 4, 22 + dz, "lantern", hanging=True)
    for dx, dz in ((1, 1), (-1, -1), (1, -1), (-1, 1)):
        S(x + dx, WALL_TOP - 2, 22 + dz, "chain", axis="y")
        S(x + dx, WALL_TOP - 3, 22 + dz, "lantern", hanging=True)
for x in PXS[1:-1]:
    S(x, FY + 5, HZ0 + 1, FFN + "wall_light", facing="south")
    S(x, FY + 5, HZ1 - 1, FFN + "wall_light", facing="north")
    S(x, FY + 10, HZ0, "blue_wall_banner", nbt=SNOWFLAKE, facing="south")
# estrado y trono (oeste)
for x in range(HX0 + 1, 33):
    for z in range(16, 29):
        S(x, FY, z, "dark_oak_planks"); S(x, FY + 1, z, "air")
for x in range(HX0 + 1, 31):
    for z in range(18, 27):
        S(x, FY + 1, z, "dark_oak_planks")
for z in range(16, 29):
    S(33, FY, z, "spruce_stairs", facing="west", half="bottom", shape="straight")
for z in range(18, 27):
    S(31, FY + 1, z, "spruce_stairs", facing="west", half="bottom", shape="straight")
fill(28, FY + 2, 19, 30, FY + 2, 25, FFN + "carpet")
# trono
S(28, FY + 2, 22, FFN + "chair", facing="east")
for dz in (-1, 1):
    S(28, FY + 2, 22 + dz, "dark_oak_stairs", facing="north" if dz > 0 else "south", half="bottom", shape="straight")
fill(27, FY + 2, 21, 27, FY + 5, 23, "dark_oak_planks")
S(27, FY + 6, 22, "gold_block")
S(27, FY + 6, 21, "dark_oak_stairs", facing="north", half="bottom", shape="straight")
S(27, FY + 6, 23, "dark_oak_stairs", facing="south", half="bottom", shape="straight")
for z in (19, 25):
    S(28, FY + 2, z, FFN + "floor_light")
for z in (17, 27):
    S(28, FY + 2, z, "supplementaries:pedestal") if False else None
    fill(29, FY + 1, z, 29, FY + 3, z, "stone_bricks")
    S(29, FY + 4, z, "campfire", facing="east", lit=True, signal_fire=False)
for z in (16, 19, 25, 28):
    S(HX0 + 1, FY + 7, z, "blue_wall_banner", nbt=SNOWFLAKE, facing="east")
S(HX0 + 1, FY + 4, 14, FFN + "wall_light", facing="east"); S(HX0 + 1, FY + 4, 30, FFN + "wall_light", facing="east")
# chimenea monumental (este)
for x in range(HX1 - 4, HX1):
    for z in range(17, 28):
        for y in range(FY, WALL_TOP + 1):
            S(x, y, z, stone(y))
fill(HX1 - 4, FY, 19, HX1 - 2, FY + 4, 25, "air")
for z in range(19, 26):
    S(HX1 - 2, FLOOR, z, "netherrack") if False else None
for z in (20, 22, 24):
    S(HX1 - 3, FY, z, "campfire", facing="west", lit=True, signal_fire=False)
for z in (21, 23):
    S(HX1 - 3, FY, z, FFD + "bone_skeleton_pile", facing="west") if False else S(HX1 - 3, FY, z, "spruce_log", axis="z")
for z in range(18, 27):
    S(HX1 - 5, FY + 5, z, FFN + "shelf", facing="west", connection={18: "right", 26: "left"}.get(z, "center"))
for z in range(19, 26):
    S(HX1 - 5, FY + 6, z, "air")
for z in (19, 21, 23, 25):
    S(HX1 - 5, FY + 4, z, FFD + "stocking", facing="west")
S(HX1 - 5, FY + 6, 20, FFD + "nordic_soul_gems_light", facing="west")
S(HX1 - 5, FY + 6, 24, FFD + "nordic_soul_gems_dark", facing="west")
S(HX1 - 5, FY + 6, 22, FFD + "royal_cushioned_crown", facing="west")
for z in range(17, 28):
    S(HX1 - 5, FY + 8, z, "blue_wall_banner", nbt=SNOWFLAKE, facing="west") if z in (19, 25) else None
for y in range(WALL_TOP + 1, RIDGE_Y + 5):
    for x in range(HX1 - 3, HX1):
        for z in range(20, 25):
            S(x, y, z, stone(y) if y < RIDGE_Y + 4 else "stone_brick_slab", **({"type": "bottom"} if y == RIDGE_Y + 4 else {}))
S(HX1 - 2, RIDGE_Y + 4, 22, "campfire", lit=True, signal_fire=True, facing="west")
# sofás frente a la chimenea
fill(HX1 - 9, FY, 19, HX1 - 6, FY, 25, FFN + "carpet")
for z in (20, 21, 22, 23, 24):
    S(HX1 - 10, FY, z, FFN + "sofa", facing="east", connection="single")
S(HX1 - 10, FY, 19, FFN + "floor_light"); S(HX1 - 10, FY, 25, FFN + "floor_light")
# biblioteca y rincones
for z in list(range(12, 16)) + list(range(29, 33)):
    fill(HX1 - 1, FY, z, HX1 - 1, FY + 3, z, "quark:spruce_bookshelf")
S(HX1 - 2, FY, 13, "supplementaries:globe", facing="west")
S(HX1 - 2, FY, 31, FFN + "table_small", facing="west")
S(HX1 - 2, FY + 1, 31, FFD + "floating_tomes", facing="west", tomes=1)
S(HX1 - 3, FY, 31, FFN + "chair", facing="east")
for (x, z) in ((HX0 + 1, 12), (HX0 + 2, 12), (HX0 + 1, 32), (HX0 + 2, 32), (HX0 + 3, 12), (HX0 + 3, 32)):
    S(x, FY, z, "barrel", facing="up", open=False)
S(HX0 + 1, FY + 1, 12, FFD + "potion_bottles", facing="south", potions=2)
S(HX0 + 2, FY + 1, 32, FFD + "tankards_empty", facing="north", tankards=1)
S(HX0 + 3, FY + 1, 12, FFD + "coin_stack_gold", facing="south")
for x in (46, 54):
    S(x, FY, HZ1 - 1, FFN + "floor_light")
    S(x, FY, PZ1 - 1, FFN + "floor_light")

# ---- torres traseras del palacio
for tx in (23, 77):
    round_tower(tx, 9, 4, 28, 12, floor_mat="spruce_planks")

# ================================================================ BARRIO OESTE: taberna, mercado, herrería
# taberna
fy = nordic_house(9, 46, 28, 60, 8, "east", 52)
fill(10, fy, 47, 27, fy, 59, "air")
for x in range(12, 18):
    S(x, fy, 49, FFN + "counter", facing="south", connection="single")
for x in range(12, 18, 2):
    S(x, fy + 1, 49, FFD + rng.choice(["tankards_honeymead", "tankards_sweetberry", "tankards_milk"]),
      facing="south", tankards=1)
for x in range(10, 20, 2):
    S(x, fy, 47, "barrel", facing="south", open=False)
    S(x + 1, fy, 47, "barrel", facing="up", open=False)
    S(x + 1, fy + 1, 47, FFD + "nordic_mead_bottles", facing="south", bottles=2)
for (tx, tz) in ((14, 54), (19, 54), (24, 54), (14, 57), (19, 57), (24, 49)):
    S(tx, fy, tz, FFN + "table_small", facing="north")
    S(tx, fy + 1, tz, rng.choice([FFD + "tankards_honeymead", FFD + "nordic_sweetrolls", FFD + "bowl_mushroom_stew"]),
      facing="north", **({"tankards": 1} if False else {}))
    S(tx - 1, fy, tz, FFN + "stool", facing="east"); S(tx + 1, fy, tz, FFN + "stool", facing="west")
fill(10, fy, 55, 10, fy + 4, 59, "stone_bricks")
S(10, fy, 57, "air"); S(10, fy + 1, 57, "air")
S(10, fy, 57, "campfire", facing="east", lit=True, signal_fire=False)
S(11, fy + 2, 57, FFD + "stocking", facing="east") if False else None
for (x, z) in ((14, 51), (22, 51), (14, 58), (22, 58)):
    S(x, 8 - 1, z, "chain", axis="y")
    S(x, 8 - 2, z, FFN + "chandelier")
S(29, 7, 54, "dark_oak_fence") if False else None
for y in range(8, 16):
    for x in (9, 10):
        for z in (56, 57, 58):
            S(x, y, z, stone(y) if y < 15 else "stone_brick_slab", **({"type": "bottom"} if y == 15 else {}))
S(10, 15, 57, "campfire", lit=True, signal_fire=False, facing="east")
S(29, 5, 51, "spruce_wall_sign", facing="east", nbt=sign_nbt(["Taberna", "El Hidromiel", "Helado", ""], color="white"))
# herrería
fy = nordic_house(9, 74, 24, 86, 7, "east", 79)
fill(10, fy, 75, 23, fy, 85, "air")
S(12, fy, 76, "anvil", facing="east"); S(14, fy, 76, "grindstone", face="floor", facing="east")
S(11, fy, 80, "blast_furnace", facing="east", lit=True); S(11, fy, 81, "smoker", facing="east", lit=True)
S(11, fy, 82, "smithing_table"); S(11, fy, 78, "crafting_table")
fill(11, fy, 84, 13, fy, 84, "barrel", facing="up", open=False)
S(16, fy, 76, "campfire", facing="south", lit=True, signal_fire=False)
S(20, fy, 84, FFN + "table_small", facing="north"); S(20, fy + 1, 84, FFD + "coin_stack_iron", facing="north")
for y in range(7, 14):
    for x in (20, 21):
        for z in (75, 76):
            S(x, y, z, stone(y) if y < 13 else "stone_brick_slab", **({"type": "bottom"} if y == 13 else {}))
S(21, 13, 76, "campfire", lit=True, signal_fire=False, facing="east")
S(25, 5, 77, "spruce_wall_sign", facing="east", nbt=sign_nbt(["Herrería", "", "", ""], color="white"))
for x in range(26, 29):
    S(x, 0, 80, "cobblestone")
# mercado
def stall(x0, z0, c1, c2, goods):
    x1, z1 = x0 + 4, z0 + 3
    for (x, z) in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
        fill(x, 1, z, x, 2, z, "spruce_fence")
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            S(x, 3, z, (c1 if x % 2 else c2) + "_wool")
            S(x, 4, z, "snow", layers=1)
    for x in range(x0 + 1, x1):
        S(x, 1, z1, FFN + "counter", facing="south", connection="single")
    S(x0 + 1, 1, z0, "barrel", facing="up", open=False); S(x1 - 1, 1, z0, "barrel", facing="up", open=False)
    S(x0 + 2, 1, z0, "quark:crate", open=False)
    S(x0 + 2, 2, z0, "lantern", hanging=False)
    S(x0 + 2, 1, z0 + 1, FFN + "stool", facing="south")
    for i, g in enumerate(goods):
        props = {"facing": "south"}
        if "potion" in g:
            props["potions"] = 2
        if "cookie" in g:
            props["fill_stage"] = "full"
        S(x0 + 1 + i, 2, z1, g, **props)

stall(9, 63, "light_blue", "white", [FFD + "berry_basket_sweetberry", FFD + "coin_stack_gold", FFD + "berry_basket_blueberry"])
stall(16, 63, "blue", "white", [FFD + "potion_bottles", FFD + "bolts_of_cloth", FFD + "cookie_jar"])
stall(23, 63, "red", "white", [FFD + "muffins_blueberry", FFD + "nordic_sweetrolls", FFD + "muffins_chocolate"])
for x in range(8, 32):
    for z in range(68, 72):
        path_tile(x, z, edge=z in (68, 71))
for x in (12, 20, 28):
    lamp_post(x, 72, 3)
for x in range(29, 32):
    for z in (52, 53, 79, 80):
        path_tile(x, z)

# ================================================================ BARRIO ESTE: lago helado
LX, LZ, RX, RZ = 81, 64, 10, 15
for x in range(66, 95):
    for z in range(45, 88):
        e = ((x - LX) / RX) ** 2 + ((z - LZ) / RZ) ** 2
        if e <= 1.0:
            S(x, 0, z, "packed_ice" if rng.random() < 0.8 else "blue_ice")
        elif e <= 1.3:
            S(x, 0, z, "snow_block")
            if rng.random() < 0.6:
                S(x, 1, z, "snow", layers=rng.choice([1, 2, 3]))
for (x, z, h, r) in ((84, 56, 16, 2.4), (86, 59, 10, 1.6), (82, 53, 8, 1.4), (78, 72, 13, 2.0),
                     (76, 75, 7, 1.3), (87, 70, 11, 1.8), (89, 50, 9, 1.5), (73, 51, 6, 1.2)):
    ice_spike(x, z, h, r)
# muelle
for x in range(70, 77):
    for z in (63, 64, 65):
        S(x, 0, z, "spruce_planks") if x > 72 else None
        S(x, 1, z, "spruce_slab", type="bottom")
for x in (70, 76):
    for z in (62, 66):
        lamp_post(x, z, 2, base=1)
# muñecos de nieve
for (x, z, f) in ((70, 55, "east"), (71, 78, "east"), (90, 82, "west")):
    fill(x, 1, z, x, 2, z, "snow_block")
    S(x, 3, z, "carved_pumpkin", facing=f)
S(72, 1, 56, FFD + "snowballs", facing="south", snowballs=3)
S(70, 1, 79, FFD + "snowballs", facing="east", snowballs=2)
for z in range(57, 72, 4):
    S(68, 1, z, "spruce_stairs", facing="west", half="bottom", shape="straight")
    S(68, 1, z + 1, "spruce_stairs", facing="west", half="bottom", shape="straight")
for z in (55, 74):
    lamp_post(67, z, 4)

# ================================================================ CÍRCULO DE PIEDRAS (waystone)
WX, WZ = 13, 25
for x in range(WX - 7, WX + 8):
    for z in range(WZ - 7, WZ + 8):
        d = math.hypot(x - WX, z - WZ)
        if d <= 2.6:
            S(x, 0, z, "chiseled_stone_bricks" if d > 1 else "lodestone")
        elif d <= 6.8:
            S(x, 0, z, rng.choice(["gravel", "cobblestone", "mossy_cobblestone", "snow_block", "coarse_dirt"]))
for k in range(8):
    a = math.radians(22.5 + 45 * k)
    x, z = round(WX + 5.5 * math.cos(a)), round(WZ + 5.5 * math.sin(a))
    h = 4 + k % 2
    fill(x, 1, z, x, h, z, rng.choice(["stone", "andesite", "mossy_stone_bricks"]))
    S(x, h + 1, z, "soul_lantern", hanging=False) if k % 2 == 0 else snow_on(x, h, z, 1, 2, 3)
S(WX, 1, WZ + 3, "spruce_sign", rotation=0,
  nbt=sign_nbt(["Waystone", "colócalo sobre", "la piedra imán", ""], color="white"))
for (x, z) in ((WX - 2, WZ - 2), (WX + 2, WZ + 2)):
    S(x, 1, z, "soul_campfire", facing="south", lit=True, signal_fire=False)

# ================================================================ TABLÓN DE INFORMACIÓN (junto al spawn)
BX, BZ0, BZ1 = 60, 79, 87
for z in range(BZ0, BZ1 + 1):
    S(BX, 0, z, "stone_bricks")
    if z in (BZ0, BZ1):
        fill(BX, 1, z, BX, 4, z, "dark_oak_log", axis="y")
    else:
        fill(BX, 1, z, BX, 3, z, "spruce_planks")
        S(BX, 4, z, "dark_oak_log", axis="z")
for z in range(BZ0 - 1, BZ1 + 2):
    S(BX - 1, 5, z, "spruce_stairs", facing="east", half="bottom", shape="straight")
    S(BX, 5, z, "dark_oak_planks"); snow_on(BX, 5, z, 1, 1, 2)
    S(BX + 1, 5, z, "spruce_stairs", facing="west", half="bottom", shape="straight")
INFO = [
    ["¡Bienvenido/a!", "KB Server", "Invierno 2026", "Terramity Awakened"],
    ["Parties", "/oparties create", "/oparties member", "invite <jugador>"],
    ["Claims", "/oclaims claim", "/oclaims unclaim", "/oclaims about"],
    ["Mapa online", "minecraft.", "jonaykb.com", ""],
]
for i, z in enumerate((86, 84, 82, 80)):
    S(BX - 1, 2, z, "dark_oak_wall_sign", facing="west", nbt=sign_nbt(INFO[i], color="white"))
    S(BX - 1, 3, z, FFN + "wall_light", facing="west") if i in (1, 3) else None
S(BX - 1, 3, 85, "supplementaries:notice_board", facing="west", has_book=False)
S(BX - 1, 3, 81, "supplementaries:notice_board", facing="west", has_book=False)

# ================================================================ ÁRBOLES, LEÑERAS Y DETALLES
for (x, z, h, r) in ((12, 40, 9, 2.6), (18, 38, 8, 2.2), (34, 88, 10, 2.8), (28, 90, 8, 2.2), (14, 90, 9, 2.4),
                     (88, 90, 10, 2.8), (82, 88, 8, 2.2), (70, 90, 9, 2.4), (86, 30, 10, 2.8), (90, 20, 9, 2.4),
                     (84, 14, 8, 2.2), (34, 74, 7, 2.0), (66, 46, 7, 2.0), (34, 47, 7, 2.0), (91, 40, 8, 2.2),
                     (9, 34, 7, 2.0), (91, 85, 7, 2.0)):
    spruce_tree(x, z, h, r)
for (x0, z0) in ((80, 34), (8, 10)):
    fill(x0, 1, z0, x0 + 5, 2, z0 + 2, "spruce_log", axis="x")
    fill(x0, 3, z0, x0 + 5, 3, z0 + 2, "spruce_slab", type="bottom")
    fill(x0, 4, z0, x0 + 5, 4, z0 + 2, "snow", layers=1)
for (x, z) in ((82, 24), (84, 24)):
    S(x, 1, z, "barrel", facing="up", open=False)

# ================================================================ FOSO HELADO
def mring(x, z):
    return max(abs(x - C), abs(z - C))


for x in range(-M, CORE + M):
    for z in range(-M, CORE + M):
        m = mring(x, z)
        if 50 <= m <= 54:
            for y in range(-1, 4):
                S(x, y, z, "air")
            S(x, -3, z, "stone")
            S(x, -2, z, rng.choices(["packed_ice", "blue_ice", "snow_block"], [70, 18, 12])[0])
            if rng.random() < 0.18:
                S(x, -1, z, "snow", layers=rng.choice([1, 1, 2]))
        elif m in (49, 55):
            S(x, -2, z, "stone_bricks"); S(x, -1, z, stone(3))
            S(x, 0, z, "polished_andesite" if m == 49 else "stone_bricks")
# carámbanos de hielo en el foso
for (x, z) in ((2, 102), (98, 103), (-2, 30), (103, 70), (30, -2), (70, -3), (-3, 75), (102, 12)):
    ice_spike(x, z, rng.randint(3, 5), 1.0, base=-1)

# ================================================================ MURALLA EXTERIOR (baja) Y BARBACANA
for x in range(-M, CORE + M):
    for z in range(-M, CORE + M):
        m = mring(x, z)
        along = z if abs(x - C) >= abs(z - C) else x
        if m in (56, 57):
            for y in range(1, 5):
                S(x, y, z, stone(y))
            S(x, 5, z, "spruce_planks" if m == 56 else "stone_bricks")
            if m == 57:
                if along % 3:
                    S(x, 6, z, stone(6)); snow_on(x, 6, z, 0.9, 1, 3)
                    if along % 9 == 1:
                        S(x, 7, z, "lantern", hanging=False)
                else:
                    S(x, 6, z, "stone_brick_slab", type="bottom")
            else:
                S(x, 6, z, "stone_brick_wall") if along % 4 == 0 else snow_on(x, 5, z, 0.5, 1, 1)
        elif m == 58:
            if along % 8 == 4:
                fill(x, 1, z, x, 3, z, "stone_bricks")
                S(x, 4, z, "stone_brick_stairs", facing=inward(x, z), half="bottom", shape="straight")
            else:
                S(x, 1, z, "stone_brick_stairs", facing=inward(x, z), half="bottom", shape="straight")
for (tx, tz) in ((-6, -6), (106, -6), (-6, 106), (106, 106)):
    round_tower(tx, tz, 4, 9, 8)
# hueco de la barbacana y puente levadizo
for x in range(45, 56):
    for z in range(104, 109):
        for y in range(1, 8):
            S(x, y, z, "air")
for tx in (42, 58):
    round_tower(tx, 107, 3, 11, 8)
fill(44, 8, 106, 56, 8, 107, "dark_oak_log", axis="x")
fill(44, 9, 106, 56, 9, 107, "stone_bricks")
for x in range(44, 57):
    S(x, 10, 107, "stone_bricks" if x % 2 else "stone_brick_slab", **({} if x % 2 else {"type": "bottom"}))
    snow_on(x, 10, 107, 0.8, 1, 2) if x % 2 else None
for x in (45, 55):
    fill(x, 1, 108, x, 7, 108, "dark_oak_log", axis="y")
for z in (105, 106, 107, 108):
    S(45, 7, z, "dark_oak_log", axis="z"); S(55, 7, z, "dark_oak_log", axis="z")
S(50, 7, 108, "spruce_hanging_sign", rotation=0, attached=False,
  nbt=sign_nbt(["Ciudadela", "de Invierno", "KB Server", ""], hanging=True, color="light_blue"))
for x in (47, 53):
    S(x, 7, 108, "lantern", hanging=True)
S(43, 9, 109, "blue_wall_banner", nbt=SNOWFLAKE, facing="south")
S(57, 9, 109, "blue_wall_banner", nbt=SNOWFLAKE, facing="south")
# puente levadizo (bajado) sobre el foso
for z in range(99, 106):
    for x in range(46, 55):
        S(x, 0, z, "dark_oak_planks" if x not in (46, 54) else "dark_oak_log",
          **({"axis": "z"} if x in (46, 54) else {}))
    S(46, 1, z, "dark_oak_fence"); S(54, 1, z, "dark_oak_fence")
for x in range(46, 55):
    S(x, -1, 102, "dark_oak_log", axis="x")
for x in (46, 54):
    fill(x, -2, 102, x, -1, 102, "dark_oak_log", axis="y")
    fill(x, 1, 104, x, 4, 104, "dark_oak_log", axis="y")
    S(x, 5, 104, "lantern", hanging=False)
    for k in range(1, 6):            # cadenas del puente hacia la puerta
        S(x, 4 + k, 104 - k, "chain", axis="z")
        S(x, 4 + k, 104 - k + 1, "chain", axis="y") if k > 1 else None
# camino de llegada
for z in range(104, CORE + M):
    for x in range(45, 56):
        if z >= 108:
            path_tile(x, z, edge=x in (45, 55))
for z in (113, 120, 127):
    lamp_post(44, z, 4, arms=[(1, 0)]); lamp_post(56, z, 4, arms=[(-1, 0)])
for z in (116, 124):
    banner_pole(43, z); banner_pole(57, z)
# camino hacia el puerto (rodea la muralla por fuera)
for x in range(56, 112):
    for z in range(110, 114):
        path_tile(x, z, edge=z in (110, 113))
for x in range(64, 112, 9):
    lamp_post(x, 114, 3)

# ================================================================ PUERTO HELADO (este)
QX0, QX1 = 109, 113
for x in range(QX0, CORE + M):
    for z in range(-M, CORE + M):
        if x <= QX1:                                  # muelle de piedra
            if z <= 114:
                S(x, 0, z, "stone_bricks" if (x + z) % 5 else "polished_andesite")
                if x == QX1:
                    S(x, -1, z, stone(3)); S(x, -2, z, "stone_bricks")
        else:                                         # mar helado
            for y in range(-1, 4):
                S(x, y, z, "air")
            S(x, -3, z, "stone")
            S(x, -2, z, rng.choices(["packed_ice", "blue_ice", "snow_block"], [64, 20, 16])[0])
            if rng.random() < 0.2:
                S(x, -1, z, "snow", layers=rng.choice([1, 2, 3]))
for z in range(-M, 115, 6):                           # norays
    S(QX1, 1, z, "stone_brick_wall")
    S(QX1, 2, z, "snow", layers=2) if False else None
# pantalanes de madera
for pz in (28, 54, 80):
    for x in range(QX1 + 1, 128):
        for z in (pz - 1, pz, pz + 1):
            S(x, 0, z, "spruce_planks")
        if x % 3 == 0:
            for z in (pz - 1, pz + 1):
                fill(x, -2, z, x, 0, z, "spruce_log", axis="y")
                S(x, 1, z, "spruce_fence")
    lamp_post(127, pz - 1, 3); lamp_post(127, pz + 1, 3)
    S(126, 1, pz, "barrel", facing="up", open=False)


def drakkar(xc, zc, L=19, B=3.3, colors=("red", "white"), shield_cols=("red", "yellow", "blue", "white")):
    zs, ze = zc - L // 2, zc + L // 2
    for z in range(zs, ze + 1):
        t = (z - zc) / (L / 2)
        prof = max(0.0, 1 - t * t) ** 0.55
        for y in range(-4, 2):
            fy = 0.35 + 0.65 * (y + 4) / 5
            w = B * prof * fy
            for dx in range(-5, 6):
                ax = abs(dx)
                if ax > w + 0.01:
                    continue
                shell = ax > w - 1.0 or y == -4
                if shell:
                    if y == 1:
                        S(xc + dx, y, z, "dark_oak_planks")
                    elif y == 0 and ax >= 2 and (z - zs) % 2 == 0:
                        S(xc + dx, y, z, shield_cols[((z - zs) // 2) % len(shield_cols)] + "_wool")
                    elif y == -1:
                        S(xc + dx, y, z, "dark_oak_log", axis="z")
                    else:
                        S(xc + dx, y, z, "spruce_planks")
                elif y == -1:
                    S(xc + dx, y, z, "spruce_planks")
                elif y >= 0:
                    S(xc + dx, y, z, "air")
    # roda con cabeza de dragón (proa, z pequeño) y codaste enroscado (popa)
    for k, (dz, dy) in enumerate(((0, 1), (1, 2), (1, 3), (2, 4), (2, 5), (3, 6), (3, 7))):
        S(xc, dy, zs - dz, "dark_oak_log", axis="y")
    S(xc, 7, zs - 4, "dark_oak_planks"); S(xc, 8, zs - 4, "dark_oak_stairs", facing="south", half="bottom", shape="straight")
    S(xc, 6, zs - 4, "dark_oak_stairs", facing="south", half="top", shape="straight")
    S(xc, 7, zs - 5, "red_wool")
    for (dz, dy) in ((0, 1), (1, 2), (1, 3), (2, 4), (2, 5), (2, 6), (1, 7), (0, 7), (0, 6)):
        S(xc, dy, ze + dz, "dark_oak_log", axis="y")
    # mástil, verga y vela recogida a medias
    fill(xc, -1, zc, xc, 13, zc, "spruce_log", axis="y")
    fill(xc - 5, 12, zc, xc + 5, 12, zc, "spruce_log", axis="x")
    for x in range(xc - 5, xc + 6):
        snow_on(x, 12, zc, 0.8, 1, 2)
    for x in range(xc - 4, xc + 5):
        for y in range(6, 12):
            if y >= 7 or abs(x - xc) < 4:
                S(x, y, zc + 1, colors[(x - xc + 10) // 2 % 2] + "_wool")
    S(xc, 14, zc, "lantern", hanging=False)
    for z in (zs + 2, ze - 2):
        S(xc, 0, z, "barrel", facing="up", open=False)
    S(xc + 1, 0, zc - 3, FFD + "tankards_honeymead", facing="south", tankards=1) if False else None
    for x in range(xc - 3, xc + 4):
        for z in range(zs, ze + 1):
            if get(x, -1, z) == "minecraft:spruce_planks" and is_air(x, 0, z) and rng.random() < 0.35:
                S(x, 0, z, "snow", layers=rng.choice([1, 2]))
    # grietas de hielo azul alrededor del casco
    for x in range(xc - 6, xc + 7):
        for z in range(zs - 3, ze + 4):
            if get(x, -2, z) in ("minecraft:packed_ice", "minecraft:snow_block") and rng.random() < 0.3:
                S(x, -2, z, "blue_ice")


drakkar(121, 41, colors=("red", "white"))
drakkar(121, 67, colors=("blue", "white"), shield_cols=("blue", "white", "red", "yellow"))
drakkar(122, 97, L=15, B=2.8, colors=("black", "red"), shield_cols=("black", "red", "white"))
# grúa de carga y mercancías en el muelle
fill(111, 1, 46, 111, 9, 46, "dark_oak_log", axis="y")
for x in range(112, 117):
    S(x, 9, 46, "dark_oak_fence")
S(110, 9, 46, "dark_oak_fence")
fill(116, 5, 46, 116, 8, 46, "chain", axis="y")
S(116, 4, 46, "barrel", facing="up", open=False)
for (x, z) in ((110, 50), (111, 50), (110, 51), (112, 58), (110, 60), (111, 60), (110, 34), (112, 22), (110, 75)):
    S(x, 1, z, rng.choice(["barrel", "quark:crate", "spruce_planks"]),
      **({"facing": "up", "open": False} if True else {}))
for (x, z) in ((110, 50), (110, 60)):
    S(x, 2, z, "quark:crate", open=False)
for (x, z) in ((112, 36), (112, 64), (112, 88)):
    S(x, 1, z, FFD + "stackable_pumpkins", facing="east", pumpkins=1) if False else None
for z in range(10, 112, 12):
    lamp_post(110, z, 4, arms=[(1, 0)])
S(110, 1, 30, "spruce_sign", rotation=4, nbt=sign_nbt(["Puerto", "Helado", "", ""], color="white"))

# ================================================================ BOSQUE NEVADO ALREDEDOR
placed = []
for _ in range(900):
    x, z = rng.randint(-M + 1, CORE + M - 2), rng.randint(-M + 1, CORE + M - 2)
    m = mring(x, z)
    if m < 61 or x >= QX0 - 2 or (40 <= x <= 60 and z > 100) or (54 <= x and 106 <= z <= 117):
        continue
    if any((x - a) ** 2 + (z - b) ** 2 < 30 for a, b in placed):
        continue
    placed.append((x, z))
    h = rng.randint(7, 14)
    spruce_tree(x, z, h, 1.6 + h * 0.2)
    if len(placed) > 80:
        break
for _ in range(25):                                   # rocas
    x, z = rng.randint(-M + 1, CORE + M - 2), rng.randint(-M + 1, CORE + M - 2)
    if mring(x, z) < 60 or x >= QX0 or is_air(x, 1, z) is False:
        continue
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if rng.random() < 0.7:
                S(x + dx, 1, z + dz, rng.choice(["stone", "andesite", "mossy_cobblestone", "cobblestone"]))
                snow_on(x + dx, 1, z + dz, 0.9, 1, 3)
    S(x, 2, z, "andesite"); snow_on(x, 2, z, 1, 2, 4)

# ================================================================ nieve suelta y conexiones
for x in range(-M + 1, CORE + M - 1):
    for z in range(-M + 1, CORE + M - 1):
        if get(x, 0, z) == "minecraft:snow_block" and is_air(x, 1, z) and rng.random() < 0.45:
            S(x, 1, z, "snow", layers=rng.choice([1, 1, 1, 2]))
# despejar el punto de spawn
for dx in (-1, 0, 1):
    for dz in (-1, 0, 1):
        if get(SPAWN[0] + dx, 1, SPAWN[2] + dz) == "minecraft:snow":
            S(SPAWN[0] + dx, 1, SPAWN[2] + dz, "air")

NON_FULL = ("stairs", "slab", "fence", "pane", "lantern", "bars", "wall", "sign", "banner", "snow",
            "campfire", "trapdoor", "door", "carpet", "candle", "rod", "fantasyfurniture", "supplementaries",
            "air", "leaves", "glass", "present", "crate", "chain", "anvil", "grindstone")


def full(name):
    if name == "minecraft:light":
        return False
    return not any(t in name for t in NON_FULL) or name in ("minecraft:snow_block",)


for (x, y, z), (name, props, nbt) in list(blocks.items()):
    fam = None
    if name.endswith("_fence"):
        fam = lambda n: n.endswith("_fence") or n.endswith("fence_gate") or full(n)
    elif name.endswith("glass_pane") or name.endswith("iron_bars"):
        fam = lambda n: n.endswith("pane") or n.endswith("iron_bars") or full(n) or n.endswith("_wall")
    elif name.endswith("_wall") and "sign" not in name and "banner" not in name:
        fam = lambda n: n.endswith("_wall") or full(n)
    if fam is None:
        continue
    for d, (dx, dz) in (("north", (0, -1)), ("south", (0, 1)), ("east", (1, 0)), ("west", (-1, 0))):
        c = fam(rawget(x + dx, y, z + dz))
        if name.endswith("_wall"):
            props[d] = "low" if c else "none"
        else:
            props[d] = "true" if c else "false"
    if name.endswith("_wall"):
        props["up"] = "true"


# ---------------------------------------------------------------- iluminación nocturna
EMIT = {"lantern": 15, "soul_lantern": 10, "glowstone": 15, "shroomlight": 15, "ochre_froglight": 15,
        "pearlescent_froglight": 15, "verdant_froglight": 15, "sea_lantern": 15, "end_rod": 14,
        "jack_o_lantern": 15, "nordic/wall_light": 14, "nordic/floor_light": 14, "nordic/chandelier": 14,
        "decorations/fairy_lights_1": 8, "decorations/fairy_lights_2": 8}


def emission(name, props):
    short = name.split(":", 1)[1]
    if short == "light":
        return int(props.get("level", 15))
    if short in ("campfire", "soul_campfire"):
        return (15 if short == "campfire" else 10) if props.get("lit", "true") == "true" else 0
    if short.endswith("candle") or short == "candle":
        return 3 * int(props.get("candles", 1)) if props.get("lit") == "true" else 0
    if short in ("blast_furnace", "smoker", "furnace"):
        return 13 if props.get("lit") == "true" else 0
    return EMIT.get(short, 0)


def compute_light():
    """Luz de bloque aproximada (como el juego: -1 por bloque, la bloquean los bloques opacos)."""
    import numpy as np
    L = np.zeros((W, H, D), np.int16)
    T = np.ones((W, H, D), bool)
    for (x, y, z), (name, props, _) in blocks.items():
        e = emission(name, props)
        if e:
            L[x, y, z] = e
        if full(name):
            T[x, y, z] = False
    for _ in range(15):
        N = L.copy()
        N[1:] = np.maximum(N[1:], L[:-1]); N[:-1] = np.maximum(N[:-1], L[1:])
        N[:, 1:] = np.maximum(N[:, 1:], L[:, :-1]); N[:, :-1] = np.maximum(N[:, :-1], L[:, 1:])
        N[:, :, 1:] = np.maximum(N[:, :, 1:], L[:, :, :-1]); N[:, :, :-1] = np.maximum(N[:, :, :-1], L[:, :, 1:])
        L = np.where(T, np.maximum(L, N - 1), L)
    return L


def place_hidden_lights():
    """Bloques de luz invisibles (nivel 11, no derrite la nieve) donde quede oscuro: de noche se ve
    y no aparecen monstruos dentro de la ciudadela."""
    try:
        import numpy as np
        light = compute_light()
    except ImportError:
        return 0
    g = np.abs(np.arange(-10, 11))
    KER = np.maximum(0, 11 - (g[:, None, None] + g[None, :, None] + g[None, None, :])).astype(np.int16)
    n = 0
    for step, thr in ((4, 8), (2, 6)):
        for X in range(1, W - 1, step):
            for Z in range(1, D - 1, step):
                for Y in range(1, H - 1):
                    if (X, Y, Z) in blocks or light[X, Y, Z] >= thr:
                        continue
                    below = rawget(X, Y - 1, Z)
                    if below == "minecraft:air" or "leaves" in below or below == "minecraft:light":
                        continue
                    if Y > OY + 30:
                        continue
                    blocks[(X, Y, Z)] = ("minecraft:light", {"level": "11", "waterlogged": "false"}, None)
                    n += 1
                    x0, x1 = max(0, X - 10), min(W, X + 11)
                    y0, y1 = max(0, Y - 10), min(H, Y + 11)
                    z0, z1 = max(0, Z - 10), min(D, Z + 11)
                    sub = KER[x0 - X + 10:x1 - X + 10, y0 - Y + 10:y1 - Y + 10, z0 - Z + 10:z1 - Z + 10]
                    light[x0:x1, y0:y1, z0:z1] = np.maximum(light[x0:x1, y0:y1, z0:z1], sub)
    return n


N_LIGHTS = place_hidden_lights()


# ---------------------------------------------------------------- NBT
class Tag:
    END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BARR, STR, LIST, COMP = range(11)


def tag_type(v):
    if isinstance(v, tuple) and v[0] == "b":
        return Tag.BYTE
    if isinstance(v, bool):
        return Tag.BYTE
    if isinstance(v, int):
        return Tag.INT
    if isinstance(v, str):
        return Tag.STR
    if isinstance(v, list):
        return Tag.LIST
    if isinstance(v, dict):
        return Tag.COMP
    raise TypeError(v)


def w_str(buf, s):
    b = s.encode("utf-8")
    buf.write(struct.pack(">H", len(b)) + b)


def w_payload(buf, v):
    t = tag_type(v)
    if t == Tag.BYTE:
        buf.write(struct.pack(">b", v[1] if isinstance(v, tuple) else int(v)))
    elif t == Tag.INT:
        buf.write(struct.pack(">i", v))
    elif t == Tag.STR:
        w_str(buf, v)
    elif t == Tag.LIST:
        et = tag_type(v[0]) if v else Tag.END
        buf.write(struct.pack(">bi", et, len(v)))
        for e in v:
            w_payload(buf, e)
    elif t == Tag.COMP:
        for k, e in v.items():
            buf.write(struct.pack(">b", tag_type(e)))
            w_str(buf, k)
            w_payload(buf, e)
        buf.write(b"\x00")


def build_structure():
    palette, index, out = [], {}, []
    for x in range(W):
        for y in range(H):
            for z in range(D):
                name, props, nbt = blocks.get((x, y, z), ("minecraft:air", {}, None))
                key = (name, tuple(sorted(props.items())))
                if key not in index:
                    index[key] = len(palette)
                    e = {"Name": name}
                    if props:
                        e["Properties"] = dict(sorted(props.items()))
                    palette.append(e)
                b = {"pos": [x, y, z], "state": index[key]}
                if nbt:
                    b["nbt"] = nbt
                out.append(b)
    root = {"DataVersion": DATA_VERSION, "size": [W, H, D], "palette": palette, "blocks": out, "entities": []}
    buf = io.BytesIO()
    buf.write(struct.pack(">b", Tag.COMP))
    w_str(buf, "")
    w_payload(buf, root)
    return gzip.compress(buf.getvalue(), mtime=0), palette


# ---------------------------------------------------------------- vista previa
COL = {
    "snow_block": (240, 245, 250), "snow": (250, 252, 255), "packed_ice": (150, 185, 235), "blue_ice": (120, 165, 235),
    "stone_bricks": (125, 125, 125), "cracked_stone_bricks": (115, 115, 115), "mossy_stone_bricks": (105, 120, 95),
    "chiseled_stone_bricks": (135, 135, 135), "cobblestone": (110, 110, 110), "polished_andesite": (140, 145, 140),
    "spruce_log": (80, 58, 35), "stripped_spruce_log": (120, 90, 55), "spruce_planks": (115, 85, 50),
    "spruce_stairs": (115, 85, 50), "spruce_slab": (115, 85, 50), "spruce_fence": (100, 75, 45),
    "dark_oak_log": (60, 45, 30), "dark_oak_planks": (65, 45, 25), "dark_oak_stairs": (62, 42, 24),
    "dark_oak_slab": (65, 45, 25), "spruce_leaves": (45, 80, 55), "podzol": (95, 65, 30), "coarse_dirt": (115, 85, 60),
    "gravel": (130, 125, 120), "glowstone": (255, 220, 120), "gold_block": (250, 205, 60), "shroomlight": (245, 150, 70),
    "ochre_froglight": (245, 225, 150), "pearlescent_froglight": (235, 200, 230), "lantern": (255, 200, 90),
    "soul_lantern": (110, 220, 230), "campfire": (255, 130, 40), "glass_pane": (190, 220, 235), "blue_banner": (50, 70, 170),
    "blue_wall_banner": (50, 70, 170), "barrel": (125, 90, 55), "carved_pumpkin": (220, 130, 30), "lodestone": (150, 150, 155),
    "light_blue_wool": (90, 180, 220), "white_wool": (235, 235, 235), "blue_wool": (55, 65, 160), "blackstone": (45, 40, 45),
    "stone_brick_slab": (125, 125, 125), "end_rod": (250, 245, 235),
}


def color(name):
    short = name.split(":", 1)[1]
    if short in COL:
        return COL[short]
    if "nordic/" in short:
        return (150, 110, 70)
    if "decorations/" in short or "present" in short:
        return (200, 60, 60) if "present" in short else (210, 180, 120)
    if "bookshelf" in short:
        return (140, 95, 55)
    h = abs(hash(short)) % 255
    return (120 + h % 100, 100 + (h * 7) % 100, 90 + (h * 13) % 100)


def render_iso(path, ymax=H, scale=8):
    from PIL import Image, ImageDraw
    s = scale
    w = (W + D) * s + 40
    h = (W + D) * s // 2 + H * s + 40
    img = Image.new("RGB", (w, h), (30, 34, 44))
    dr = ImageDraw.Draw(img)
    ox, oy = D * s + 20, H * s + 20
    keys = sorted((p for p in blocks if blocks[p][0] != "minecraft:air" and p[1] < ymax),
                  key=lambda p: (p[0] + p[2], p[1]))
    for (x, y, z) in keys:
        name = blocks[(x, y, z)][0]
        r, g, b = color(name)
        sx = ox + (x - z) * s
        sy = oy + (x + z) * s // 2 - y * s
        top = [(sx, sy), (sx + s, sy + s // 2), (sx, sy + s), (sx - s, sy + s // 2)]
        left = [(sx - s, sy + s // 2), (sx, sy + s), (sx, sy + 2 * s), (sx - s, sy + s + s // 2)]
        right = [(sx, sy + s), (sx + s, sy + s // 2), (sx + s, sy + s + s // 2), (sx, sy + 2 * s)]
        hgt = 0.25 if name.endswith(":snow") or "carpet" in name else 1.0
        if hgt < 1:
            d = int(s * (1 - hgt))
            top = [(px, py + d) for px, py in top]
        dr.polygon(left, fill=(int(r * .72), int(g * .72), int(b * .72)))
        dr.polygon(right, fill=(int(r * .86), int(g * .86), int(b * .86)))
        dr.polygon(top, fill=(r, g, b))
    img.save(path)


def render_plan(path, ymax, scale=12):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W * scale, D * scale), (0, 0, 0))
    dr = ImageDraw.Draw(img)
    for x in range(W):
        for z in range(D):
            for y in range(ymax + OY, -1, -1):
                n = rawget(x, y, z)
                if n != "minecraft:air":
                    r, g, b = color(n)
                    f = 0.6 + 0.4 * y / max(1, ymax)
                    dr.rectangle([x * scale, z * scale, x * scale + scale - 1, z * scale + scale - 1],
                                 fill=(int(r * f), int(g * f), int(b * f)))
                    break
    img.save(path)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    data, palette = build_structure()
    with open(os.path.join(OUT, "lobby.nbt"), "wb") as f:
        f.write(data)
    datapack_lobby.write_zip(os.path.join(OUT, "kb_lobby_datapack.zip"), data)
    mods = sorted({p["Name"].split(":")[0] for p in palette})
    print(f"{N_LIGHTS} bloques de luz invisibles")
    print(f"{len(blocks)} bloques no-aire, {len(palette)} estados en la paleta, namespaces: {', '.join(mods)}")
    try:
        render_plan(os.path.join(OUT, "preview_planta.png"), ymax=6, scale=6)
        print("vistas previas generadas en", OUT)
    except ImportError:
        print("Pillow no instalado: sin vistas previas")
