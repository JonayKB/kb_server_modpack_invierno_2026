#!/usr/bin/env bash
# Publica el modpack para KB MC Launcher en me.jonaykb.com/modpacks/<id>/
#
#   ./publicar.sh                 sube la versión de parche (1.0.3 -> 1.0.4)
#   ./publicar.sh 1.1.0           publica con esa versión
#   ./publicar.sh --dry-run       genera los zips y el latest.json sin subir nada
#   ./publicar.sh --force         publica aunque haya cambios sin commit
#
# Los zips llevan la versión en el nombre (mods-1.0.4.zip) para que ninguna
# caché sirva uno viejo. latest.json se sube el último: hasta ese momento los
# jugadores siguen viendo la versión anterior. Se guarda la versión anterior por
# si alguien la estaba descargando y se borran las más viejas.
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
SSH=(ssh -p "$SSH_PORT" "$SSH_USER@$SSH_HOST")

DRY_RUN=0 FORCE=0 VERSION=""
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --force) FORCE=1 ;;
        -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        [0-9]*.[0-9]*.[0-9]*) VERSION="$arg" ;;
        *) echo "Argumento desconocido: $arg" >&2; exit 1 ;;
    esac
done

info() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

for cmd in git git-lfs zip unzip rsync ssh python3; do
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

# 2. Versión
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if (( DRY_RUN == 0 )); then
    info "Leyendo la versión publicada"
    "${SSH[@]}" "cat '$REMOTE_DIR/latest.json' 2>/dev/null || true" > "$WORK/remote.json"
else
    : > "$WORK/remote.json"
fi

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

# 3. Zips
MODS_ZIP="mods-$VERSION.zip"
OVERRIDES_ZIP="overrides-$VERSION.zip"

info "Creando $MODS_ZIP ($(ls mods/*.jar | wc -l) mods)"
(cd mods && zip -qX "$WORK/$MODS_ZIP" *.jar)

info "Creando $OVERRIDES_ZIP"
(cd overrides && zip -qrX "$WORK/$OVERRIDES_ZIP" .)

# 4. latest.json (conserva images y changelog de la versión publicada)
python3 - "$WORK/remote.json" "$WORK/latest.json" <<EOF
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
    "modsUrl": "$PUBLIC_BASE/$MODPACK_ID/$MODS_ZIP",
    "overridesUrl": "$PUBLIC_BASE/$MODPACK_ID/$OVERRIDES_ZIP",
    "images": old.get("images", []),
}
if "changelog" in old:
    new["changelog"] = old["changelog"]
json.dump(new, open(sys.argv[2], "w"), ensure_ascii=False, indent=2)
open(sys.argv[2], "a").write("\n")
EOF

ls -lh "$WORK"/*.zip | awk '{print "    " $5 "  " $NF}'

if (( DRY_RUN == 1 )); then
    OUT="$REPO/.publicar-dry-run"
    rm -rf "$OUT" && mkdir -p "$OUT"
    cp "$WORK"/*.zip "$WORK/latest.json" "$OUT/"
    info "Dry run: nada subido. Archivos en $OUT"
    cat "$OUT/latest.json"
    exit 0
fi

# 5. Subida: zips primero y latest.json al final
info "Subiendo a $SSH_USER@$SSH_HOST:$REMOTE_DIR"
"${SSH[@]}" "mkdir -p '$REMOTE_DIR'"
rsync -h --progress -e "ssh -p $SSH_PORT" \
    "$WORK/$MODS_ZIP" "$WORK/$OVERRIDES_ZIP" "$SSH_USER@$SSH_HOST:$REMOTE_DIR/"
rsync -e "ssh -p $SSH_PORT" "$WORK/latest.json" "$SSH_USER@$SSH_HOST:$REMOTE_DIR/latest.json.new"
"${SSH[@]}" "mv '$REMOTE_DIR/latest.json.new' '$REMOTE_DIR/latest.json'"

# 6. Limpieza: deja la versión nueva y la anterior
info "Borrando zips de versiones antiguas"
KEEP="$VERSION ${CURRENT:-}"
"${SSH[@]}" "cd '$REMOTE_DIR' && for f in mods-*.zip overrides-*.zip; do
    [ -e \"\$f\" ] || continue
    v=\${f#*-}; v=\${v%.zip}
    case ' $KEEP ' in *\" \$v \"*) ;; *) rm -v \"\$f\" ;; esac
done"

info "Comprobando $PUBLIC_BASE/$MODPACK_ID/latest.json"
if curl -fsS "$PUBLIC_BASE/$MODPACK_ID/latest.json?nocache=$RANDOM" | grep -q "\"version\": \"$VERSION\""; then
    info "Publicada la versión $VERSION"
else
    echo "Aviso: la URL pública todavía no devuelve la versión $VERSION (¿caché?)." >&2
fi
