#!/usr/bin/env bash
# Provision a THROWAWAY test MySQL for proving number-computing SQL changes are
# byte-identical before shipping. Synthetic data only — never production.
#
#   bash scripts/setup_test_db.sh                 # create DB + load 20k synthetic rows
#   bash scripts/setup_test_db.sh --rows 100000   # bigger set for perf timing
#
# Requires a reachable MySQL. In a cloud container without one, start it first:
#   (Debian/Ubuntu)  apt-get update && apt-get install -y default-mysql-server \
#                    && service mysql start
#   or docker:       docker run -d --name alt-test-db -e MYSQL_ALLOW_EMPTY_PASSWORD=1 \
#                    -p 3306:3306 mysql:8
#
# Env overrides: DB_HOST (localhost), DB_USER (root), DB_PASS (empty), DB_NAME (alt_test)
set -euo pipefail

ROWS=20000
[ "${1:-}" = "--rows" ] && ROWS="${2:-20000}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_USER="${DB_USER:-root}"
DB_NAME="${DB_NAME:-alt_test}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SQL="$HERE/synthetic_snapshot.sql"

MYSQL=(mysql -h "$DB_HOST" -u "$DB_USER")
[ -n "${DB_PASS:-}" ] && MYSQL+=(-p"$DB_PASS")

echo "1/3  generating $ROWS synthetic rows ..."
python3 "$HERE/railway/gen_synthetic_snapshot.py" --rows "$ROWS" --out "$SQL"

echo "2/3  creating database \`$DB_NAME\` ..."
"${MYSQL[@]}" -e "CREATE DATABASE IF NOT EXISTS \`$DB_NAME\` CHARACTER SET utf8mb4;"

echo "3/3  loading schema + synthetic rows ..."
"${MYSQL[@]}" "$DB_NAME" < "$SQL"
COUNT=$("${MYSQL[@]}" -N -e "SELECT COUNT(*) FROM \`$DB_NAME\`.wp_alt_layoffs;")
echo "done — $DB_NAME.wp_alt_layoffs has $COUNT rows."

cat <<'NOTE'

--- how to prove a query rewrite is safe ---
1. Copy the CURRENT aggregate SQL from includes/db.php into old.sql, the NEW
   (folded/optimized) version into new.sql, both SELECTing the same totals.
2. Run both against alt_test and diff:
     mysql -N alt_test < old.sql > /tmp/old.txt
     mysql -N alt_test < new.sql > /tmp/new.txt
     diff /tmp/old.txt /tmp/new.txt && echo "IDENTICAL — safe to ship"
3. Only ship if the diff is empty. A single differing number = do not ship.
This DB is disposable: DROP DATABASE alt_test; when done. Synthetic data only.
NOTE
