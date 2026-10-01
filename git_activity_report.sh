#!/usr/bin/env bash

set -uo pipefail

# ============================================================
# Git Activity Report
# Genera un reporte de actividad de desarrollo desde Git
#
# Uso:
#   ./git_activity_report.sh
#   ./git_activity_report.sh 2026-07-01 2026-09-14
#   ./git_activity_report.sh 2026-07-01 2026-09-14 "German Ponce"
#
# Ejecutar desde la raíz de un repositorio Git.
# ============================================================

START_DATE="${1:-2026-07-01}"
END_DATE="${2:-$(date +%Y-%m-%d)}"
AUTHOR="${3:-}"

# ------------------------------------------------------------
# Validaciones
# ------------------------------------------------------------

if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: git no está instalado."
    exit 1
fi

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
    echo "ERROR: este directorio no pertenece a un repositorio Git."
    echo
    echo "Ejecuta el script desde la raíz de tu repositorio."
    exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
REPO_NAME="$(basename "$REPO_ROOT")"

cd "$REPO_ROOT"

# ------------------------------------------------------------
# Directorio de salida
# ------------------------------------------------------------

SAFE_START="${START_DATE//[^0-9]/}"
SAFE_END="${END_DATE//[^0-9]/}"

OUTPUT_DIR="git_activity_report_${SAFE_START}_${SAFE_END}"

mkdir -p "$OUTPUT_DIR"

HTML="$OUTPUT_DIR/reporte.html"
TXT="$OUTPUT_DIR/reporte.txt"
COMMITS_CSV="$OUTPUT_DIR/commits.csv"
FILES_CSV="$OUTPUT_DIR/archivos.csv"
STATS="$OUTPUT_DIR/estadisticas.txt"

# ------------------------------------------------------------
# Información del repositorio
# ------------------------------------------------------------

REMOTE="$(git remote get-url origin 2>/dev/null || echo "Sin remote origin")"
CURRENT_BRANCH="$(git branch --show-current 2>/dev/null || echo "N/A")"

GIT_USER="$(git config user.name 2>/dev/null || echo "No configurado")"
GIT_EMAIL="$(git config user.email 2>/dev/null || echo "No configurado")"

#if [[ -z "$AUTHOR" ]]; then
#    AUTHOR="$GIT_USER"
#fi

# ------------------------------------------------------------
# Rango Git
#
# Usamos:
#
#   --since="2026-07-01 00:00:00"
#   --until="2026-09-14 23:59:59"
#
# para incluir todo el día final.
# ------------------------------------------------------------

SINCE="${START_DATE} 00:00:00"
UNTIL="${END_DATE} 23:59:59"

# ------------------------------------------------------------
# Argumentos base
# ------------------------------------------------------------

LOG_ARGS=(
    log
    --all
    --date=iso
    --since="$SINCE"
    --until="$UNTIL"
)

if [[ -n "$AUTHOR" ]]; then
    LOG_ARGS+=("--author=$AUTHOR")
fi

# ------------------------------------------------------------
# Conteos
# ------------------------------------------------------------

TOTAL_COMMITS=$(git "${LOG_ARGS[@]}" --no-merges --format='%H' | wc -l)

TOTAL_MERGES=$(git "${LOG_ARGS[@]}" --merges --format='%H' | wc -l)

# Estadísticas globales
NUMSTAT="$(mktemp)"

git "${LOG_ARGS[@]}" \
    --no-merges \
    --numstat \
    --format='' 2>/dev/null |
awk '
    NF == 3 && $1 ~ /^[0-9]+$/ && $2 ~ /^[0-9]+$/ {
        add += $1
        del += $2
        files++
    }
    END {
        print add+0, del+0, files+0
    }
' > "$NUMSTAT"

read -r TOTAL_ADDED TOTAL_DELETED NUMSTAT_FILES < "$NUMSTAT"

rm -f "$NUMSTAT"

# ------------------------------------------------------------
# CSV COMMITS
# ------------------------------------------------------------

echo '"hash","short_hash","date","author","email","subject"' > "$COMMITS_CSV"

git "${LOG_ARGS[@]}" \
    --no-merges \
    --format='%H%x09%h%x09%ad%x09%an%x09%ae%x09%s' |
while IFS=$'\t' read -r HASH SHORT DATE AUTHOR_NAME EMAIL SUBJECT; do

    # Escapar comillas dobles para CSV
    AUTHOR_NAME="${AUTHOR_NAME//\"/\"\"}"
    EMAIL="${EMAIL//\"/\"\"}"
    SUBJECT="${SUBJECT//\"/\"\"}"

    echo "\"$HASH\",\"$SHORT\",\"$DATE\",\"$AUTHOR_NAME\",\"$EMAIL\",\"$SUBJECT\""

done >> "$COMMITS_CSV"

# ------------------------------------------------------------
# CSV ARCHIVOS
# ------------------------------------------------------------

echo '"commit","date","author","status","insertions","deletions","file"' > "$FILES_CSV"

git "${LOG_ARGS[@]}" \
    --no-merges \
    --format='COMMIT%x09%H%x09%ad%x09%an' \
    --date=iso \
    --name-status |
while IFS=$'\t' read -r A B C D E; do

    if [[ "$A" == "COMMIT" ]]; then
        COMMIT_HASH="$B"
        COMMIT_DATE="$C"
        COMMIT_AUTHOR="$D"
        continue
    fi

    # Saltar líneas vacías
    [[ -z "${A:-}" ]] && continue

    STATUS="$A"

    # Para rename/copy puede haber dos rutas.
    FILE="$B"

    echo "\"$COMMIT_HASH\",\"$COMMIT_DATE\",\"$COMMIT_AUTHOR\",\"$STATUS\",\"\",\"\",\"$FILE\""

done >> "$FILES_CSV"

# ------------------------------------------------------------
# Función: estadísticas por mes
# ------------------------------------------------------------

MONTH_STATS=""
MONTH_ROWS=""

for MONTH in 07 08 09; do

    YEAR=2026

    case "$MONTH" in
        07) MONTH_NAME="Julio" ;;
        08) MONTH_NAME="Agosto" ;;
        09) MONTH_NAME="Septiembre" ;;
    esac

    MONTH_START="${YEAR}-${MONTH}-01"

    if [[ "$MONTH" == "07" ]]; then
        MONTH_END="${YEAR}-07-31"
    elif [[ "$MONTH" == "08" ]]; then
        MONTH_END="${YEAR}-08-31"
    else
        MONTH_END="$END_DATE"
    fi

    # Evitar meses fuera del rango solicitado
    if [[ "$MONTH_END" < "$START_DATE" || "$MONTH_START" > "$END_DATE" ]]; then
        continue
    fi

    [[ "$MONTH_START" < "$START_DATE" ]] && MONTH_START="$START_DATE"
    [[ "$MONTH_END" > "$END_DATE" ]] && MONTH_END="$END_DATE"

    MCOMMITS=$(git log \
        --all \
        --no-merges \
        --since="${MONTH_START} 00:00:00" \
        --until="${MONTH_END} 23:59:59" \
        ${AUTHOR:+--author="$AUTHOR"} \
        --format='%H' |
        wc -l)

    MSTATS=$(git log \
        --all \
        --no-merges \
        --since="${MONTH_START} 00:00:00" \
        --until="${MONTH_END} 23:59:59" \
        ${AUTHOR:+--author="$AUTHOR"} \
        --numstat \
        --format='' 2>/dev/null |
        awk '
            NF == 3 && $1 ~ /^[0-9]+$/ && $2 ~ /^[0-9]+$/ {
                add += $1
                del += $2
                files++
            }
            END {
                print add+0, del+0, files+0
            }')

    read -r MADD MDEL MFILES <<< "$MSTATS"

    MONTH_STATS+="
$MONTH_NAME:
  Commits:       $MCOMMITS
  Inserciones:   $MADD
  Eliminaciones: $MDEL
  Archivos:      $MFILES
"

    MONTH_ROWS+="
<tr>
<td>$MONTH_NAME</td>
<td>$MCOMMITS</td>
<td>$MADD</td>
<td>$MDEL</td>
<td>$MFILES</td>
</tr>
"
done

# ------------------------------------------------------------
# Módulos / carpetas con mayor actividad
# ------------------------------------------------------------

MODULE_TMP="$(mktemp)"

git "${LOG_ARGS[@]}" \
    --no-merges \
    --name-only \
    --format='' 2>/dev/null |
grep -v '^$' |
awk '
{
    split($0, p, "/")
    if (length(p[1]) > 0)
        print p[1]
}' |
sort |
uniq -c |
sort -nr |
head -20 > "$MODULE_TMP"

MODULE_ROWS=""

while read -r COUNT MODULE; do
    [[ -z "$MODULE" ]] && continue

    MODULE_ROWS+="
<tr>
<td>$MODULE</td>
<td>$COUNT</td>
</tr>
"
done < "$MODULE_TMP"

rm -f "$MODULE_TMP"

# ------------------------------------------------------------
# Commits recientes
# ------------------------------------------------------------

RECENT_ROWS=""

git "${LOG_ARGS[@]}" \
    --no-merges \
    --format='%h%x09%ad%x09%an%x09%s' |
head -30 |
while IFS=$'\t' read -r HASH DATE COMMIT_AUTHOR SUBJECT; do

    RECENT_ROWS+="
<tr>
<td><code>$HASH</code></td>
<td>$DATE</td>
<td>$COMMIT_AUTHOR</td>
<td>$SUBJECT</td>
</tr>
"

done

# ------------------------------------------------------------
# TXT
# ------------------------------------------------------------

cat > "$TXT" <<EOF
============================================================
REPORTE DE ACTIVIDAD GIT
============================================================

Repositorio:
$REPO_NAME

Ruta:
$REPO_ROOT

Remote:
$REMOTE

Rama actual:
$CURRENT_BRANCH

Autor:
$AUTHOR

Usuario Git configurado:
$GIT_USER <$GIT_EMAIL>

Periodo:
$START_DATE hasta $END_DATE


============================================================
RESUMEN GENERAL
============================================================

Commits realizados:        $TOTAL_COMMITS
Commits de merge:          $TOTAL_MERGES
Archivos modificados:      $NUMSTAT_FILES
Líneas agregadas:          $TOTAL_ADDED
Líneas eliminadas:         $TOTAL_DELETED


============================================================
ACTIVIDAD POR MES
============================================================
$MONTH_STATS


============================================================
MÓDULOS / CARPETAS CON MAYOR ACTIVIDAD
============================================================

EOF

while read -r COUNT MODULE; do
    [[ -z "$MODULE" ]] && continue
    printf "%-50s %s archivos\n" "$MODULE" "$COUNT" >> "$TXT"
done < <(
    git "${LOG_ARGS[@]}" \
        --no-merges \
        --name-only \
        --format='' 2>/dev/null |
    grep -v '^$' |
    awk '
    {
        split($0, p, "/")
        if (length(p[1]) > 0)
            print p[1]
    }' |
    sort |
    uniq -c |
    sort -nr |
    head -20
)

cat >> "$TXT" <<EOF


============================================================
ÚLTIMOS COMMITS
============================================================

EOF

git "${LOG_ARGS[@]}" \
    --no-merges \
    --format='%ad | %h | %an | %s' |
head -30 >> "$TXT"

# ------------------------------------------------------------
# Estadísticas
# ------------------------------------------------------------

cat > "$STATS" <<EOF
Repositorio: $REPO_NAME
Periodo: $START_DATE -> $END_DATE
Autor: $AUTHOR

Commits: $TOTAL_COMMITS
Merges: $TOTAL_MERGES
Archivos: $NUMSTAT_FILES
Inserciones: $TOTAL_ADDED
Eliminaciones: $TOTAL_DELETED

Remote:
$REMOTE

Rama actual:
$CURRENT_BRANCH

Fecha de generación:
$(date '+%Y-%m-%d %H:%M:%S')
EOF

# ------------------------------------------------------------
# HTML
# ------------------------------------------------------------

cat > "$HTML" <<EOF
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">

<title>Reporte Git - $REPO_NAME</title>

<style>
body {
    font-family: Arial, Helvetica, sans-serif;
    margin: 40px;
    background: #f5f5f5;
    color: #222;
}

.container {
    max-width: 1400px;
    margin: auto;
    background: white;
    padding: 35px;
    box-shadow: 0 2px 10px rgba(0,0,0,.08);
}

h1 {
    margin-bottom: 5px;
}

h2 {
    margin-top: 35px;
    border-bottom: 2px solid #ddd;
    padding-bottom: 8px;
}

.info {
    color: #666;
    margin-bottom: 25px;
}

.cards {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 15px;
}

.card {
    background: #fafafa;
    border: 1px solid #ddd;
    padding: 20px;
    text-align: center;
}

.card .number {
    font-size: 28px;
    font-weight: bold;
}

.card .label {
    color: #666;
    margin-top: 5px;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 15px;
}

th {
    background: #eee;
    text-align: left;
}

th, td {
    padding: 9px;
    border-bottom: 1px solid #ddd;
}

tr:hover {
    background: #fafafa;
}

code {
    font-family: monospace;
}

.footer {
    margin-top: 40px;
    color: #777;
    font-size: 12px;
}
</style>

</head>

<body>

<div class="container">

<h1>Reporte de Actividad Git</h1>

<div class="info">

<strong>Repositorio:</strong> $REPO_NAME<br>
<strong>Periodo:</strong> $START_DATE → $END_DATE<br>
<strong>Autor:</strong> $AUTHOR<br>
<strong>Rama actual:</strong> $CURRENT_BRANCH<br>
<strong>Remote:</strong> $REMOTE

</div>


<h2>Resumen general</h2>

<div class="cards">

<div class="card">
<div class="number">$TOTAL_COMMITS</div>
<div class="label">Commits</div>
</div>

<div class="card">
<div class="number">$NUMSTAT_FILES</div>
<div class="label">Archivos</div>
</div>

<div class="card">
<div class="number">$TOTAL_ADDED</div>
<div class="label">Líneas agregadas</div>
</div>

<div class="card">
<div class="number">$TOTAL_DELETED</div>
<div class="label">Líneas eliminadas</div>
</div>

<div class="card">
<div class="number">$TOTAL_MERGES</div>
<div class="label">Merges</div>
</div>

</div>


<h2>Actividad mensual</h2>

<table>

<thead>
<tr>
<th>Mes</th>
<th>Commits</th>
<th>Inserciones</th>
<th>Eliminaciones</th>
<th>Archivos</th>
</tr>
</thead>

<tbody>

$MONTH_ROWS

</tbody>

</table>


<h2>Carpetas / módulos con mayor actividad</h2>

<table>

<thead>
<tr>
<th>Carpeta / módulo</th>
<th>Archivos modificados</th>
</tr>
</thead>

<tbody>

$MODULE_ROWS

</tbody>

</table>


<h2>Últimos commits</h2>

<table>

<thead>
<tr>
<th>Hash</th>
<th>Fecha</th>
<th>Autor</th>
<th>Commit</th>
</tr>
</thead>

<tbody>

$RECENT_ROWS

</tbody>

</table>


<div class="footer">
Reporte generado el $(date '+%Y-%m-%d %H:%M:%S')
</div>

</div>

</body>
</html>
EOF

# ------------------------------------------------------------
# Resultado
# ------------------------------------------------------------

echo
echo "============================================================"
echo " REPORTE GENERADO"
echo "============================================================"
echo
echo "Repositorio : $REPO_NAME"
echo "Periodo     : $START_DATE -> $END_DATE"
echo "Autor       : $AUTHOR"
echo
echo "Commits     : $TOTAL_COMMITS"
echo "Archivos    : $NUMSTAT_FILES"
echo "Agregadas   : $TOTAL_ADDED"
echo "Eliminadas  : $TOTAL_DELETED"
echo
echo "Archivos generados:"
echo
echo "  $HTML"
echo "  $TXT"
echo "  $COMMITS_CSV"
echo "  $FILES_CSV"
echo "  $STATS"
echo
echo "============================================================"
