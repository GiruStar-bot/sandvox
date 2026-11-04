#!/usr/bin/env bash
# Godot の同時起動の数をしぼる鍵つきの起動（R4）。複数の作業者が並んでいても、同時に動く Godot は GODOT_SLOTS 本まで。
# 使い方: tools/godot1.sh --headless --path . --script res://...   （引数は godot と同じ）
#         GODOT=tools/godot1.sh tools/run_tests.sh               （試験の一括も、1本ずつ枠を取る）
# 枠: GODOT_SLOTS（既定 3。この箱は4コア）。headless には GPU の取り合いは無い。しぼるのは CPU と、時間の上限（elapsed_ms）の
#     ある試験が混み合いで落ちないため。
# 重さ・速さを測るとき（bench、ms/日、起動時間）は GODOT_EXCLUSIVE=1 で全部の枠を取り、1本だけで走らせる。
# 鍵: /tmp/the_world_godot.slot<N>.lock（flock）。待っている間は何も出さない。
# GODOT1_TIMEOUT=秒 なら、枠を取ってから Godot の時間だけを測る（枠を待つ時間は入れない。run_tests.sh が使う。超えたら終了コード 124）
# GODOT1_STARTED_FILE=道のり なら、枠を取った時刻（date +%s%N）をそこに書く（run_tests.sh が待ちと Godot の時間を分けて出すため）
SLOTS="${GODOT_SLOTS:-3}"
BIN="${GODOT_BIN:-godot}"
# headless は既定で超高速: 描画の繰り返しを止め、実時間に合わせない（1フレーム = 1/2000 秒として即次へ）。GODOT_REALTIME=1 で外す。--import には付けない
FAST=()
case " $* " in *" --headless "*) case " $* " in *" --import "*) ;; *) [ "${GODOT_REALTIME:-0}" = "1" ] || FAST=(--disable-render-loop --fixed-fps 2000) ;; esac ;; esac
run() {
	set -- "${FAST[@]}" "$@"
	[ -n "${GODOT1_STARTED_FILE:-}" ] && date +%s%N > "$GODOT1_STARTED_FILE"
	if [ -n "${GODOT1_TIMEOUT:-}" ]; then
		exec timeout --kill-after=10 "$GODOT1_TIMEOUT" "$BIN" "$@"
	fi
	exec "$BIN" "$@"
}
if [ "${GODOT_EXCLUSIVE:-0}" = "1" ]; then
	# 全部の枠を順に取る（取る順を固定して、取り合いで止まらないようにする）
	for i in $(seq 1 "$SLOTS"); do
		exec {fd}>"/tmp/the_world_godot.slot$i.lock"
		flock "$fd"
	done
	run "$@"
fi
while true; do
	for i in $(seq 1 "$SLOTS"); do
		exec {fd}>"/tmp/the_world_godot.slot$i.lock"
		if flock -n "$fd"; then
			run "$@"
		fi
		exec {fd}>&-
	done
	sleep 1
done
