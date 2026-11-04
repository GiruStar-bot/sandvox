#!/usr/bin/env python3
"""tools/test/tiers.json の中身が本物の試験と合っているかを見る。合わなければ 1 を返す。
使い方: tools/run_tests.sh --list --tier full | python3 -I tools/test/tiers_check.py

smoke_limit_s・slow・measured_s は、どの道具も読まない覚え書きだった（D399 の根っこ）。読まない値は守りではなく飾りなので、
ここで守らせる。載っているのに出てこない試験（phantom）、両方の段に載っている試験、smoke_limit_s を超える smoke の試験は
不合格。段に載っていない試験と、時間の測りが無い smoke の試験は数だけ出す（full では回るので、不合格にはしない）。

Why not ここで試験を探し直す: 探す所を数え上げた写しが2つになり、D399 で落ちたのと同じ形でずれる。
run_tests.sh の discover() が出した物を受け取る（あれが本物の一覧）。
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# run_tests.sh:148-156 が discover() を通さず別の行として回す、Python の絵の確かめ。tiers.json に時間だけ載っている
ART_GATE = "tools/pixel/validate_assets.py"


def main():
    # Why not the art gate always (before the clean-up): the modern line has no tools/pixel (TO_PM 117)
    found = set(l.strip() for l in sys.stdin if l.strip()) | ({ART_GATE} if os.path.exists(os.path.join(ROOT, ART_GATE)) else set())
    if len(found) < 2:
        print("tiers_check: 試験の一覧が標準入力に来ていない（使い方を見よ）", file=sys.stderr)
        return 2
    t = json.load(open(os.path.join(ROOT, "tools/test/tiers.json"), encoding="utf-8"))
    smoke, slow, meas, limit = list(t["smoke"]), t["slow"], t["measured_s"], float(t["smoke_limit_s"])
    # heavy は tiers.py の full が外す段（nightly が -j1 で回す）。一覧に出ないので、ファイルがあるものだけ見つかった扱いにする
    found |= {h for h in t.get("heavy", []) if os.path.exists(os.path.join(ROOT, h))}
    bad = []

    for name, listed in (("smoke", smoke), ("slow", list(slow)), ("measured_s", list(meas))):
        for x in sorted(set(listed) - found):
            bad.append("%s に載っているが出てこない: %s" % (name, x))
    for x in sorted(x for x in set(smoke) if smoke.count(x) > 1):
        bad.append("smoke に2回載っている: %s" % x)
    for x in sorted(set(smoke) & set(slow)):
        bad.append("smoke と slow の両方に載っている（tiers.py は slow を読まないので smoke で回る）: %s" % x)
    for x in sorted(x for x in smoke if x in meas and float(meas[x]) > limit):
        bad.append("smoke だが smoke_limit_s=%g を超える: %s (%g 秒)" % (limit, x, float(meas[x])))
    for x in sorted(x for x in slow if x in meas and float(slow[x]) != float(meas[x])):
        bad.append("slow と measured_s で時間が違う: %s (%g と %g)" % (x, float(slow[x]), float(meas[x])))

    untiered = sorted(found - set(smoke) - set(slow) - {ART_GATE})
    print("TIERS tests %d | smoke %d | slow %d | measured_s %d | smoke_limit_s %g"
          % (len(found) - 1, len(smoke), len(slow), len(meas), limit))
    print("TIERS どの段にも無い: %d（full では回る） | smoke で時間の測りが無い: %d"
          % (len(untiered), len([x for x in smoke if x not in meas])))
    for line in bad:
        print("TIERS FAIL " + line)
    print("TIERS rc=%d" % (1 if bad else 0))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
