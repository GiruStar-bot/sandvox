# The start's stages against the oracle's trace (START_PORT_PLAN §2, rows S0-a by stage): from the oracle's whole state at stage
# FROM (or from people.create's inputs when FROM is "-"), the Python stages run through TO, and every hash the oracle wrote at TO
# must be equal. TO "19_weights" is the whole start with _create_tiers' weights (rows S0-a and S0-p). TO "00_inputs" with FROM "-" is row S0-j: the inputs as read, before any stage
#   python py/tests/test_start_stage.py <trace dir> <FROM|-> <TO>
# Persons arrays the start port leaves to the persons port (finish_person's draws) are reported, not failed: NOT_PORTED below
import os
import sys
import time

from common import Kit, peak_mb
from core import digest
from tiers.start import build, create, trace

NOT_PORTED = {"persons." + n for n in ("traits", "lam", "dw", "emo", "emo_base", "dd", "dream_kind", "dream_importance",
                                       "dream_progress", "dream_status", "dream_blocked", "pref_leisure", "pref_social",
                                       "pol_interest", "q_income", "q_price", "q_job", "mem_month", "mem_kind", "mem_val",
                                       "mem_head", "basket", "q_act", "pressure_prev", "rank")}


def main():
    d, first, last = sys.argv[1], sys.argv[2], sys.argv[3]
    k = Kit("py/tests/test_start_stage.py %s %s" % (first, last))
    t0 = time.perf_counter()
    if first == "-":
        p, prefectures = create.inputs()
        ctx = {"prefectures": prefectures}
        first = None
    else:
        p, ctx = trace.load_stage(os.path.join(d, first))
    t1 = time.perf_counter()
    if last == "19_weights":
        build.run(p, ctx, first, build.NAMES[-1])
        for i in range(p.n):
            p.weight[i] = 1.0
    elif last != "00_inputs":
        build.run(p, ctx, first, last)
    t2 = time.perf_counter()
    ref = digest.read_hashes(os.path.join(d, last + ".sha.txt"))
    got = trace.stage_hashes(p, ctx, list(ref))
    bad = [n for n in sorted(ref) if got[n] != ref[n] and n not in NOT_PORTED]
    info = [n for n in sorted(ref) if got[n] != ref[n] and n in NOT_PORTED]
    k.check(not bad, "S0-a %s: %d of %d hashes equal to the oracle's%s" % (
        last, len(ref) - len(bad) - len(info), len(ref) - len(info), (", differing " + " ".join(bad[:40])) if bad else ""))
    if info:
        print("info persons arrays left to the persons port, differing: " + " ".join(info))
    print("time load %.1f s, stages %.1f s, peak %.0f MB" % (t1 - t0, t2 - t1, peak_mb()))
    k.finish()


if __name__ == "__main__":
    main()
