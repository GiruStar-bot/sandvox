extends "res://tools/test/test_kit.gd"
## The runner's known failures by row (V114, TO_E 14:11): tools/test/known_rows.py's cases, from tools/test/test_known_rows.py, each a
## check; the first is V114's mutation (a second row broken in a listed file must FAIL, not show as KNOWN)
##   godot --headless --path . --script res://tools/test/test_known_rows.gd


func _init() -> void:
	var out: Array = []
	var rc: int = OS.execute("python3", [ProjectSettings.globalize_path("res://tools/test/test_known_rows.py")], out, true)
	check(rc == 0, "test_known_rows.py ran (exit %d)" % rc)
	var n: int = 0
	for line: String in String(out[0] if out.size() > 0 else "").split("\n"):
		if line.begins_with("ok   ") or line.begins_with("FAIL "):
			n += 1
			check(line.begins_with("ok   "), line.substr(5))
	check(n == 16, "the 16 cases reported (%d)" % n)
	finish()
