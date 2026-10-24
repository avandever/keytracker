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

# The package under test, copied in once however many scripts follow.
docker exec "$CONTAINER" rm -rf /tmp/kt_under_test /tmp/keytracker
docker cp "$REPO/keytracker" "$CONTAINER":/tmp/kt_under_test >/dev/null
docker exec "$CONTAINER" ln -sfn /tmp/kt_under_test /tmp/keytracker
docker cp "$HERE/scratch_url.py" "$CONTAINER":/tmp/scratch_url.py >/dev/null
url=$(docker exec "$CONTAINER" python3 /tmp/scratch_url.py)

run_one() {
  local name="$1"
  docker cp "$HERE/$name" "$CONTAINER":/tmp/"$name" >/dev/null
  docker exec \
    -e TEST_DATABASE_URL="$url" \
    -e DATABASE_URL="$url" \
    -e TRACKER_CONFIG_PATH=ENV \
    -e ENABLE_COLLECTOR= \
    -e ENABLE_CARD_REFRESHER= \
    "$CONTAINER" python3 /tmp/"$name"
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
