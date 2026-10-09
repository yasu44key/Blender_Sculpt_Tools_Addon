#!/usr/bin/env bash
# GUI tests (event simulation). Opens a Blender 5.2 window briefly per test.
# Isolated user folder, like run_tests.sh.   bash tests/run_gui_tests.sh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
W="$(cygpath -u "${TEMP:-/tmp}")/sts_gui_$$"; mkdir -p "$W"
export BLENDER_USER_RESOURCES="$(cygpath -w "$W")"
"$B" --factory-startup --command extension build --source-dir "$(cygpath -w "$ROOT")" --output-dir "$(cygpath -w "$W")" >/dev/null || exit 1
"$B" --command extension install-file -r user_default -e "$(cygpath -w "$(ls "$W"/*.zip)")" >/dev/null || exit 1
"$B" -b --factory-startup --python-expr "import bpy;bpy.ops.wm.save_as_mainfile(filepath=r'$(cygpath -w "$W/empty.blend")')" >/dev/null 2>&1
status=0
for t in "$ROOT"/tests/gui/gui_*.py; do
  echo "=== $(basename "$t")"
  export STS_GUI_OUT="$(cygpath -w "$W/result.txt")"; rm -f "$W/result.txt"
  timeout 120 "$B" --enable-event-simulate --window-geometry 0 0 1400 1000 \
    "$(cygpath -w "$W/empty.blend")" --python "$(cygpath -w "$t")" > "$W/log.txt" 2>&1
  cat "$W/result.txt" 2>/dev/null || { echo "NO RESULT"; status=1; }
  grep -q "^FAIL\|EXCEPTION" "$W/result.txt" 2>/dev/null && status=1
done
rm -rf "$W"
exit $status
