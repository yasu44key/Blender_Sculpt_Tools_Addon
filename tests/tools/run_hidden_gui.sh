#!/usr/bin/env bash
# usage: run_gui_edge.sh <repo dir>   (hidden GUI test, isolated user folder)
SRC="$1"; GUI_TEST="$2"; B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
W="$(cygpath -u "$TEMP")/sts_guiedge"; rm -rf "$W"; mkdir -p "$W"
export BLENDER_USER_RESOURCES="$(cygpath -w "$W")"
"$B" --factory-startup --command extension build --source-dir "$(cygpath -w "$SRC")" --output-dir "$(cygpath -w "$W")" >/dev/null
"$B" --command extension install-file -r user_default -e "$(cygpath -w "$(ls $W/*.zip)")" >/dev/null
"$B" -b --factory-startup --python-expr "import bpy;bpy.ops.wm.save_as_mainfile(filepath=r'$(cygpath -w "$W/empty.blend")')" >/dev/null 2>&1
export STS_GUI_OUT="$(cygpath -w "$W/result.txt")"
timeout 120 "$B" --enable-event-simulate --window-geometry 0 0 1400 1000 "$(cygpath -w "$W/empty.blend")" --python "$GUI_TEST" > "$W/log.txt" 2>&1
cat "$W/result.txt" 2>/dev/null || { echo "NO RESULT"; grep -E "Error|Traceback" "$W/log.txt" | head; }
