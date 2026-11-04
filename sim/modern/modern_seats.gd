extends RefCounted
## A seat in the modern world (MODERN_PLAN 4): one entity's occupant, called at each month end with that entity's observation in its own view,
## answering with actions in the view's terms (entities by the view's tokens). Occupants:
##   scripted: a Callable(observation: Dictionary) -> Array of actions
##   replay: a transcript of earlier answers by day; the observation's md5 is compared with the one recorded (a mismatch is counted)
## No network and no model call is on this path. Every seat keeps its own transcript (its context); nothing passes between seats.
## The answer is mapped back to the world through the view; one unknown token refuses the whole answer, and the world then refuses or applies
## the set as a whole (modern_world.gd check_actions), falling back to the rule actions.
const MV = preload("res://sim/modern/modern_view.gd")

var view: RefCounted
var mode: String = ""
var script_fn: Callable
var transcript: Array = []    # [{"day", "obs_md5", "answer"}], what this seat saw and answered
var replay_from: Array = []
var diverged: int = 0


static func scripted(v: RefCounted, fn: Callable) -> RefCounted:
	var s = load("res://sim/modern/modern_seats.gd").new()
	s.view = v
	s.mode = "scripted"
	s.script_fn = fn
	return s


static func replay(v: RefCounted, earlier: Array) -> RefCounted:
	var s = load("res://sim/modern/modern_seats.gd").new()
	s.view = v
	s.mode = "replay"
	s.replay_from = earlier.duplicate(true)
	return s


func actions(w: RefCounted, e: int) -> Dictionary:
	var obs: Dictionary = view.observe(w, e)
	var md5: String = MV.text_of(obs).md5_text()
	var answer: Variant = []
	if mode == "scripted":
		answer = script_fn.call(obs)
	else:
		var row: Dictionary = {}
		for r: Dictionary in replay_from:
			if int(r["day"]) == w.field.day:
				row = r
				break
		if row.is_empty():
			transcript.append({"day": w.field.day, "obs_md5": md5, "answer": []})
			return {"actions": [], "error": "the transcript has no answer for day %d" % w.field.day}
		diverged += 0 if String(row["obs_md5"]) == md5 else 1
		answer = (row["answer"] as Array).duplicate(true)
	transcript.append({"day": w.field.day, "obs_md5": md5, "answer": answer.duplicate(true) if answer is Array else answer})
	if not (answer is Array):
		return {"actions": [], "error": "the answer is not a list"}
	var out: Array = []
	for a: Variant in answer:
		var m: Dictionary = view.to_world(a)
		if m.has("error"):
			return {"actions": [], "error": String(m["error"])}
		out.append(m)
	return {"actions": out, "error": ""}
