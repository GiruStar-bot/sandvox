#!/usr/bin/env python3
"""run_tests.sh の段の選び。標準入力の試験の道のり（1行1本）を、段で絞って標準出力へ。
使い方: ... | python3 tools/test/tiers.py <smoke|affected|full|heavy> [<git-rev>]
表は tools/test/tiers.json。affected は `git diff --name-only <rev>` ＋ 未追跡のファイルから選ぶ。"""
import json, os, subprocess, sys

root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
tier = sys.argv[1] if len(sys.argv) > 1 else "full"
rev = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
tests = [l.strip() for l in sys.stdin if l.strip()]
tiers = json.load(open(os.path.join(root, "tools/test/tiers.json"), encoding="utf-8"))


CODE_EXT = (".gd", ".cpp", ".h", ".json", ".bin", ".tscn", ".tres", ".cfg", ".py", ".sh")


def changed_files(rev):
    out = subprocess.run(["git", "-C", root, "diff", "--name-only", rev], capture_output=True, text=True, check=True).stdout.split()
    out += subprocess.run(["git", "-C", root, "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True).stdout.split()
    return sorted(set(out))


def affected(tests, files, tiers):
    pick = set()
    for t in tests:
        tdir = os.path.dirname(t)
        for f in files:
            # 試験のファイルそのもの、試験のフォルダ（以下）の変更
            if f == t or f.startswith(tdir + "/"):
                pick.add(t)
    for prefix, pats in tiers.get("map", {}).items():
        if any(f.startswith(prefix) for f in files):
            for t in tests:
                if "*" in pats or any(t.startswith(p) for p in pats):
                    pick.add(t)
    return [t for t in tests if t in pick]


if tier == "smoke":
    smoke = set(tiers["smoke"])
    sel = [t for t in tests if t in smoke]
elif tier == "affected":
    files = changed_files(rev)
    sel = affected(tests, files, tiers)
    # 地図に載らない変更で試験が0本になると見逃すので、その時は smoke に落とし、載せるべきファイルを出す（D116）
    code = [f for f in files if (f.endswith(CODE_EXT) and not f.startswith("outputs/")) or f == "project.godot"]
    lone = [f for f in code if not affected(tests, [f], tiers)]
    for f in lone:
        print("UNMAPPED " + f, file=sys.stderr)
    if lone:
        smoke = set(tiers["smoke"])
        sel = [t for t in tests if t in smoke or t in sel]
elif tier == "heavy":
    heavy = set(tiers.get("heavy", []))
    sel = [t for t in tests if t in heavy]
else:
    # heavy: 長い通し試験（深い時間の生成・図書館・長い走り）は full から外し、nightly が -j1 で別に回す（V063: 3本並べると箱が詰まり 1500 秒を超えた）
    heavy = set(tiers.get("heavy", []))
    sel = [t for t in tests if t not in heavy]
print("\n".join(sel))
