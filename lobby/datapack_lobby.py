#!/usr/bin/env python3
"""Funciones del datapack del lobby (namespace kb_lobby) y empaquetado del zip.

    python3 lobby/datapack_lobby.py     # rehace salida/kb_lobby_datapack.zip con salida/lobby.nbt

generar_lobby.py también lo usa al generar la estructura.

Comandos (como op, de pie en el centro que quieras para el lobby):
    /function kb_lobby:colocar          coloca el lobby (también colocar_90, colocar_180, colocar_270)
    /function kb_lobby:girar            lo gira 90° en el mismo sitio
    /function kb_lobby:deshacer         lo quita y deja el terreno como estaba
    /function kb_lobby:confirmar        borra la copia del terreno (ya no se puede deshacer ni girar)
    /function kb_lobby:abrir / cerrar   quita / pone el muro de barrera (abrir lo llama apertura:final)
    /function kb_lobby:estado           dice cómo está

Cómo funciona:
- Un marker (tag kb_lobby) guarda el centro. Las acciones cargan la zona con forceload,
  esperan a que esté cargada y luego actúan desde el marker.
- Antes de colocar, el terreno original (161 x 53 x 161) se copia con clone a y -59..-7,
  justo debajo. deshacer y girar lo restauran desde ahí; deshacer y confirmar lo rellenan
  de deepslate. Así sobrevive a reinicios.
- El muro de barrera va un bloque por fuera de la estructura, de la base a 127 bloques
  por encima, y solo sustituye aire (al quitarlo solo se borran las barreras).
"""
import json
import os
import zipfile

HALF = 80                      # la estructura es de 161 x 161: centro ± 80
Y0, Y1 = -4, 48                # capas de la estructura respecto a los pies (53 de alto)
WALL = HALF + 1                # el muro va justo por fuera
WALL_TOP = 123                 # 128 bloques de alto desde la base
COPY_Y = -59                   # la copia del terreno ocupa y -59..-7 (encima de la bedrock)
SLICE = 3                      # 161 x 53 x 3 = 25599 bloques por clone/fill (límite 32768)
MIN_Y, MAX_Y = 4, 196          # alturas válidas del centro (copia debajo, muro por debajo de 320)

OBJ = "kb_lobby"
MARKER = "@e[type=minecraft:marker,tag=kb_lobby,limit=1]"
ADMIN = "@a[tag=kb_lobby_admin]"

# rotación: (nombre en /place, esquina de colocación, punto de spawn, ángulo de spawn)
ROTATIONS = [
    ("none", (-HALF, -HALF), (0, 37), 180),
    ("clockwise_90", (HALF, -HALF), (-37, 0), -90),
    ("180", (HALF, HALF), (0, -37), 0),
    ("counterclockwise_90", (-HALF, HALF), (37, 0), 90),
]

# acciones que esperan a que la zona esté cargada
COLOCAR, GIRAR, DESHACER, CONFIRMAR, ABRIR, CERRAR = range(1, 7)


def msg(text, color="yellow", target=ADMIN):
    return "tellraw %s %s" % (target, json.dumps(
        ["", {"text": "[Lobby] ", "color": "aqua", "bold": True}, {"text": text, "color": color}],
        ensure_ascii=False))


def slices():
    z = -HALF
    while z <= HALF:
        yield z, min(z + SLICE - 1, HALF)
        z += SLICE


def copia_guardar():
    return [f"clone ~{-HALF} ~{Y0} ~{a} ~{HALF} ~{Y1} ~{b} ~{-HALF} {COPY_Y} ~{a}" for a, b in slices()]


def copia_restaurar():
    top = COPY_Y + Y1 - Y0
    return [f"clone ~{-HALF} {COPY_Y} ~{a} ~{HALF} {top} ~{b} ~{-HALF} ~{Y0} ~{a}" for a, b in slices()]


def copia_borrar():
    top = COPY_Y + Y1 - Y0
    return [f"fill ~{-HALF} {COPY_Y} ~{a} ~{HALF} {top} ~{b} minecraft:deepslate" for a, b in slices()]


def muro(block, mode):
    w, t = WALL, WALL_TOP
    return [
        f"fill ~{-w} ~{Y0} ~{-w} ~{-w} ~{t} ~{w} {block} {mode}",
        f"fill ~{w} ~{Y0} ~{-w} ~{w} ~{t} ~{w} {block} {mode}",
        f"fill ~{-HALF} ~{Y0} ~{-w} ~{HALF} ~{t} ~{-w} {block} {mode}",
        f"fill ~{-HALF} ~{Y0} ~{w} ~{HALF} ~{t} ~{w} {block} {mode}",
    ]


def loaded_check():
    pts = list(range(-WALL, WALL, 16)) + [WALL]
    return " ".join(f"if loaded ~{x} ~ ~{z}" for x in pts for z in pts)


def pedir(accion, needs_marker=True):
    """Cuerpo de un comando de admin: comprueba y deja la acción en cola."""
    lines = [f"tag @s add kb_lobby_admin"]
    busy = f"score #ocupado {OBJ} matches 1"
    lines.append(f"execute if {busy} run " + msg("Hay otra acción en marcha, espera unos segundos.", "red", "@s"))
    if needs_marker:
        lines.append(f"execute unless {busy} unless entity {MARKER} run "
                     + msg("No encuentro el lobby: acércate a él (o no está colocado).", "red", "@s"))
        cond = f"unless {busy} if entity {MARKER}"
    else:
        cond = f"unless {busy}"
    return lines, cond


def functions():
    f = {}
    load = [
        f"scoreboard objectives add {OBJ} dummy",
        f"execute unless score #estado {OBJ} matches 0.. run scoreboard players set #estado {OBJ} 0",
        f"execute unless score #rot {OBJ} matches 0.. run scoreboard players set #rot {OBJ} 0",
        f"scoreboard players set #cuatro {OBJ} 4",
    ]
    f["load"] = load

    estados = (f"Estado: #estado 0 = sin colocar, 2 = colocado (se puede deshacer y girar), "
               f"3 = confirmado.")

    # ---------------------------------------------------------------- colocar
    for i, (name, _, _, _) in enumerate(ROTATIONS):
        lines, cond = pedir(COLOCAR, needs_marker=False)
        grados = ["", "_90", "_180", "_270"][i]
        lines.insert(0, f"# Coloca el lobby con su centro aquí, girado {i * 90}°. Ponte de pie en el centro.")
        lines += [
            f"execute {cond} unless score #estado {OBJ} matches 0 run "
            + msg("Ya hay un lobby colocado. Usa kb_lobby:girar, kb_lobby:deshacer o kb_lobby:estado.", "red", "@s"),
            f"execute {cond} if score #estado {OBJ} matches 0 run scoreboard players set #rot_nueva {OBJ} {i}",
            f"execute {cond} if score #estado {OBJ} matches 0 align xyz positioned ~0.5 ~ ~0.5 run function kb_lobby:interno/colocar_inicio",
        ]
        f["colocar" + grados] = lines

    f["interno/colocar_inicio"] = [
        f"kill @e[type=minecraft:marker,tag=kb_lobby]",
        f"execute unless dimension minecraft:overworld run " + msg("El lobby solo se puede colocar en el overworld.", "red", "@s"),
        f"execute if dimension minecraft:overworld run summon minecraft:marker ~ ~ ~ {{Tags:[\"kb_lobby\"]}}",
        f"execute store result score #y {OBJ} run data get entity {MARKER} Pos[1]",
        f"execute if entity {MARKER} unless score #y {OBJ} matches {MIN_Y}..{MAX_Y} run "
        + msg(f"Ponte entre y={MIN_Y} e y={MAX_Y}: la copia del terreno va debajo y el muro llega 123 bloques por encima.", "red", "@s"),
        f"execute if entity {MARKER} unless score #y {OBJ} matches {MIN_Y}..{MAX_Y} run kill {MARKER}",
        f"execute if entity {MARKER} run scoreboard players set #accion {OBJ} {COLOCAR}",
        f"execute if entity {MARKER} run function kb_lobby:interno/pedir",
    ]

    # ---------------------------------------------------------------- girar / deshacer / confirmar
    lines, cond = pedir(GIRAR)
    lines.insert(0, "# Gira el lobby 90° en el sentido de las agujas del reloj, en el mismo sitio.")
    lines += [
        f"execute {cond} unless score #estado {OBJ} matches 2 run "
        + msg("Solo se puede girar un lobby colocado y sin confirmar.", "red", "@s"),
        f"execute {cond} if score #estado {OBJ} matches 2 run scoreboard players operation #rot_nueva {OBJ} = #rot {OBJ}",
        f"execute {cond} if score #estado {OBJ} matches 2 run scoreboard players add #rot_nueva {OBJ} 1",
        f"execute {cond} if score #estado {OBJ} matches 2 run scoreboard players operation #rot_nueva {OBJ} %= #cuatro {OBJ}",
        f"execute {cond} if score #estado {OBJ} matches 2 run scoreboard players set #accion {OBJ} {GIRAR}",
        f"execute {cond} if score #estado {OBJ} matches 2 run function kb_lobby:interno/pedir",
    ]
    f["girar"] = lines

    for name, accion, texto, estado_ok, err in [
        ("deshacer", DESHACER, "# Quita el lobby y el muro y deja el terreno como estaba.", "2",
         "Solo se puede deshacer un lobby colocado y sin confirmar."),
        ("confirmar", CONFIRMAR, "# Da el lobby por bueno: borra la copia del terreno (ya no se puede deshacer ni girar).", "2",
         "No hay un lobby colocado sin confirmar."),
        ("abrir", ABRIR, "# Quita el muro de barrera. Lo llama apertura:final (tag #apertura:abrir).", "2..3",
         "No hay un lobby colocado."),
        ("cerrar", CERRAR, "# Vuelve a poner el muro de barrera alrededor del lobby.", "2..3",
         "No hay un lobby colocado."),
    ]:
        lines, cond = pedir(accion)
        lines.insert(0, texto)
        lines += [
            f"execute {cond} unless score #estado {OBJ} matches {estado_ok} run " + msg(err, "red", "@s"),
            f"execute {cond} if score #estado {OBJ} matches {estado_ok} run scoreboard players set #accion {OBJ} {accion}",
            f"execute {cond} if score #estado {OBJ} matches {estado_ok} run function kb_lobby:interno/pedir",
        ]
        f[name] = lines

    f["estado"] = [
        "tag @s add kb_lobby_admin",
        f"execute if score #estado {OBJ} matches 0 run " + msg("No hay lobby colocado.", "yellow", "@s"),
        f"execute if score #estado {OBJ} matches 2 run " + msg("Lobby colocado. Se puede girar o deshacer; usa kb_lobby:confirmar cuando esté bien.", "yellow", "@s"),
        f"execute if score #estado {OBJ} matches 3 run " + msg("Lobby colocado y confirmado.", "yellow", "@s"),
        f"execute if score #estado {OBJ} matches 2.. as {MARKER} run tellraw @s "
        "[\"\",{\"text\":\"[Lobby] \",\"color\":\"aqua\",\"bold\":true},{\"text\":\"Centro: \",\"color\":\"yellow\"},"
        "{\"nbt\":\"Pos\",\"entity\":\"@s\",\"color\":\"gold\"},{\"text\":\"  giro: \",\"color\":\"yellow\"},"
        "{\"score\":{\"name\":\"#rot\",\"objective\":\"kb_lobby\"},\"color\":\"gold\"},{\"text\":\" x 90°\",\"color\":\"gold\"}]",
        f"execute if score #estado {OBJ} matches 2.. unless entity {MARKER} run "
        + msg("El marker del centro no está cargado: acércate al lobby.", "yellow", "@s"),
    ]

    # ---------------------------------------------------------------- espera hasta que la zona esté cargada
    f["interno/pedir"] = [
        f"scoreboard players set #ocupado {OBJ} 1",
        f"scoreboard players set #intentos {OBJ} 0",
        f"execute at {MARKER} run forceload add ~{-WALL} ~{-WALL} ~{WALL} ~{WALL}",
        "schedule function kb_lobby:interno/esperar 5t",
    ]
    f["interno/esperar"] = [
        f"scoreboard players add #intentos {OBJ} 1",
        f"execute at {MARKER} {loaded_check()} run function kb_lobby:interno/ejecutar",
        f"execute if score #ocupado {OBJ} matches 1 if score #intentos {OBJ} matches ..120 run schedule function kb_lobby:interno/esperar 10t",
        f"execute if score #ocupado {OBJ} matches 1 if score #intentos {OBJ} matches 121.. run function kb_lobby:interno/fallo",
    ]
    f["interno/fallo"] = [
        f"scoreboard players set #ocupado {OBJ} 0",
        f"execute at {MARKER} run forceload remove ~{-WALL} ~{-WALL} ~{WALL} ~{WALL}",
        f"execute if score #accion {OBJ} matches {COLOCAR} run kill {MARKER}",
        msg("La zona no terminó de cargar en 60 s; no se ha hecho nada. Vuelve a intentarlo.", "red"),
    ]
    f["interno/ejecutar"] = [
        "# Se ejecuta en el centro (marker) con toda la zona cargada.",
        f"scoreboard players set #ocupado {OBJ} 0",
        f"execute if score #accion {OBJ} matches {COLOCAR} run function kb_lobby:interno/hacer_colocar",
        f"execute if score #accion {OBJ} matches {GIRAR} run function kb_lobby:interno/hacer_girar",
        f"execute if score #accion {OBJ} matches {DESHACER} run function kb_lobby:interno/hacer_deshacer",
        f"execute if score #accion {OBJ} matches {CONFIRMAR} run function kb_lobby:interno/hacer_confirmar",
        f"execute if score #accion {OBJ} matches {ABRIR} run function kb_lobby:interno/barrera_quitar",
        f"execute if score #accion {OBJ} matches {ABRIR} run " + msg("Muro de barrera quitado.", "green"),
        f"execute if score #accion {OBJ} matches {CERRAR} run function kb_lobby:interno/barrera_poner",
        f"execute if score #accion {OBJ} matches {CERRAR} run " + msg("Muro de barrera puesto.", "green"),
        f"forceload remove ~{-WALL} ~{-WALL} ~{WALL} ~{WALL}",
    ]

    # ---------------------------------------------------------------- acciones
    f["interno/hacer_colocar"] = [
        "function kb_lobby:interno/copia_guardar",
        f"scoreboard players operation #rot {OBJ} = #rot_nueva {OBJ}",
        "function kb_lobby:interno/poner",
        "function kb_lobby:interno/barrera_poner",
        "gamerule spawnRadius 0",
        f"scoreboard players set #estado {OBJ} 2",
        msg("Lobby colocado, con muro de barrera y spawn. Puedes usar kb_lobby:girar o kb_lobby:deshacer; "
            "cuando esté bien, kb_lobby:confirmar.", "green"),
    ]
    f["interno/hacer_girar"] = [
        "function kb_lobby:interno/copia_restaurar",
        f"scoreboard players operation #rot {OBJ} = #rot_nueva {OBJ}",
        "function kb_lobby:interno/poner",
        msg("Lobby girado 90°.", "green"),
    ]
    f["interno/hacer_deshacer"] = [
        "function kb_lobby:interno/barrera_quitar",
        "function kb_lobby:interno/copia_restaurar",
        "function kb_lobby:interno/copia_borrar",
        f"kill {MARKER}",
        f"scoreboard players set #estado {OBJ} 0",
        msg("Lobby quitado y terreno restaurado. El spawn del mundo sigue donde estaba el lobby: cámbialo con /setworldspawn.", "green"),
    ]
    f["interno/hacer_confirmar"] = [
        "function kb_lobby:interno/copia_borrar",
        f"scoreboard players set #estado {OBJ} 3",
        msg("Lobby confirmado: copia del terreno borrada.", "green"),
    ]

    poner = ["# Coloca la estructura y el spawn según #rot."]
    for i, (name, (cx, cz), (sx, sz), ang) in enumerate(ROTATIONS):
        poner.append(f"execute if score #rot {OBJ} matches {i} run place template kb:lobby ~{cx} ~{Y0} ~{cz} {name}")
        poner.append(f"execute if score #rot {OBJ} matches {i} run setworldspawn ~{sx} ~ ~{sz} {ang}")
    f["interno/poner"] = poner

    f["interno/copia_guardar"] = ["# Copia el terreno original debajo (y %d..%d)." % (COPY_Y, COPY_Y + Y1 - Y0)] + copia_guardar()
    f["interno/copia_restaurar"] = copia_restaurar()
    f["interno/copia_borrar"] = copia_borrar()
    f["interno/barrera_poner"] = muro("minecraft:barrier", "replace minecraft:air")
    f["interno/barrera_quitar"] = muro("minecraft:air", "replace minecraft:barrier")
    return f


def write_zip(path, nbt):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("pack.mcmeta", json.dumps({"pack": {"pack_format": 15, "description": "KB Server - lobby de invierno"}}))
        z.writestr("data/kb/structures/lobby.nbt", nbt)
        for name, lines in functions().items():
            z.writestr(f"data/kb_lobby/functions/{name}.mcfunction", "\n".join(lines) + "\n")
        z.writestr("data/minecraft/tags/functions/load.json", json.dumps({"values": ["kb_lobby:load"]}))
        # apertura:final llama a #apertura:abrir
        z.writestr("data/apertura/tags/functions/abrir.json", json.dumps({"values": ["kb_lobby:abrir"]}))


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salida")
    with open(os.path.join(out, "lobby.nbt"), "rb") as fh:
        nbt = fh.read()
    write_zip(os.path.join(out, "kb_lobby_datapack.zip"), nbt)
    print("datapack escrito en", os.path.join(out, "kb_lobby_datapack.zip"))
