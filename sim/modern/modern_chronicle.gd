extends RefCounted
## The chronicle (BLUEPRINT 2, L4): the record the owner reads. Rows {day, date, kind, place, who, facts, why}, appended by the world
## from field thresholds (a shortage, a project finished, a licence changed, a status line crossed, a year closed) and from every actor
## decision with its reason codes. Exact JSONL; tools/modern/chronicle.py renders it in time order. The chronicle is output only: nothing
## reads it back into the field.
const KINDS: Array[String] = ["shortage", "project_done", "licence", "lever_set", "lever_applied", "lever_refused", "decision", "status_line", "year_close", "seat_refused", "election"]

var rows: Array = []
var base_year: int = 0
var _last_shortage: Dictionary = {}   # entity -> day of the last shortage row (one row per run of short days)


func create(year: int) -> void:
	base_year = year
	rows = []


static func date_of(base_year: int, day: int) -> String:
	var y: int = base_year + day / 365
	var doy: int = day % 365
	var md: Array = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
	var m: int = 0
	while m < 11 and doy >= int(md[m]):
		doy -= int(md[m])
		m += 1
	return "%04d-%02d-%02d" % [y, m + 1, doy + 1]


func add(day: int, kind: String, place: String, who: String, facts: Dictionary, why: String = "") -> void:
	rows.append({"day": day, "date": date_of(base_year, day), "kind": kind, "place": place, "who": who, "facts": facts, "why": why})


## Field thresholds for one day: a shortage row opens when an entity first goes short and closes when it is served again
func observe_field(f: RefCounted, keys: PackedStringArray) -> void:
	for e: int in f.E:
		var short: bool = f.unserved[e] > 1e-6 * maxf(1.0, f.demand[e]) or f.dc_served[e] < 1.0 - 1e-9
		var k: String = keys[e]
		if short and not _last_shortage.has(k):
			_last_shortage[k] = f.day
			add(f.day, "shortage", k, "field", {"unserved_mw": f.unserved[e], "dc_served": f.dc_served[e], "fab_served": f.fab_served[e]},
				"demand above supply, links and storage; DC cut first" if f.fab_first[e] == 0 else "demand above supply; fab cut first")
		elif not short and _last_shortage.has(k):
			add(f.day, "shortage", k, "field", {"ended_after_days": f.day - int(_last_shortage[k])}, "supply met demand again")
			_last_shortage.erase(k)


func to_jsonl() -> String:
	var out: PackedStringArray = PackedStringArray()
	for r: Dictionary in rows:
		out.append(JSON.stringify(r))
	return "\n".join(out) + ("\n" if rows.size() > 0 else "")


func to_dict() -> Dictionary:
	return {"rows": rows.duplicate(true), "last_shortage": _last_shortage.duplicate()}


func from_dict(d: Dictionary) -> void:
	rows = (d.get("rows", []) as Array).duplicate(true)
	_last_shortage = (d.get("last_shortage", {}) as Dictionary).duplicate()
