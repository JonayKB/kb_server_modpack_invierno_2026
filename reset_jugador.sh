#!/usr/bin/env bash
# Resetea a un jugador para que vuelva a entrar como si fuera nuevo.
#
#   ./reset_jugador.sh <carpeta_del_servidor> <nombre|uuid>
#   ./reset_jugador.sh <carpeta_del_servidor> <nombre|uuid> --mantener-discord
#   ./reset_jugador.sh <carpeta_del_servidor> <nombre|uuid> --dry-run
#
# Con el servidor APAGADO. No borra nada: mueve los ficheros a
# <servidor>/resets/<nombre>_<fecha>/ para poder deshacerlo.
#
# Qué quita:
#   - Todo fichero del mundo con su UUID en el nombre: playerdata (inventario,
#     posición y datos de mods: Curios, Iron's Spells, skill trees, waystones
#     descubiertas, tags...), advancements, stats, su equipo personal de FTB
#     Teams y su progreso de FTB Quests, sus datos de Open Parties and Claims...
#   - Su clase de Class Enhancement (data/class_enhancement_data.dat), para
#     que le vuelva a salir el menú de elegir clase.
#   - Su vínculo con Discord en config/kb_discord_auth/links.json (tendrá que
#     volver a iniciar sesión con Discord), salvo con --mantener-discord.
#
# Qué NO toca: lo construido, sus tumbas, mascotas o monturas, sus waystones
# colocadas, ni una party de FTB Teams compartida con otros (avisa si la hay).
set -euo pipefail

usage() { sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

DRY_RUN=0 KEEP_DISCORD=0 ARGS=()
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --mantener-discord) KEEP_DISCORD=1 ;;
        -h|--help) usage ;;
        -*) echo "Opción desconocida: $arg" >&2; exit 1 ;;
        *) ARGS+=("$arg") ;;
    esac
done
[ "${#ARGS[@]}" -eq 2 ] || usage

SERVER="$(cd "${ARGS[0]}" && pwd)"
TARGET="${ARGS[1]}"
command -v python3 >/dev/null || { echo "Hace falta python3" >&2; exit 1; }

LEVEL="$(sed -n 's/^level-name=//p' "$SERVER/server.properties" 2>/dev/null | tr -d '\r')"
WORLD="$SERVER/${LEVEL:-world}"
[ -d "$WORLD" ] || { echo "No encuentro el mundo en $WORLD" >&2; exit 1; }
LINKS="$SERVER/config/kb_discord_auth/links.json"

# ¿Está el servidor encendido? (mira si algún java tiene esta carpeta como cwd)
for pid in $(pgrep -x java 2>/dev/null || true); do
    if [ "$(readlink "/proc/$pid/cwd" 2>/dev/null)" = "$SERVER" ]; then
        echo "El servidor parece encendido (java, PID $pid). Apágalo antes." >&2
        exit 1
    fi
done

# Nombre o UUID -> UUID y nombre, mirando usercache.json y links.json
read -r UUID NAME < <(python3 -I - "$TARGET" "$SERVER/usercache.json" "$LINKS" <<'PY'
import json, re, sys
target, usercache, links = sys.argv[1], sys.argv[2], sys.argv[3]
pairs = []
try:
    pairs += [(e["uuid"], e["name"]) for e in json.load(open(usercache, encoding="utf-8"))]
except (OSError, ValueError, KeyError):
    pass
try:
    data = json.load(open(links, encoding="utf-8"))
    pairs += [(u, r.get("minecraftName") or "?") for u, r in (data.get("links") or {}).items()]
except (OSError, ValueError, AttributeError):
    pass
if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", target):
    uuid = target.lower()
    name = next((n for u, n in pairs if u.lower() == uuid), "?")
    print(uuid, name)
else:
    hit = next(((u, n) for u, n in pairs if n.lower() == target.lower()), None)
    print(*(hit if hit else ("", "")))
PY
)
[ -n "$UUID" ] || { echo "No encuentro a '$TARGET' en usercache.json ni en links.json. Pásame su UUID." >&2; exit 1; }
PLAIN="${UUID//-/}"
echo "Jugador: $NAME ($UUID)"
echo "Mundo:   $WORLD"
echo

# Ficheros del mundo con su UUID en el nombre (con o sin guiones)
mapfile -t FILES < <(find "$WORLD" -type f \( -iname "*$UUID*" -o -iname "*$PLAIN*" \) | sort)

HAS_LINK=0
if [ "$KEEP_DISCORD" -eq 0 ] && [ -f "$LINKS" ] && grep -qi "\"$UUID\"" "$LINKS"; then
    HAS_LINK=1
fi

# Datos compartidos del mundo (data/*.dat, NBT comprimido) con una entrada suya.
# Class Enhancement guarda ahí la clase elegida: si no se quita, no le vuelve
# a salir el menú. Los demás solo se avisan.
NBT_PY="$(mktemp)"
trap 'rm -f "$NBT_PY"' EXIT
cat >"$NBT_PY" <<'PY'
import gzip, io, os, struct, sys

def rd(f, n):
    b = f.read(n)
    if len(b) != n:
        raise EOFError
    return b

def rstr(f):
    return rd(f, struct.unpack(">H", rd(f, 2))[0]).decode("utf-8", "surrogatepass")

def wstr(f, s):
    b = s.encode("utf-8", "surrogatepass")
    f.write(struct.pack(">H", len(b)) + b)

FMT = {1: ">b", 2: ">h", 3: ">i", 4: ">q", 5: ">f", 6: ">d"}
ARR = {7: ">b", 11: ">i", 12: ">q"}

def rpay(f, t):
    if t in FMT:
        fm = FMT[t]; return struct.unpack(fm, rd(f, struct.calcsize(fm)))[0]
    if t in ARR:
        n = struct.unpack(">i", rd(f, 4))[0]; fm = ARR[t]
        return list(struct.unpack(">%d%s" % (n, fm[1]), rd(f, n * struct.calcsize(fm))))
    if t == 8:
        return rstr(f)
    if t == 9:
        et = rd(f, 1)[0]; n = struct.unpack(">i", rd(f, 4))[0]
        return (et, [rpay(f, et) for _ in range(n)])
    if t == 10:
        d = {}
        while True:
            ct = rd(f, 1)[0]
            if ct == 0:
                return d
            k = rstr(f); d[k] = (ct, rpay(f, ct))
    raise ValueError("tag %d" % t)

def wpay(f, t, v):
    if t in FMT:
        f.write(struct.pack(FMT[t], v))
    elif t in ARR:
        f.write(struct.pack(">i", len(v)) + struct.pack(">%d%s" % (len(v), ARR[t][1]), *v))
    elif t == 8:
        wstr(f, v)
    elif t == 9:
        et, items = v
        f.write(bytes([et]) + struct.pack(">i", len(items)))
        for it in items:
            wpay(f, et, it)
    elif t == 10:
        for k, (ct, cv) in v.items():
            f.write(bytes([ct])); wstr(f, k); wpay(f, ct, cv)
        f.write(b"\0")

def load(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass
    f = io.BytesIO(raw)
    t = rd(f, 1)[0]; name = rstr(f)
    return t, name, rpay(f, t)

def save(path, t, name, v):
    f = io.BytesIO(); f.write(bytes([t])); wstr(f, name); wpay(f, t, v)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(gzip.compress(f.getvalue()))
    os.replace(tmp, path)

mode, path, uuid = sys.argv[1], sys.argv[2], sys.argv[3].lower()
if mode == "has-raw":
    # ¿Aparece el UUID en texto dentro del fichero (descomprimido)?
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
        sys.exit(0 if uuid.encode() in raw.lower() else 1)
    except OSError:
        sys.exit(1)

t, name, root = load(path)
data = root.get("data", (10, {}))[1]
classes = data.get("playerClasses", (10, {}))[1]
keys = [k for k in classes if k.lower() == uuid]
if mode == "class-get":
    for k in keys:
        print(classes[k][1])
    sys.exit(0 if keys else 1)
if mode == "class-del":
    for k in keys:
        del classes[k]
    save(path, t, name, root)
PY

CLASS_DAT="$WORLD/data/class_enhancement_data.dat"
CLASS_NAME=""
if [ -f "$CLASS_DAT" ]; then
    CLASS_NAME="$(python3 -I "$NBT_PY" class-get "$CLASS_DAT" "$UUID" || true)"
fi

OTHER_DAT=()
if [ -d "$WORLD/data" ]; then
    while IFS= read -r f; do
        [ "$f" = "$CLASS_DAT" ] && continue
        python3 -I "$NBT_PY" has-raw "$f" "$UUID" && OTHER_DAT+=("$f")
    done < <(find "$WORLD" -path "*/data/*.dat" -type f | sort)
fi

if [ "${#FILES[@]}" -eq 0 ] && [ "$HAS_LINK" -eq 0 ] && [ -z "$CLASS_NAME" ]; then
    echo "No hay nada suyo que quitar."
    exit 0
fi

echo "Se moverán a la copia de seguridad:"
for f in "${FILES[@]}"; do echo "  ${f#"$SERVER/"}"; done
[ "$HAS_LINK" -eq 1 ] && echo "  (y su entrada en config/kb_discord_auth/links.json)"
[ -n "$CLASS_NAME" ] && echo "  (y su clase '$CLASS_NAME' en ${CLASS_DAT#"$SERVER/"})"

if [ "${#OTHER_DAT[@]}" -gt 0 ]; then
    echo
    echo "Aviso: su UUID aparece en otros datos compartidos del mundo. No los toco:"
    for f in "${OTHER_DAT[@]}"; do echo "  ${f#"$SERVER/"}"; done
fi

# Party de FTB Teams compartida: no se toca, solo se avisa
if [ -d "$WORLD/ftbteams" ]; then
    mapfile -t PARTIES < <(grep -rli -e "$UUID" "$WORLD/ftbteams" 2>/dev/null \
        | grep -viE "$UUID|$PLAIN" || true)
    if [ "${#PARTIES[@]}" -gt 0 ]; then
        echo
        echo "Aviso: aparece en otros ficheros de FTB Teams (seguramente una party)."
        echo "No los toco. Si quieres sacarlo, con el server encendido usa /ftbteams."
        for f in "${PARTIES[@]}"; do echo "  ${f#"$SERVER/"}"; done
    fi
fi

if [ "$DRY_RUN" -eq 1 ]; then
    echo; echo "--dry-run: no se ha cambiado nada."
    exit 0
fi

echo
read -r -p "¿Seguir? [s/N] " ok
[[ "$ok" =~ ^[sS]$ ]] || { echo "Cancelado."; exit 1; }

BACKUP="$SERVER/resets/${NAME}_$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
for f in "${FILES[@]}"; do
    rel="${f#"$SERVER/"}"
    mkdir -p "$BACKUP/$(dirname "$rel")"
    mv "$f" "$BACKUP/$rel"
done

if [ -n "$CLASS_NAME" ]; then
    rel="${CLASS_DAT#"$SERVER/"}"
    mkdir -p "$BACKUP/$(dirname "$rel")"
    cp -p "$CLASS_DAT" "$BACKUP/$rel"
    python3 -I "$NBT_PY" class-del "$CLASS_DAT" "$UUID"
fi

if [ "$HAS_LINK" -eq 1 ]; then
    mkdir -p "$BACKUP/config/kb_discord_auth"
    cp -p "$LINKS" "$BACKUP/config/kb_discord_auth/links.json"
    python3 -I - "$LINKS" "$UUID" <<'PY'
import json, os, sys
path, uuid = sys.argv[1], sys.argv[2].lower()
with open(path, encoding="utf-8") as f:
    data = json.load(f)
links = data.get("links") or {}
for key in [k for k in links if k.lower() == uuid]:
    del links[key]
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
os.replace(tmp, path)
PY
fi

echo
echo "Hecho. Copia de seguridad en: $BACKUP"
echo "Para deshacerlo: cp -a \"$BACKUP\"/. \"$SERVER\"/"
