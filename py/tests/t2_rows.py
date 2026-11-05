# sim/modern/test_modern_t2_month.gd's year-1 death rows, line for line (T23_PLAN §12): _mh, _gsum, _t2s_dgq, _t2s_qk, over the
# year's tallies as that test sums them (year_add over months 1-12 of tr_margins["t22"]).
# T2s-dgq (year 1, DIAGNOSTIC) Mantel-Haenszel rate ratios over single age x sex strata, Robins-Breslow-Greenland variance: grade 3 ÷
#        grade 1 and grade 4 ÷ grade 3 by sex over 65+ against R74's 4 rows; the bottom ÷ top quartile over each of M010's 10
#        observations' sex and ages within ±2 years of its age at risk on the two-group scale (÷ 1.5) against y with τ; 14 at z 2.914
# T2s-qk (year 1, the stop rule) the bottom ÷ top MH log rate ratio at least two thirds of the MH-weighted ln I_3(a)
import math

from core.gd import gd_round
from tiers import month

INF = float("inf")
Z_DGQ = 2.914
YEAR_KEYS = ["d_as", "d_old", "x_as", "e_as", "v_as", "d_g", "x_g", "d_k", "x_k"]
R74_ROWS = [["R74-0001 AGES 1B M, grade 3 / grade 1", 0, 2, 0, 2.44, 2.14, 2.80], ["R74-0005 AGES 1B F, grade 3 / grade 1", 1, 2, 0, 1.88, 1.44, 2.47],
            ["R74-0024 NIPPON DATA90 model 2 M, grade 4 / grade 3", 0, 3, 2, 1.31, 1.00, 1.73], ["R74-0025 NIPPON DATA90 model 2 F, grade 4 / grade 3", 1, 3, 2, 1.43, 1.10, 1.84]]
M010_OBS = [["R73-009 M", 0, 72.5, 0.19845093872383832, 0.0742863177222006], ["R73-011 M", 0, 82.0, -0.01980262729617973, 0.059713500781834496],
            ["R73-013 F", 1, 72.5, 0.4942963218147801, 0.12385631052695982], ["R73-015 F", 1, 82.0, -0.17395330712343798, 0.08945492733006984],
            ["R73-018 M", 0, 67.0, 0.1906203596086497, 0.21707234911538092], ["R73-019 M", 0, 67.0, 0.3852624007906449, 0.1768265095755335],
            ["R73-020 F", 1, 67.0, 0.11332868530700327, 0.3777484055047742], ["R73-021 F", 1, 67.0, -0.40047756659712525, 0.3216049269135736],
            ["R73-001/R73-002/R73-003 M", 0, 75.0, 0.3401754717150547, 0.07208801532958557], ["R73-005/R73-006/R73-007 F", 1, 75.0, 0.38236080054220545, 0.21163082095381233]]


def year_add(yr, tl):
    for key in YEAR_KEYS:
        if key not in yr:
            yr[key] = list(tl[key])
        else:
            for x in range(len(tl[key])):
                yr[key][x] += tl[key][x]


def _mh(rows):
    num = 0.0
    den = 0.0
    vn = 0.0
    for r in rows:
        t = float(r[1]) + float(r[3])
        if t <= 0.0 or float(r[1]) <= 0.0 or float(r[3]) <= 0.0:
            continue
        num += float(r[0]) * float(r[3]) / t
        den += float(r[2]) * float(r[1]) / t
        vn += (float(r[0]) + float(r[2])) * float(r[1]) * float(r[3]) / (t * t)
    if num <= 0.0 or den <= 0.0:
        return [0.0, INF]
    return [num / den, vn / (num * den)]


def _gsum(t, ix, g):
    v = float(t[ix * month.NG + g])
    if g == 3:
        v += float(t[ix * month.NG + 4])
    return v


def t2s_dgq(kit, p, yr, label, as_check=True):
    miss_g = 0
    txt = ""
    for row in R74_ROWS:
        strata = []
        for a in range(65, month.AGES):
            ix = a * 2 + int(row[1])
            strata.append([_gsum(yr["d_g"], ix, int(row[2])), _gsum(yr["x_g"], ix, int(row[2])), _gsum(yr["d_g"], ix, int(row[3])), _gsum(yr["x_g"], ix, int(row[3]))])
        mh = _mh(strata)
        mgv = month._lc(p, "death_multiplier")
        l = math.log(float(mgv[int(row[2])]) / float(mgv[int(row[3])]))
        lr = math.log(float(mh[0])) if float(mh[0]) > 0.0 else -INF
        band = Z_DGQ * math.sqrt(float(mh[1]))
        inside = band < INF and abs(lr - l) <= band
        miss_g += 0 if inside else 1
        txt += " %s model %.3f against the m_g in use %.3f ± %.3f in log %s (source %.2f, beside);" % (row[0], float(mh[0]), math.exp(l), band, "in" if inside else "OUT", float(row[4]))
    f = month._lc(p, "death_income_factor")
    miss_k = 0
    for o in M010_OBS:
        strata2 = []
        a0 = int(gd_round(float(o[2])))
        for a2 in range(a0 - 2, a0 + 3):
            ix2 = a2 * 2 + int(o[1])
            strata2.append([yr["d_k"][ix2 * 4 + 3], yr["x_k"][ix2 * 4 + 3], yr["d_k"][ix2 * 4], yr["x_k"][ix2 * 4]])
        mh2 = _mh(strata2)
        y = math.log(float(mh2[0])) / 1.5 if float(mh2[0]) > 0.0 else -INF
        band2 = Z_DGQ * math.sqrt(float(o[4]) * float(o[4]) + float(mh2[1]) / 2.25 + float(f["tau2"]))
        inside2 = band2 < INF and abs(y - float(o[3])) <= band2
        miss_k += 0 if inside2 else 1
        txt += " %s at %.1f: model y %.3f source %.3f ± %.3f %s;" % (o[0], float(o[2]), y, float(o[3]), band2, "in" if inside2 else "OUT")
    line = "T2s-dgq (%s; the grade rows a CODE CHECK, current-grade HR against the m_g in use, TO_E 13:50; the income rows against their sources) 14 comparisons at z %.3f: grade misses %d, income misses %d;%s" % (label, Z_DGQ, miss_g, miss_k, txt)
    if as_check:
        kit.check(miss_g + miss_k == 0, line)
    else:
        print("REPORT " + line, flush=True)
    return [miss_g == 0, miss_k == 0]


def t2s_qk(kit, p, yr, label, persons_line=None):
    # Why persons_line from outside: the persons layer's spread is a REPORT on a people.create start (GDScript only); the check does
    # not read it
    qm = p.tr_margins["t22_q_means"]
    pts = ""
    for k in range(4):
        pts += " %.3f" % ((qm[k] / qm[4 + k]) / (qm[0] / qm[4]))
    per = persons_line if persons_line is not None else " (not read: the persons layer's start is GDScript's)"
    strata = []
    li = 0.0
    lw = 0.0
    for ix in range(month.AGES * 2):
        strata.append([yr["d_k"][ix * 4 + 3], yr["x_k"][ix * 4 + 3], yr["d_k"][ix * 4], yr["x_k"][ix * 4]])
        t = float(yr["x_k"][ix * 4 + 3]) + float(yr["x_k"][ix * 4])
        wi = float(yr["d_k"][ix * 4]) * float(yr["x_k"][ix * 4 + 3]) / t if t > 0.0 else 0.0
        li += wi * math.log(month.lc_income_factor(p, ix // 2, 3))
        lw += wi
    mh = _mh(strata)
    lm = math.log(float(mh[0]))
    lin = li / lw
    print("REPORT T2s-qk (%s) each quartile's mean equivalized income ÷ the top's (top .. bottom): the points%s, the persons layer%s; the bottom ÷ top death ratio %.4f (log %.4f) against the input's MH-weighted I_3 %.4f (log %.4f)" % (label, pts, per, float(mh[0]), lm, math.exp(lin), lin), flush=True)
    kit.check(lm >= lin * 2.0 / 3.0, "T2s-qk (%s; the stop rule, TO_E 22:04; RE-DECLARED on MH weights after the stop, 23:06; the stop stands until M026) the model's log bottom ÷ top ratio %.4f at least two thirds of the input's %.4f" % (label, lm, lin))
    return lm, lin
