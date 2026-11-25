#!/usr/bin/env bash
# Publica el modpack para KB MC Launcher en me.jonaykb.com/modpacks/<id>/
#
#   ./publicar.sh                  sube la versión de parche (1.0.3 -> 1.0.4)
#   ./publicar.sh 1.1.0            publica con esa versión
#   ./publicar.sh --dry-run        muestra qué cambiaría y genera el manifiesto sin subir nada
#   ./publicar.sh --force          publica aunque haya cambios sin commit
#   ./publicar.sh --con-zips       sube también los zips completos (launchers anteriores a la 1.10)
#   ./publicar.sh --verificar-todo comprueba en el servidor el hash de todos los archivos, no solo los nuevos
#
# Cada archivo (mods/*.jar y todo overrides/) se sube suelto y se guarda por su
# SHA-256 en objects/ab/abcdef..., así un archivo que no cambia no se vuelve a
# subir ni a descargar, y uno repetido en dos carpetas se guarda una vez. El
# manifiesto (manifest-<versión>.json) lista cada ruta con su hash y tamaño; el
# launcher lo compara con lo instalado y solo baja lo que cambia.
#
# ajustes-jugador.txt dice qué overrides son ajustes del jugador (configs de
# cliente...): esos se respetan si los cambia. El resto se deja siempre como
# lo publica el modpack.
#
# Orden de subida: objetos nuevos a .incoming/, se comprueba su hash en el
# servidor y se mueven a objects/; luego el manifiesto, y latest.json el último:
# hasta ese momento los jugadores siguen viendo la versión anterior. Se conservan
# los objetos de la versión anterior por si alguien la estaba descargando.
set -euo pipefail

MODPACK_ID="${MODPACK_ID:-terramity-awakened}"
LOADER="forge"
LOADER_VERSION="47.4.20"
MC_VERSION="1.20.1"

SSH_HOST="${SSH_HOST:-192.168.0.13}"
SSH_PORT="${SSH_PORT:-6454}"
SSH_USER="${SSH_USER:-serverkb}"
REMOTE_BASE="${REMOTE_BASE:-/var/www/modpacks}"
PUBLIC_BASE="${PUBLIC_BASE:-https://me.jonaykb.com/modpacks}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_DIR="$REMOTE_BASE/$MODPACK_ID"
PUBLIC_DIR="$PUBLIC_BASE/$MODPACK_ID"
SSH=(ssh -o ConnectTimeout=15 -p "$SSH_PORT" "$SSH_USER@$SSH_HOST")
RSYNC_SSH="ssh -o ConnectTimeout=15 -p $SSH_PORT"

DRY_RUN=0 FORCE=0 WITH_ZIPS=0 VERIFY_ALL=0 VERSION=""
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --force) FORCE=1 ;;
        --con-zips) WITH_ZIPS=1 ;;
        --verificar-todo) VERIFY_ALL=1 ;;
        -h|--help) sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        [0-9]*.[0-9]*.[0-9]*) VERSION="$arg" ;;
        *) echo "Argumento desconocido: $arg" >&2; exit 1 ;;
    esac
done

info() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mAviso:\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

for cmd in git git-lfs zip unzip rsync ssh python3 curl sha256sum numfmt; do
    command -v "$cmd" >/dev/null || fail "falta el comando '$cmd'"
done

cd "$REPO"

# 1. Comprobaciones del repo
if [[ -n "$(git status --porcelain)" && $FORCE -eq 0 ]]; then
    git status --short
    fail "hay cambios sin commit. Haz commit o usa --force."
fi

info "Descargando archivos de Git LFS que falten"
git lfs pull

info "Comprobando que los jars son reales y no punteros de LFS"
broken=()
for jar in mods/*.jar; do
    unzip -tq "$jar" >/dev/null 2>&1 || broken+=("$jar")
done
(( ${#broken[@]} == 0 )) || fail "jars inválidos: ${broken[*]}"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# 2. Lo publicado ahora mismo: latest.json y su manifiesto, separados por un
#    carácter 0x1E (en --dry-run sin conexión se sigue comparando con nada)
info "Leyendo la versión publicada"
REMOTE_OK=1
"${SSH[@]}" "cd '$REMOTE_DIR' 2>/dev/null && [ -f latest.json ] || exit 0
    cat latest.json; printf '\n\036\n'
    m=\$(python3 -c 'import json; print(json.load(open(\"latest.json\")).get(\"manifestUrl\", \"\").rsplit(\"/\", 1)[-1])' 2>/dev/null)
    if [ -n \"\$m\" ] && [ -f \"\$m\" ]; then cat \"\$m\"; fi" > "$WORK/remote.txt" || REMOTE_OK=0
if (( REMOTE_OK == 0 )); then
    (( DRY_RUN == 1 )) || fail "no se pudo conectar con $SSH_HOST"
    warn "sin conexión con el servidor; se compara con nada."
    : > "$WORK/remote.txt"
fi
python3 - "$WORK" <<'EOF'
import sys
work = sys.argv[1]
latest, _, manifest = open(f"{work}/remote.txt", encoding="utf-8").read().partition("\n\x1e\n")
open(f"{work}/remote.json", "w", encoding="utf-8").write(latest)
open(f"{work}/remote-manifest.json", "w", encoding="utf-8").write(manifest)
EOF

CURRENT="$(python3 -c '
import json, sys
try: print(json.load(open(sys.argv[1]))["version"])
except Exception: print("")
' "$WORK/remote.json")"

if [[ -z "$VERSION" ]]; then
    if [[ -z "$CURRENT" ]]; then
        VERSION="1.0.0"
    else
        VERSION="$(python3 -c '
import sys
major, minor, patch = sys.argv[1].split(".")[:3]
print(f"{major}.{minor}.{int(patch) + 1}")
' "$CURRENT")"
    fi
fi
[[ "$VERSION" != "$CURRENT" ]] || fail "la versión $VERSION ya está publicada"
info "Versión: ${CURRENT:-ninguna} -> $VERSION"

# 3. Manifiesto: hash de cada archivo y diferencias con lo publicado
MANIFEST="manifest-$VERSION.json"
info "Calculando el hash de cada archivo"
python3 - "$REPO" "$WORK" "$MANIFEST" "$MODPACK_ID" "$VERSION" <<'EOF'
import fnmatch, hashlib, json, os, sys
repo, work, manifest_name, modpack_id, version = sys.argv[1:]

settings_file = f"{repo}/ajustes-jugador.txt"
player_patterns = []
if os.path.exists(settings_file):
    for line in open(settings_file, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            player_patterns.append(line.lower())

def is_player_setting(rel):
    return not rel.startswith("mods/") and any(fnmatch.fnmatchcase(rel.lower(), p) for p in player_patterns)

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

sources = []  # (ruta dentro de la instancia, archivo local)
for name in sorted(os.listdir(f"{repo}/mods")):
    if name.endswith(".jar") and os.path.isfile(f"{repo}/mods/{name}"):
        sources.append((f"mods/{name}", f"{repo}/mods/{name}"))
for root, dirs, files in os.walk(f"{repo}/overrides"):
    dirs.sort()
    for name in sorted(files):
        local = os.path.join(root, name)
        rel = os.path.relpath(local, f"{repo}/overrides").replace(os.sep, "/")
        if rel.startswith("mods/"):
            sys.exit(f"overrides/{rel}: los mods van en mods/, no en overrides/")
        sources.append((rel, local))

files, objects, seen = [], {}, set()
for rel, local in sources:
    if rel.lower() in seen:
        sys.exit(f"ruta repetida sin distinguir mayúsculas (en Windows chocan): {rel}")
    seen.add(rel.lower())
    digest, size = sha256(local), os.path.getsize(local)
    entry = {"path": rel, "sha256": digest, "size": size}
    if is_player_setting(rel):
        entry["playerSetting"] = True
    files.append(entry)
    objects.setdefault(digest, (local, size))

manifest = {
    "formatVersion": 1,
    "modpackId": modpack_id,
    "version": version,
    "objectsUrl": "objects/",
    "syncDirs": ["mods"],
    "files": files,
}
with open(f"{work}/{manifest_name}", "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))
with open(f"{work}/objects.tsv", "w", encoding="utf-8") as f:
    for digest, (local, size) in sorted(objects.items()):
        f.write(f"{digest}\t{size}\t{local}\n")

total = sum(size for _, size in objects.values())
dupes = sum(f["size"] for f in files) - total
print(f"    {len(files)} archivos, {len(objects)} distintos, {total / 2**30:.2f} GiB"
      + (f" ({dupes / 2**20:.0f} MiB repetidos se guardan una vez)" if dupes else ""))
print(f"    {sum(1 for f in files if f.get('playerSetting'))} son ajustes del jugador (ajustes-jugador.txt)")

# Diferencias con el manifiesto publicado
try:
    old = {f["path"]: f["sha256"] for f in json.load(open(f"{work}/remote-manifest.json"))["files"]}
except Exception:
    old = None
if old is None:
    print("    (no hay manifiesto publicado con el que comparar)")
else:
    new = {f["path"]: f["sha256"] for f in files}
    added = sorted(p for p in new if p not in old)
    removed = sorted(p for p in old if p not in new)
    changed = sorted(p for p in new if p in old and old[p] != new[p])
    def show(sign, paths, color):
        mods = [p for p in paths if p.startswith("mods/")]
        for p in mods:
            print(f"    \033[{color}m{sign} {p}\033[0m")
        if len(paths) > len(mods):
            print(f"    \033[{color}m{sign} {len(paths) - len(mods)} archivo(s) de overrides\033[0m")
    show("+", added, "32")
    show("-", removed, "31")
    show("~", changed, "33")
    if not (added or removed or changed):
        print("    Sin cambios en los archivos respecto a la versión publicada")
EOF
MANIFEST_SHA="$(sha256sum "$WORK/$MANIFEST" | cut -d' ' -f1)"

# 4. Objetos que faltan en el servidor
if (( REMOTE_OK == 1 )); then
    "${SSH[@]}" "cd '$REMOTE_DIR/objects' 2>/dev/null && find . -type f -printf '%f\n' || true" | sort -u > "$WORK/remote-objects.txt"
else
    : > "$WORK/remote-objects.txt"
fi
cut -f1 "$WORK/objects.tsv" | sort -u > "$WORK/needed.txt"
comm -23 "$WORK/needed.txt" "$WORK/remote-objects.txt" > "$WORK/missing.txt"
# Líneas de objects.tsv de lo que falta (sha, tamaño, archivo local)
awk -F'\t' 'NR == FNR { missing[$1] = 1; next } $1 in missing' "$WORK/missing.txt" "$WORK/objects.tsv" > "$WORK/upload.tsv"

mkdir -p "$WORK/incoming"
: > "$WORK/incoming/SHA256SUMS"
UPLOAD_BYTES=0
while IFS=$'\t' read -r sha size local; do
    mkdir -p "$WORK/incoming/${sha:0:2}"
    ln -s "$local" "$WORK/incoming/${sha:0:2}/$sha"
    printf '%s  %s\n' "$sha" "${sha:0:2}/$sha" >> "$WORK/incoming/SHA256SUMS"
    UPLOAD_BYTES=$((UPLOAD_BYTES + size))
done < "$WORK/upload.tsv"
info "Archivos nuevos a subir: $(wc -l < "$WORK/upload.tsv") ($(numfmt --to=iec "$UPLOAD_BYTES"))"

# 5. latest.json (conserva images y changelog de la versión publicada)
MODS_ZIP="mods-$VERSION.zip"
OVERRIDES_ZIP="overrides-$VERSION.zip"
python3 - "$WORK/remote.json" "$WORK/latest.json" "$WITH_ZIPS" <<EOF
import json, sys
try:
    old = json.load(open(sys.argv[1]))
except Exception:
    old = {}
new = {
    "id": "$MODPACK_ID-v$VERSION",
    "modpackId": "$MODPACK_ID",
    "version": "$VERSION",
    "loader": "$LOADER",
    "loaderVersion": "$LOADER_VERSION",
    "minecraftVersion": "$MC_VERSION",
    "manifestUrl": "$PUBLIC_DIR/$MANIFEST",
    "manifestSha256": "$MANIFEST_SHA",
}
if sys.argv[3] == "1":
    new["modsUrl"] = "$PUBLIC_DIR/$MODS_ZIP"
    new["overridesUrl"] = "$PUBLIC_DIR/$OVERRIDES_ZIP"
new["images"] = old.get("images", [])
if "changelog" in old:
    new["changelog"] = old["changelog"]
json.dump(new, open(sys.argv[2], "w"), ensure_ascii=False, indent=2)
open(sys.argv[2], "a").write("\n")
EOF

if (( WITH_ZIPS == 1 )); then
    info "Creando $MODS_ZIP y $OVERRIDES_ZIP para launchers antiguos"
    (cd mods && zip -qX "$WORK/$MODS_ZIP" *.jar)
    (cd overrides && zip -qrX "$WORK/$OVERRIDES_ZIP" .)
fi

if (( DRY_RUN == 1 )); then
    OUT="$REPO/.publicar-dry-run"
    rm -rf "$OUT" && mkdir -p "$OUT"
    cp "$WORK/$MANIFEST" "$WORK/latest.json" "$WORK/upload.tsv" "$OUT/"
    (( WITH_ZIPS == 0 )) || cp "$WORK"/*.zip "$OUT/"
    info "Dry run: nada subido. Archivos en $OUT"
    cat "$OUT/latest.json"
    exit 0
fi

# 6. Subida de objetos nuevos y comprobación de su hash en el servidor
"${SSH[@]}" "mkdir -p '$REMOTE_DIR/objects' '$REMOTE_DIR/.incoming'"
if [[ -s "$WORK/upload.tsv" ]]; then
    info "Subiendo archivos nuevos"
    rsync -rL --partial --info=progress2 -h -e "$RSYNC_SSH" \
        "$WORK/incoming/" "$SSH_USER@$SSH_HOST:$REMOTE_DIR/.incoming/"
    info "Comprobando en el servidor el hash de lo subido"
    "${SSH[@]}" "cd '$REMOTE_DIR/.incoming' && sha256sum -c --quiet SHA256SUMS" \
        || fail "algún archivo no llegó bien (ver arriba). Vuelve a ejecutar el script: rsync corrige solo lo que falle."
    "${SSH[@]}" "cd '$REMOTE_DIR/.incoming' && for f in */*; do
        [ -f \"\$f\" ] || continue
        mkdir -p \"../objects/\${f%/*}\" && mv -f \"\$f\" \"../objects/\$f\"
    done && cd .. && rm -rf .incoming"
fi

info "Comprobando que están todos los archivos del manifiesto"
"${SSH[@]}" "cd '$REMOTE_DIR/objects' && find . -type f -printf '%f\n'" | sort -u > "$WORK/remote-objects.txt"
absent="$(comm -23 "$WORK/needed.txt" "$WORK/remote-objects.txt" | wc -l)"
(( absent == 0 )) || fail "faltan $absent archivos en el servidor; no se publica"

if (( VERIFY_ALL == 1 )); then
    info "Comprobando el hash de todos los archivos en el servidor"
    sed 's/^\(..\)\(.*\)$/\1\2  \1\/\1\2/' "$WORK/needed.txt" \
        | "${SSH[@]}" "cd '$REMOTE_DIR/objects' && sha256sum -c --quiet -" \
        || fail "hay archivos dañados en el servidor (ver arriba); bórralos de objects/ y vuelve a publicar"
fi

# 7. Zips (opcional), manifiesto y, por último, latest.json
info "Publicando el manifiesto y latest.json"
uploads=("$WORK/$MANIFEST")
(( WITH_ZIPS == 0 )) || uploads+=("$WORK/$MODS_ZIP" "$WORK/$OVERRIDES_ZIP")
rsync -h --progress -e "$RSYNC_SSH" "${uploads[@]}" "$SSH_USER@$SSH_HOST:$REMOTE_DIR/"
"${SSH[@]}" "cd '$REMOTE_DIR' && echo '$MANIFEST_SHA  $MANIFEST' | sha256sum -c --quiet -" \
    || fail "el manifiesto no llegó bien; no se publica"
rsync -e "$RSYNC_SSH" "$WORK/latest.json" "$SSH_USER@$SSH_HOST:$REMOTE_DIR/latest.json.new"
"${SSH[@]}" "mv '$REMOTE_DIR/latest.json.new' '$REMOTE_DIR/latest.json'"

# 8. Limpieza: deja lo que usan la versión nueva y la anterior
info "Borrando archivos que ya no usa ninguna de las dos últimas versiones"
KEEP="$VERSION ${CURRENT:-}"
python3 - "$WORK/$MANIFEST" "$WORK/remote-manifest.json" <<'EOF' | sort -u > "$WORK/keep.txt"
import json, sys
for path in sys.argv[1:]:
    try:
        for f in json.load(open(path))["files"]:
            print(f["sha256"])
    except Exception:
        pass
EOF
comm -23 "$WORK/remote-objects.txt" "$WORK/keep.txt" | sed 's/^\(..\)/\1\/\1/' > "$WORK/stale.txt"
if [[ -s "$WORK/stale.txt" ]]; then
    echo "    $(wc -l < "$WORK/stale.txt") archivo(s) sin usar"
    "${SSH[@]}" "cd '$REMOTE_DIR/objects' && xargs -r rm -f && find . -mindepth 1 -type d -empty -delete" < "$WORK/stale.txt"
fi
"${SSH[@]}" "cd '$REMOTE_DIR' && for f in mods-*.zip overrides-*.zip manifest-*.json; do
    [ -e \"\$f\" ] || continue
    v=\${f#*-}; v=\${v%.zip}; v=\${v%.json}
    case ' $KEEP ' in *\" \$v \"*) ;; *) rm -v \"\$f\" ;; esac
done"

# 9. Comprobación desde fuera, como lo verán los jugadores
info "Comprobando $PUBLIC_DIR"
ok=1
public_latest="$(curl -fsS "$PUBLIC_DIR/latest.json?nocache=$RANDOM" || true)"
if ! grep -q "\"version\": \"$VERSION\"" <<< "$public_latest"; then
    warn "la URL pública todavía no devuelve la versión $VERSION (¿caché?)."
    ok=0
fi
if [[ "$(curl -fsS "$PUBLIC_DIR/$MANIFEST" | sha256sum | cut -d' ' -f1)" != "$MANIFEST_SHA" ]]; then
    warn "el manifiesto público no coincide con el subido."
    ok=0
fi
# Algunos de los archivos nuevos más pequeños, descargados de verdad
while IFS=$'\t' read -r sha _ _; do
    if [[ "$(curl -fsS "$PUBLIC_DIR/objects/${sha:0:2}/$sha" | sha256sum | cut -d' ' -f1)" != "$sha" ]]; then
        warn "objects/${sha:0:2}/$sha no se descarga bien."
        ok=0
    fi
done < <(sort -t$'\t' -k2,2n "$WORK/upload.tsv" | head -3)
if (( ok == 1 )); then
    info "Publicada la versión $VERSION"
else
    warn "publicada la versión $VERSION, pero revisa los avisos de arriba."
fi
