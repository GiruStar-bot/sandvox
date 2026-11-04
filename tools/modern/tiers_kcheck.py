"""T1s-g's verdict from tiers_kcheck.gd's JSON (ISS_TIERED_POPULATION.md §12.5 F8, §12.8 10.6):
  python3 -I tools/modern/tiers_kcheck.py <json> [<json> ...]   (one file per K run is merged)"""
import json, math, sys
d = {}
for path in sys.argv[1:]:
    d.update(json.load(open(path)))
TOL = {"poor": 0.0075, "bundles": 0.0075}


def mean_se(v):
    m = sum(v) / len(v)
    se = (math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1)) / math.sqrt(len(v))) if len(v) > 1 else float("nan")
    return m, se


fail = 0
noext = 0
for scope in ("national", "small"):
    for r in ("assets", "poor", "bundles"):
        t = {k: [row[scope][r] for row in d[k]] for k in ("4", "8", "16")}
        n = min(len(t[k]) for k in t)
        m = {k: mean_se(t[k][:n])[0] for k in t}
        se = {k: mean_se(t[k][:n])[1] for k in t}
        # the K runs share seeds and keyed draws, so the differences are read per seed and their SE over the seeds (M004 W7)
        # Why not the independent-sample variances: under the runs' positive covariance they are upper bounds, and the regime gate
        # then rejects less often than it should
        reg_m, reg_se = mean_se([(t["4"][s] - t["8"][s]) - 2 * (t["8"][s] - t["16"][s]) for s in range(n)])
        regime = abs(reg_m) <= 2 * reg_se
        inf_m, inf_se = mean_se([2 * t["16"][s] - t["8"][s] for s in range(n)])
        diff = {"4": mean_se([t["4"][s] - (2 * t["16"][s] - t["8"][s]) for s in range(n)]),
                "8": mean_se([t["8"][s] - (2 * t["16"][s] - t["8"][s]) for s in range(n)])}
        tol = TOL.get(r, 0.01 * abs(inf_m))
        bound = {k: abs(diff[k][0]) + 1.645 * diff[k][1] for k in ("4", "8")}
        if not regime:
            verdict = "NO EXTRAPOLATION"
            noext += 1
        elif all(bound[k] <= tol for k in ("4", "8")):
            verdict = "PASS"
        else:
            verdict = "FAIL"
            fail += 1
        print("T1s-g %-8s %-7s K4 %.5f±%.5f K8 %.5f±%.5f K16 %.5f±%.5f T(inf) %.5f±%.5f paired regime %.5f±%.5f bound K4 %.5f K8 %.5f tol %.5f 1/K regime %s %s" % (
            scope, r, m["4"], se["4"], m["8"], se["8"], m["16"], se["16"], inf_m, inf_se, reg_m, reg_se, bound["4"], bound["8"], tol, "yes" if regime else "no", verdict))
print("T1s-g failures", fail, "no extrapolation (the regime failed, not a pass)", noext)
