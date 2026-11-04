class_name TestKit
extends SceneTree
## 試験の共通部品（R4 T1）。headless の試験は SceneTree の代わりにこれを継ぐ:
##   extends "res://tools/test/test_kit.gd"
## （class_name の表が古くても読めるように、継ぐときは道のりで書く）
##   check(ok, label)           … 合否を1つ数える（ok / FAIL の行を出す）
##   metric(name, value, max)   … 数を1つ残す。上限は tools/test/budgets.json（無ければ引数の max。-1 なら上限なし）
##   skip(label)                … 飛ばした項目（SKIP の行を出す。数には入れない）
##   check_visual(fn, label)    … 絵や写真の項目。headless なら SKIP、窓があれば fn.call() の答えで check
##   await quiet_audio()        … 音を止めて待つ（村の場面を開く試験は finish の前に。鳴ったままだと終わりの漏れになる）
##   finish()                   … 終わり。1行の `RESULT {json}` を出して quit する（落ちた項目か上限超えがあれば 1）
## RESULT の json: file・passed・failed・checks・skipped・failures[]（落ちた label）・metrics{}・over_budget[]・elapsed_ms。
## finish まで来ないまま見張りの上限（elapsed_ms の上限の2倍、無ければ120秒）を過ぎたら、落ちた項目を1つ足して終わる。
## 上限には機械ごとの倍率を1つ掛ける（budgets.json の machine_multiplier。環境変数 TEST_BUDGET_SCALE が優先）。
## 回し方は tools/run_tests.sh の頭を見る。

const BUDGETS_PATH := "res://tools/test/budgets.json"
const MAX_LISTED_FAILURES := 50     # RESULT に載せる落ちた label の上限（数は failed に全部入る）
const WATCHDOG_DEFAULT_S := 120.0   # budgets.json に elapsed_ms が無い試験の見張りの上限（秒）

var checks: int = 0
var failures: int = 0
var skipped: int = 0
var failure_labels: Array[String] = []
var metrics: Dictionary = {}          # 名前 -> 数
var inline_budgets: Dictionary = {}   # 名前 -> 試験の中で書いた上限（budgets.json が優先）
var _started_usec: int = Time.get_ticks_usec()
var _finished := false
var _watchdog_limit_usec: int = -1
var _seeded: int = _fix_seed()        # 決まった種で始める（同じ未来になる）。TEST_SEED で変えられる

static func _fix_seed() -> int:
	var sd: int = int(OS.get_environment("TEST_SEED")) if OS.get_environment("TEST_SEED") != "" else 42
	seed(sd)
	return sd

func check(ok: bool, label: String) -> void:
	checks += 1
	print(("ok   " if ok else "FAIL ") + label)
	if not ok:
		failures += 1
		if failure_labels.size() < MAX_LISTED_FAILURES: failure_labels.append(label)

func metric(name: String, value: float, max_value: float = -1.0) -> void:
	metrics[name] = value
	if max_value >= 0.0: inline_budgets[name] = max_value
	print("metric %s = %s" % [name, str(value)])

func skip(label: String) -> void:
	skipped += 1
	print("SKIP " + label)

func is_headless() -> bool:
	return DisplayServer.get_name() == "headless"

## 絵が要る項目。headless では答えを作らずに飛ばす（fn も呼ばない）
func check_visual(fn: Callable, label: String) -> void:
	if is_headless():
		skip(label + " (headless)")
		return
	check(bool(fn.call()), label)

## この試験の名前（budgets.json の鍵。ファイル名から .gd を除いたもの）
func test_name() -> String:
	var s: Script = get_script()
	return s.resource_path.get_file().get_basename() if s != null else "unknown"

## 機械ごとの倍率（環境変数 > budgets.json > 1）
static func machine_multiplier(budgets: Dictionary) -> float:
	var env := OS.get_environment("TEST_BUDGET_SCALE")
	if env.is_valid_float() and env.to_float() > 0.0: return env.to_float()
	return float(budgets.get("machine_multiplier", 1.0))

static func load_budgets() -> Dictionary:
	if not FileAccess.file_exists(BUDGETS_PATH): return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(BUDGETS_PATH))
	return parsed if parsed is Dictionary else {}

## 上限を超えた数（[{name, value, max}]）。budgets.json の tests[試験の名前][数の名前] が優先、無ければ試験の中の上限
func over_budget() -> Array[Dictionary]:
	var budgets := load_budgets()
	var scale := machine_multiplier(budgets)
	var tests: Dictionary = budgets.get("tests", {})
	var mine: Dictionary = tests.get(test_name(), {})
	var out: Array[Dictionary] = []
	for name: String in metrics:
		var limit := -1.0
		if mine.has(name): limit = float(mine[name])
		elif inline_budgets.has(name): limit = float(inline_budgets[name])
		if limit < 0.0: continue
		var scaled := limit * scale
		if float(metrics[name]) > scaled:
			out.append({"name": name, "value": metrics[name], "max": scaled})
	return out

## 時間の数か（elapsed_ms・*_ms・ms_per_day）。混み合いで揺れるので、GODOT_EXCLUSIVE=1 のときだけ上限を判定する（R4 A5）
static func is_time_metric(name: String) -> bool:
	return name == "elapsed_ms" or name.ends_with("_ms") or name.contains("_ms_") or name.contains("ms_per_day")

static func time_budgets_enforced() -> bool:
	return OS.get_environment("GODOT_EXCLUSIVE") == "1"

## 見張りの上限（µs）。budgets.json の elapsed_ms の2倍、無ければ WATCHDOG_DEFAULT_S。どちらも倍率を掛ける
func _watchdog_usec() -> int:
	if _watchdog_limit_usec < 0:
		var budgets := load_budgets()
		var mine: Dictionary = (budgets.get("tests", {}) as Dictionary).get(test_name(), {})
		var ms: float = float(mine.get("elapsed_ms", WATCHDOG_DEFAULT_S * 500.0)) * 2.0
		_watchdog_limit_usec = int(ms * machine_multiplier(budgets) * 1000.0)
	return _watchdog_limit_usec

## 見張り: 台本の誤りで止まったり、待ちが終わらなかったりして finish まで来ないとき、落ちたとして終わる
## （誤りで止まった台本は quit を呼ばないので、そのままだと run_tests.sh の時間切れまで待つことになる）
func _process(_delta: float) -> bool:
	if _finished: return false
	if Time.get_ticks_usec() - _started_usec > _watchdog_usec():
		check(false, "finish() was not reached within %.0f s (script error or endless wait)" % (_watchdog_usec() / 1e6))
		finish()
	return false

## 鳴っている音を全部止めて、音の側が手放すまで待つ（await quiet_audio()）。村の場面を開く試験は finish の前に呼ぶ。
## 鳴ったまま quit すると、再生中の流れ（AudioStreamPlayback）が終わりの漏れとして出る（R4 T3。STRICT_LEAKS で落ちる）
## 待ちは実時間で数える（2026-10-06 A6）: 止めた再生を AudioServer が手放すのは音の糸（実時間で回る）が1回混ぜた後。
## headless の速い既定（--fixed-fps 2000）では「0.1 秒の timer」が実時間の数ミリ秒で終わり、手放す前に quit して漏れていた
## （test_audio_danger の 26 ObjectDB・13 resources）。止める前の再生を弱い参照で持ち、全部消えるまで（最短 QUIET_MIN_MS、
## 最長 QUIET_MAX_MS の実時間）フレームを回す。
## 弱い参照で待つのは AudioStreamPlayer だけ。2D/3D の再生器は、物理の1歩の前に止めると再生を自分で持ったまま（setplayback。
## AudioServer には渡っていないので漏れではなく、節を消すときに手放す）で、待っても消えない。2D/3D は最短の待ちで足りる。
const QUIET_MIN_MS := 250    # 2D/3D と手の届かない再生（鳴ったまま先に消えた再生器の分）にも音の糸が何度も回る余り
const QUIET_MAX_MS := 3000
func quiet_audio() -> void:
	paused = true   # 先に木を止める（音の係が止めた音をまた鳴らさないように）。この後は finish だけ
	var pending: Array[WeakRef] = []
	var players: Array[Node] = []
	for n: Node in root.find_children("*", "", true, false):
		if n is AudioStreamPlayer or n is AudioStreamPlayer2D or n is AudioStreamPlayer3D:
			players.append(n)
			if n is AudioStreamPlayer and n.call("has_stream_playback"): pending.append(weakref(n.call("get_stream_playback")))
	var am: Node = root.get_node_or_null(^"AudioManager")
	if am != null and am.has_method("stop_everything"): am.call("stop_everything")
	for n: Node in players:
		if not is_instance_valid(n): continue
		n.call("stop")
		n.set("stream", null)   # 流れを外すと、再生の残り（AudioStreamPlayback）も手放す
	var t0 := Time.get_ticks_msec()
	while true:
		await process_frame
		var waited := Time.get_ticks_msec() - t0
		if waited >= QUIET_MAX_MS: break
		if waited < QUIET_MIN_MS: continue
		var alive := false
		for w: WeakRef in pending:
			if w.get_ref() != null:
				alive = true
				break
		if not alive: break

## 終わり。前と同じ「checks: N failures: M」の行のあとに、機械が読む1行を出す
func finish() -> void:
	if _finished: return
	_finished = true
	var elapsed_ms: float = float(Time.get_ticks_usec() - _started_usec) / 1000.0
	metrics["elapsed_ms"] = snappedf(elapsed_ms, 0.1)
	var over := over_budget()
	for o: Dictionary in over:
		print("OVER BUDGET %s = %s (max %s)%s" % [o.name, str(o.value), str(o.max), "" if time_budgets_enforced() or not is_time_metric(String(o.name)) else " [time: not enforced without GODOT_EXCLUSIVE=1]"])
	print("checks: ", checks, " failures: ", failures)
	var s: Script = get_script()
	var result := {
		"file": s.resource_path if s != null else "",
		"passed": checks - failures, "failed": failures, "checks": checks, "skipped": skipped,
		"failures": failure_labels, "metrics": metrics, "over_budget": over,
		"elapsed_ms": metrics["elapsed_ms"],
	}
	print("RESULT " + JSON.stringify(result, "", false))
	var enforced := over.filter(func(o: Dictionary) -> bool: return time_budgets_enforced() or not is_time_metric(String(o.name)))
	quit(1 if failures > 0 or not enforced.is_empty() else 0)
