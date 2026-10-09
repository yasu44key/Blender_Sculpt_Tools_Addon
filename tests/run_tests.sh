#!/usr/bin/env bash
# Build the extension, install it into an isolated Blender user folder and run
# every tests/test_*.py inside Blender (background).
#
#   tests/run_tests.sh              # Blender 5.1 and 5.2, all tests
#   tests/run_tests.sh 5.2          # one version
#   TESTS=test_bezier_draw.py tests/run_tests.sh 5.2
#
# Your normal Blender preferences are never touched (BLENDER_USER_RESOURCES).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSIONS="${*:-5.1 5.2}"
BF="/c/Program Files/Blender Foundation"
WORK="$(cygpath -u "${TEMP:-/tmp}")/sts_test_$$"
mkdir -p "$WORK/user_build"

# Every Blender call below runs with an isolated user folder.
BLENDER_USER_RESOURCES="$(cygpath -w "$WORK/user_build")" \
"$BF/Blender 5.2/blender.exe" --factory-startup --command extension build \
  --source-dir "$(cygpath -w "$ROOT")" --output-dir "$(cygpath -w "$WORK")" | grep -iE "error|warn" ; ls "$WORK"/*.zip >/dev/null 2>&1 || exit 1
ZIP="$(ls "$WORK"/*.zip | head -1)"

status=0
for v in $VERSIONS; do
  BL="$BF/Blender $v/blender.exe"
  RES="$WORK/user_$v"
  mkdir -p "$RES"
  export BLENDER_USER_RESOURCES="$(cygpath -w "$RES")"
  "$BL" --command extension install-file -r user_default -e "$(cygpath -w "$ZIP")" || { echo "install failed ($v)"; status=1; continue; }
  for t in "$ROOT"/tests/${TESTS:-test_*.py}; do
    echo "=== Blender $v : $(basename "$t")"
    "$BL" -b --python-exit-code 1 --python "$(cygpath -w "$t")" 2>&1 \
      | grep -E "^(PASS|FAIL|RESULT|Traceback|  File|[A-Za-z]*Error)" || true
    [ "${PIPESTATUS[0]}" -eq 0 ] || status=1
  done
done
rm -rf "$WORK"
exit $status
