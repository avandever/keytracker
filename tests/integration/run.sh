#!/bin/bash
# Run one integration script, or all of them, inside the app container.
#
#   tests/integration/run.sh test_publish_round.py   # one
#   tests/integration/run.sh                         # all, with a summary
#
# The working copy of the package is dropped in beside the script rather than
# installed, so the running site keeps its own code: /tmp is the script's own
# directory and therefore first on sys.path, and /tmp/keytracker points at it.
# That is what lets this test an uncommitted change against a live container.
#
# Both DATABASE_URL and TEST_DATABASE_URL are set to the scratch database for
# the test process. The scripts read TEST_DATABASE_URL, but a script that
# forgot to would otherwise inherit the container's own DATABASE_URL -- which
# is production, and these scripts call drop_all(). Belt and braces on purpose.
set -e

CONTAINER="${KEYTRACKER_CONTAINER:-keytracker}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "No running container named '$CONTAINER'." >&2
  echo "Start the app (see CLAUDE.md) or set KEYTRACKER_CONTAINER." >&2
  exit 1
fi

# Everything this run uses lives under one directory of its own. Two runs at
# once used to copy over each other's package and then drop each other's
# tables mid-test, which surfaces as "concurrent DDL statement" and missing
# tables rather than as anything that points at the cause.
RUN_DIR="/tmp/kt_run_$$"
cleanup() { docker exec "$CONTAINER" rm -rf "$RUN_DIR" 2>/dev/null || true; }
trap cleanup EXIT

docker exec "$CONTAINER" mkdir -p "$RUN_DIR"
docker cp "$REPO/keytracker" "$CONTAINER":"$RUN_DIR"/keytracker >/dev/null
docker cp "$HERE/scratch_url.py" "$CONTAINER":"$RUN_DIR"/scratch_url.py >/dev/null
url=$(docker exec "$CONTAINER" python3 "$RUN_DIR"/scratch_url.py)

# The scratch database is one database, though, and every script drops every
# table in it. So they take turns: a second run waits rather than pulling the
# first one's tables out from under it. The lock lives in the container, which
# is where both runs meet however they were started.
run_one() {
  local name="$1"
  docker cp "$HERE/$name" "$CONTAINER":"$RUN_DIR"/"$name" >/dev/null
  docker exec \
    -e TEST_DATABASE_URL="$url" \
    -e DATABASE_URL="$url" \
    -e TRACKER_CONFIG_PATH=ENV \
    -e ENABLE_COLLECTOR= \
    -e ENABLE_CARD_REFRESHER= \
    "$CONTAINER" sh -c \
    "flock /tmp/keytracker-integration.lock python3 $RUN_DIR/$name"
}

if [ $# -ge 1 ]; then
  run_one "$(basename "$1")"
  exit $?
fi

# All of them. Background threads in the container print their own noise and
# occasionally a traceback of their own, so a script is judged by its exit
# status, not by what went past on the way.
failed=()
for path in "$HERE"/test_*.py; do
  name=$(basename "$path")
  printf '%-30s ' "$name"
  if out=$(run_one "$name" 2>&1); then
    echo "ok"
  else
    echo "FAILED"
    failed+=("$name")
    echo "$out" | grep -E '^\s*\[FAIL|^FAILED|Error' | sed 's/^/      /' | head -5
  fi
done

echo
if [ ${#failed[@]} -eq 0 ]; then
  echo "all scripts passed"
else
  echo "failed: ${failed[*]}"
  exit 1
fi
