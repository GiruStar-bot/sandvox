#!/usr/bin/env bash
# headless の試験を全部、1本ずつ回す（R4 T1）。Godot は同時に1つだけ。
#
# 使い方:
#   tools/run_tests.sh                 # 全部
#   tools/run_tests.sh bank town       # 道のりにその文字を含む試験だけ
#   tools/run_tests.sh --list          # 回す試験を並べるだけ
#   tools/run_tests.sh -j 3            # 3本ずつ並べて回す（既定 3。-j 1 で直列。並べるときの Godot は tools/godot1.sh の枠で起動）
#   tools/run_tests.sh --tier smoke    # 速い試験だけ（tools/test/tiers.json の smoke。-j3 で約2分）
#   tools/run_tests.sh --tier affected <git-rev>   # <rev> から変わったファイルに関わる試験だけ（同じフォルダ以下＋tiers.json の map）
#   tools/run_tests.sh --tier full     # 全部（既定。夜の一括）
# 環境変数:
#   GODOT=/usr/local/bin/godot   使う Godot（既定は PATH の godot）
#   TEST_TIMEOUT=600             1本あたりの上限の秒数（超えたら不合格。GODOT=tools/godot1.sh なら鍵を待つ時間は入れない）
#   TEST_BUDGET_SCALE=1.5        機械ごとの倍率（tools/test/budgets.json の machine_multiplier より優先）
#   STRICT_LEAKS=0               終わりの漏れを WARN に戻す（既定は 1 = 漏れも不合格。R4 T3 で漏れ0になったので）
#   GODOT_EXCLUSIVE=1            時間の上限（elapsed_ms・*_ms・ms_per_day）を判定する（独り占めで直列。無ければ上限超えは報告だけで、不合格にしない）
#   TEST_OUT=dir                 出力の場所（既定は outputs/tests/run_<時刻>_<pid>/。並べて回しても混ざらない）
#
# 回す試験: sim/**/test_*.gd、tools/**/test_*.gd、world/pixel/test_*.gd、world/flat/test_*.gd、audio_test/test_*.gd、native/test_*.gd、EXTRA_TESTS（窓なしで通る verify_*）。
# 試験は tools/test/test_kit.gd を継ぎ、最後に1行の `RESULT {json}` を出す（新しい試験の書き方は test_kit.gd の頭）。
# 台本の誤りで止まった試験は、TestKit の見張り（elapsed_ms の上限の2倍、無ければ120秒）が落として終わらせる。
# 不合格: 終了コード ≠0（終わりで落ちるのも）、落ちた項目、上限を超えた数（over_budget）、RESULT 行が無い、
#         「SCRIPT ERROR」、漏れ以外の「ERROR:」の行、時間切れ。
#         終わりの漏れ（"ObjectDB instances were leaked" / "resources still in use at exit" / "RIDs ... were leaked"）も
#         不合格（STRICT_LEAKS=1 が既定。R4 T3 で参照の輪を切った。STRICT_LEAKS=0 なら数えて WARN に留める）。
# 書くもの（1回ごとに別の場所。ほかの回の場所は消さない。複数の作業者が並べて回すと、前は logs を消し合っていた）:
#   <出力>/summary.txt（表）、<出力>/results.json（まとめ）、<出力>/logs/*.log。<出力> は TEST_OUT か outputs/tests/run_<時刻>_<pid>/
#   終わったら outputs/tests/latest（いちばん新しく終わった回へのリンク）と outputs/tests/summary.txt・results.json（その写し）を置き換える
# 既知の不合格: tools/test/known_failures.json（理由・持ち主・期限・rows つき）に載り、期限の切れていない試験の不合格は、
#   落ちた項目が全部 rows のどれかで始まるときだけ KNOWN と出し、終了コードに数えない（表の下に別に並べる）。
#   rows に無い項目が1つでも落ちれば FAIL（V114。照合は tools/test/known_rows.py）。期限が過ぎれば FAIL に戻る（R4 A6）。
# 終了コード: 全部合格（KNOWN は除く）なら 0、1本でも不合格なら 1。
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 2
JOBS=3; TIER=full; REV=""
ARGS=("$@"); FILTERS=(); LIST=0; k=0
while [ $k -lt ${#ARGS[@]} ]; do
	a="${ARGS[$k]}"
	case "$a" in
		--list) LIST=1 ;;
		-h|--help) sed -n '2,30p' "$0"; exit 0 ;;
		-j) k=$((k + 1)); JOBS="${ARGS[$k]:-3}" ;;
		-j[0-9]*) JOBS="${a#-j}" ;;
		--tier) k=$((k + 1)); TIER="${ARGS[$k]:-full}"
			if [ "$TIER" = affected ]; then k=$((k + 1)); REV="${ARGS[$k]:-HEAD}"; fi ;;
		*) FILTERS+=("$a") ;;
	esac
	k=$((k + 1))
done
case "$JOBS" in ''|*[!0-9]*|0) echo "bad -j"; exit 2 ;; esac
case "$TIER" in smoke|affected|full|heavy) ;; *) echo "bad --tier (smoke|affected <rev>|full|heavy)"; exit 2 ;; esac
# 時間の上限は独り占め（GODOT_EXCLUSIVE=1）のときだけ判定する。独り占めは枠を全部取るので並べても意味がない
[ "${GODOT_EXCLUSIVE:-0}" = "1" ] && JOBS=1
# 並べるなら枠つきの起動（同時 GODOT_SLOTS 本まで）。直列は今まで通り godot を直接
if [ -z "${GODOT:-}" ]; then
	if [ "$JOBS" -gt 1 ]; then GODOT="$ROOT/tools/godot1.sh"; else GODOT=godot; fi
fi
export GODOT_BIN="${GODOT_BIN:-godot}"
TEST_TIMEOUT="${TEST_TIMEOUT:-600}"
BASE="$ROOT/outputs/tests"
OUT="${TEST_OUT:-$BASE/run_$(date +%Y%m%d_%H%M%S)_$$}"
case "$OUT" in /*) ;; *) OUT="$ROOT/$OUT" ;; esac
LOGS="$OUT/logs"
export TESTPLAY_REPORT_DIR="$OUT/testplay"   # 試遊ボットの報告はこの回の場所へ（outputs/testplay を書き換えない）

# 窓なしで通ると分かっている、名前が test_ でない試験（R4_godot_scripter 2.1）
# Why not the verify_* list (before the clean-up): every entry was a game script under world/pixel, which left this line (TO_PM 117)
EXTRA_TESTS=()

# 載っているのに無いファイルで止める（D399: 6本の幻が1時間半の回しの中で黙って落ちていた）。
# Why not discover() の中で見る: あそこは `{ ... } | sort -u` の中なので、exit しても下請けの殻だけが終わり、戻り値は捨てられる（2026-10-18 に実際そうなった）
# Why not 警告だけ: 長い回しでは流れて消える。curated な一覧なので、無いファイルは書き間違いであって正しい状態ではない
for f in "${EXTRA_TESTS[@]}"; do
	[ -f "$f" ] || { echo "EXTRA_TESTS に無いファイル: $f" >&2; exit 2; }
done

discover() {
	# Why not `find .`: scratchpad/ の作業者の worktree に試験の写しが丸ごとあり、native/third_party は他人の木。
	# .gdignore も .git/info/exclude も find は見ないので、探す場所を数え上げる（native は maxdepth 1 で third_party に入らない）
	# Why not tools/test ごと外す: あそこに本物の試験が増えたら拾いたい。継ぐ元の test_kit.gd だけを名前で外す
	{
		find sim -name 'test_*.gd' -type f
		find tools -name 'test_*.gd' -type f ! -path 'tools/test/test_kit.gd'
		find world/pixel -maxdepth 1 -name 'test_*.gd' -type f 2>/dev/null
		find world/flat -maxdepth 1 -name 'test_*.gd' -type f 2>/dev/null
		find audio_test -maxdepth 1 -name 'test_*.gd' -type f 2>/dev/null
		find native -maxdepth 1 -name 'test_*.gd' -type f 2>/dev/null
		for f in "${EXTRA_TESTS[@]}"; do echo "$f"; done
	} | sort -u
}

TESTS=()
while IFS= read -r f; do
	if [ ${#FILTERS[@]} -gt 0 ]; then
		hit=0
		for p in "${FILTERS[@]}"; do [[ "$f" == *"$p"* ]] && hit=1; done
		[ $hit -eq 1 ] || continue
	fi
	TESTS+=("$f")
done < <(discover | python3 "$ROOT/tools/test/tiers.py" "$TIER" "$REV")

if [ $LIST -eq 1 ]; then printf '%s\n' "${TESTS[@]}"; exit 0; fi
# 型の一覧（class_name）を最新にしてから回す。古いと新しい型が「宣言されていない」と落ちる（2026-10-06）
"$GODOT" --headless --path "$ROOT" --import >/dev/null 2>&1 || true
if [ ${#TESTS[@]} -eq 0 ]; then echo "no tests matched"; exit 2; fi

mkdir -p "$LOGS"
rm -f "$LOGS"/*.log   # この回の場所だけ（TEST_OUT を使い回したとき）
echo "output: $OUT"
INDEX="$OUT/.index.tsv"
ROWS="$OUT/.rows"; rm -rf "$ROWS"; mkdir -p "$ROWS"
echo "tier: $TIER${REV:+ $REV} | jobs: $JOBS | tests: ${#TESTS[@]}"
started=$(date +%s%N)
run_one() {   # $1=番号 $2=ファイル。この試験の書き場所は別（TESTPLAY_REPORT_DIR も試験ごと）
	local i="$1" f="$2" name log t0 rc ms
	name="$(echo "${f%.gd}" | tr '/' '_')"
	log="$LOGS/$name.log"
	export TESTPLAY_REPORT_DIR="$OUT/testplay/$name"
	t0=$(date +%s%N)
	started_file="$OUT/.started.$i"; rm -f "$started_file"   # 試験ごと（-j で並べても混ざらない）
	if [ "$(basename "$GODOT")" = "godot1.sh" ]; then   # 鍵つきの起動: 時間切れは鍵を取ってから数える（ほかの作業者の Godot を待つ間は数えない）
		GODOT1_STARTED_FILE="$started_file" GODOT1_TIMEOUT="$TEST_TIMEOUT" "$GODOT" --headless --path "$ROOT" -s "res://$f" > "$log" 2>&1
	else
		timeout --kill-after=10 "$TEST_TIMEOUT" "$GODOT" --headless --path "$ROOT" -s "res://$f" > "$log" 2>&1
	fi
	rc=$?
	t1=$(date +%s%N)
	# ms は Godot が動いた時間だけ（鍵を待った時間は wait に分ける。前は待ちも入れていて、test_audio_danger が
	# 実は 1.2 秒なのに「29.5分」と出た回があった。2026-10-06 A6）
	ts=$t0; [ -s "$started_file" ] && ts=$(cat "$started_file")
	ms=$(( (t1 - ts) / 1000000 )); wait_ms=$(( (ts - t0) / 1000000 ))
	wait_note=""; [ $wait_ms -gt 0 ] && wait_note=" (waited $wait_ms ms for a slot)"
	printf '[%2d/%d] %-52s rc=%-3s %6d ms%s\n' "$i" "${#TESTS[@]}" "$f" "$rc" "$ms" "$wait_note"
	printf '%s\t%s\t%s\t%s\n' "$f" "$rc" "$ms" "$log" > "$ROWS/$(printf '%04d' "$i").tsv"
}
i=0
for f in "${TESTS[@]}"; do
	i=$((i + 1))
	while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do wait -n 2>/dev/null || sleep 0.2; done
	run_one "$i" "$f" &
done
wait
cat "$ROWS"/*.tsv > "$INDEX" 2>/dev/null
# 絵の確かめ（Python、ART_PIPELINE_R4 A0）: 移った組は --strict で FAIL なら不合格、まだの組は WARN の数だけ（validate_assets.py の gate）
hit=$(( ${#FILTERS[@]} == 0 ))
if [ "$TIER" = affected ]; then hit=0; git diff --name-only "$REV" 2>/dev/null | grep -qE '^(tools/pixel/|assets/|world/pixel/assets)' && hit=1; fi
for p in "${FILTERS[@]}"; do [[ "tools/pixel/validate_assets.py" == *"$p"* ]] && hit=1; done
# Why not run it unconditionally: the modern line has no tools/pixel (the clean-up, TO_PM 117)
if [ $hit -eq 1 ] && [ -f tools/pixel/validate_assets.py ]; then
	log="$LOGS/tools_pixel_validate_assets.log"; t0=$(date +%s%N)
	python3 tools/pixel/validate_assets.py --gate > "$log" 2>&1; rc=$?
	printf '[art] %-52s rc=%-3s %6d ms\n' "tools/pixel/validate_assets.py --gate" "$rc" "$(( ($(date +%s%N) - t0) / 1000000 ))"
	printf '%s\t%s\t%s\t%s\n' "tools/pixel/validate_assets.py" "$rc" "$(( ($(date +%s%N) - t0) / 1000000 ))" "$log" >> "$INDEX"
fi
total_ms=$(( ($(date +%s%N) - started) / 1000000 ))

TEST_JOBS="$JOBS" TEST_TIER="$TIER" GODOT_EXCLUSIVE="${GODOT_EXCLUSIVE:-0}" STRICT_LEAKS="${STRICT_LEAKS:-1}" TEST_TIMEOUT="$TEST_TIMEOUT" python3 - "$INDEX" "$OUT" "$total_ms" <<'PY'
import json, os, re, sys, time
sys.path.insert(0, "tools/test")
import known_rows
index, out, total_ms = sys.argv[1], sys.argv[2], int(sys.argv[3])
enforce_time = os.environ.get("GODOT_EXCLUSIVE", "0") == "1"
time_re = re.compile(r"(^|_)ms($|_)|ms_per_day|elapsed")   # 時間の数（混み合いで揺れる）
strict = os.environ.get("STRICT_LEAKS", "1") == "1"
timeout_s = int(os.environ.get("TEST_TIMEOUT", "600"))
# 終わりの漏れ（Godot の出す行）。数も拾う
leak_res = {"objects": re.compile(r"^WARNING: (\d+) ObjectDB instances were leaked at exit"),
            "resources": re.compile(r"^ERROR: (\d+) resources still in use at exit"),
            "rids": re.compile(r'^WARNING: (\d+) RIDs of type ".*" were leaked')}
# 漏れ以外の「ERROR:」の行は不合格（わざと出す試験ができたら、ここに許す型を足す）
# その1本目が tools/security/test_mcp_token.gd: 「鍵が無ければ橋は始まらない」という正しい振る舞いを確かめるのに、
# その振る舞い自体が mcp_bridge.gd:82 で push_error を出す。上の行が言う通り、ここが足す場所。
# Why not アドオンの push_error を push_warning に落とす: addons/godot_mcp は取り込み物で、CREDITS.md:54 の通り
#   licence が未確認（中に LICENSE が無い。MAIN_HANDOFF の未決の点にも挙がっている）。直しても次の取り込みで消え、
#   出自が未解決の所に差分を増やすことになる。そもそも鍵無しで始まらないのは T023 の構え（mcp_bridge.gd:80。
#   橋は socket に答えた相手にエディタを渡す）なので、試験のために本番の設定ミスを静かにするのは向きが逆。
# Why not 'godot_mcp:.*' でまとめて許す: 部分系まるごとを除外してしまう。文面1つに錨を打つ。
# 落とし穴（承知の上でこうする）: アドオンがこの文面を変えると錨が外れ、この試験はまた赤くなる。黙って通るより安全な向き。
mcp_no_token = re.compile(r"^ERROR: godot_mcp: GODOT_MCP_BRIDGE_TOKEN is not set; the bridge does not start$")
# Why not 前方一致だけ（「...is not set」で止める）: 後ろに何か足された行まで許してしまう。
#   例「...is not set; starting anyway with the key sk-abc123」が黙って通る。長くなった行こそ振る舞いが変わった印なので、
#   そこで静かになるのは逆向き。全文を $ まで留め、言い回しが変われば合わなくなって赤くなる（それが安全な向き）。
# 2本目: sim/scenario/test_spin_up.gd の K2・K3・ST4。「合わない鍵フレーム・データの無い時代・止まらない空回しを拒む」のを確かめる試験で、
# 拒む側（spin_up.gd の push_error）が、拒んだ印として ERROR: の行を出す。6行を、文面ごとに錨を打って許す。
# Why not spin_up.gd の push_error を push_warning に落とす: 本番で鍵フレームを拒んだ声が静かになる。拒むのが正しい振る舞いで、声はその証拠。
# Why not 'ERROR: keyframe:.*' や 'ERROR: spin-up.*' でまとめて許す: 別の理由で拒んだ行まで黙って通る。理由ごとに文面の形を留める。
# 落とし穴（承知の上でこうする）: 文面を変えると錨が外れ、この試験が赤くなる。黙って通るより安全な向き。
spin_up_refusals = [
    re.compile(r'^ERROR: keyframe: user://test_spin_up/\S+ was made with params \{[^{}]*\}, asked \{[^{}]*\}$'),
    re.compile(r"^ERROR: keyframe: rules_version [0-9a-f]{64}, the code is [0-9a-f]{64}; refusing a keyframe of other rules$"),
    re.compile(r"^ERROR: keyframe: era -?\d+, expected -?\d+$"),
    re.compile(r"^ERROR: keyframe: digest [0-9a-f]{32} after load, header says [0-9a-f]{32}$"),
    re.compile(r"^ERROR: spin-up not stationary by max_years \d+ \(era -?\d+, rules_version [0-9a-f]{16}\): last window ending year \d+: .*$"),
    re.compile(r"^ERROR: spin-up: no Earth data slice for -?\d+ \(supported: \[[-0-9, ]*\]\)$")]
error_allow = [leak_res["resources"], mcp_no_token] + spin_up_refusals
known = {}
try:
    kf = json.load(open("tools/test/known_failures.json", encoding="utf-8"))
    for k in kf.get("failures", []): known[k["file"]] = k
except (OSError, ValueError, KeyError) as e:
    print("known_failures.json: %s" % e)
today = time.strftime("%Y-%m-%d")
rows = []
for line in open(index, encoding="utf-8"):
    f, rc, ms, log = line.rstrip("\n").split("\t")
    rc, ms = int(rc), int(ms)
    text = open(log, encoding="utf-8", errors="replace").read()
    result = None
    for l in text.splitlines():
        if l.startswith("RESULT "):
            try: result = json.loads(l[7:])
            except ValueError: result = None
    leaks, leak_counts, engine_errors = [], {}, []
    for l in text.splitlines():
        for k, r in leak_res.items():
            mm = r.search(l)
            if mm:
                leaks.append(l.strip())
                leak_counts[k] = leak_counts.get(k, 0) + int(mm.group(1))
        if l.startswith("ERROR:") and not any(r.search(l) for r in error_allow): engine_errors.append(l.strip())
    script_errors = len(re.findall(r"SCRIPT ERROR", text))
    reasons, warns, notes = [], [], []
    if rc in (124, 137): reasons.append("timeout %ds" % timeout_s)
    elif rc != 0: reasons.append("exit %d" % rc)
    if result is None: reasons.append("no RESULT line")
    else:
        if result.get("failed", 0) > 0: reasons.append("%d failed" % result["failed"])
        for o in result.get("over_budget", []):
            msg = "over budget %s=%s>%s" % (o["name"], o["value"], round(o["max"], 3))
            if time_re.search(o["name"]) and not enforce_time: notes.append(msg + " (time, not enforced: GODOT_EXCLUSIVE=1 to enforce)")
            else: reasons.append(msg)
    if script_errors: reasons.append("%d SCRIPT ERROR" % script_errors)
    if engine_errors: reasons.append("%d ERROR: %s" % (len(engine_errors), engine_errors[0][:120]))
    if leaks: (reasons if strict else warns).append("leak " + " ".join("%s=%d" % kv for kv in sorted(leak_counts.items())))
    k = known.get(f)
    status, reasons, kwarns = known_rows.classify(k, result, reasons, today)
    warns += kwarns
    if status == "PASS" and warns: status = "WARN"
    rows.append({
        "file": f, "exit": rc, "wall_ms": ms,
        "status": status, "known": k,
        "passed": result.get("passed") if result else None,
        "failed": result.get("failed") if result else None,
        "skipped": result.get("skipped") if result else None,
        "metrics": result.get("metrics", {}) if result else {},
        "failures": result.get("failures", []) if result else [],
        "leaks": leak_counts, "budget_notes": notes, "reasons": reasons, "warnings": warns, "log": os.path.relpath(log),
    })
n_fail = sum(1 for r in rows if r["status"] == "FAIL")
n_warn = sum(1 for r in rows if r["status"] == "WARN")
n_known = sum(1 for r in rows if r["status"] == "KNOWN")
summary = {
    "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "total_ms": total_ms, "tests": len(rows),
    "pass": len(rows) - n_fail - n_warn - n_known, "warn": n_warn, "fail": n_fail, "known": n_known,
    "checks_passed": sum(r["passed"] or 0 for r in rows), "checks_failed": sum(r["failed"] or 0 for r in rows),
    "leaked_objects": sum(r["leaks"].get("objects", 0) for r in rows),
    "strict_leaks": strict, "time_budgets_enforced": enforce_time, "jobs": int(os.environ.get("TEST_JOBS", "1")), "tier": os.environ.get("TEST_TIER", "full"), "results": rows,
}
json.dump(summary, open(out + "/results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
lines = ["%-52s %-5s %6s %6s %5s %8s  %s" % ("test", "stat", "pass", "fail", "skip", "ms", "notes"), "-" * 110]
for r in rows:
    lines.append("%-52s %-5s %6s %6s %5s %8d  %s" % (r["file"], r["status"], r["passed"], r["failed"], r["skipped"],
                 r["wall_ms"], "; ".join(r["reasons"] + r["warnings"] + r["budget_notes"])[:200]))
lines.append("-" * 110)
for r in rows:
    if r["status"] == "KNOWN":
        k = r["known"]
        lines.append("KNOWN %s (until %s, %s): %s" % (r["file"], k.get("expires"), k.get("owner", "?"), k.get("reason", "")))
lines.append("tests %d: pass %d, warn %d, fail %d, known %d | checks passed %d, failed %d | leaked objects %d | total %.1f s%s" % (
    len(rows), summary["pass"], n_warn, n_fail, n_known, summary["checks_passed"], summary["checks_failed"], summary["leaked_objects"],
    total_ms / 1000.0, " | STRICT_LEAKS" if strict else "") + ("" if enforce_time else " | time budgets: report only"))
open(out + "/summary.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
sys.exit(1 if n_fail else 0)
PY
rc=$?
# いちばん新しく終わった回を outputs/tests/latest と、その写しの summary.txt・results.json に（置き換えは mv で一度に）
if [ -f "$OUT/summary.txt" ]; then
	mkdir -p "$BASE"
	ln -sfn "$OUT" "$BASE/.latest.$$" && mv -Tf "$BASE/.latest.$$" "$BASE/latest"
	for f in summary.txt results.json; do
		cp "$OUT/$f" "$BASE/.$f.$$" && mv -f "$BASE/.$f.$$" "$BASE/$f"
	done
fi
exit $rc
