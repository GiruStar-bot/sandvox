# The core's save and restore (the PM, TO_E.md 07:17): a run saved at month a and restored continues to month b at the
# uninterrupted run's full digest, every tr_* field included, on the path chosen (TIERS_NB=1 for Numba)
#   python py/tests/test_resume.py <oracle dir with m00/> <a> <b>
import os
import shutil
import sys

from common import Kit, ROOT
from tiers import state
if os.environ.get("TIERS_NB") == "1":
    from tiers import month_nb as month
else:
    from tiers import month


def run(p, m):
    while p.month < m:
        month.step(p)
        p.month += 1
    return p


def main():
    d, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    kit = Kit("py/tests/test_resume.py")
    path = "numba" if os.environ.get("TIERS_NB") == "1" else "pure"
    p = run(month.St(state.load(os.path.join(d, "m00"), as_lists=path == "pure")), b)
    want, want_f = state.digest_st(p)
    del p
    q = run(month.St(state.load(os.path.join(d, "m00"), as_lists=path == "pure")), a)
    sd = os.path.join(ROOT, "outputs", "py_resume_%s_m%02d" % (path, a))
    shutil.rmtree(sd, ignore_errors=True)
    state.save(q, sd)
    at_a, at_a_f = state.digest_st(q)
    del q
    r = month.St(state.load(sd, as_lists=path == "pure"))
    back, back_f = state.digest_st(r)
    kit.check(back == at_a, "%s: the state saved at month %d and read back has the same full digest (%s, %s); fields differing %s"
              % (path, a, back[:16], at_a[:16], sorted(n for n in at_a_f if back_f.get(n) != at_a_f[n])[:8]))
    run(r, b)
    got, got_f = state.digest_st(r)
    kit.check(got == want, "%s: restored at month %d and run to %d, the full digest %s equals the uninterrupted run's %s; fields differing %s"
              % (path, a, b, got[:16], want[:16], sorted(n for n in want_f if got_f.get(n) != want_f[n])[:8]))
    shutil.rmtree(sd, ignore_errors=True)
    kit.finish()


if __name__ == "__main__":
    main()
