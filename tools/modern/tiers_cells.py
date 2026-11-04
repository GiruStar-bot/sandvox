"""T1's units under each sizing of ISS_TIERED_POPULATION.md §11.1a, from tiers_cells.gd's dump:
  python3 -I tools/modern/tiers_cells.py <cells json>"""
import json, sys, math, collections
d = json.load(open(sys.argv[1]))
raw = {tuple(int(x) for x in k.split("|")): v for k, v in d["cells"].items()}
# adults from 20: band 3 (15-19) all to class 6 ("none")
cells = collections.Counter()
for (c,b,s,k,t,e), n in raw.items():
    cells[(c,b,s,6 if b <= 3 else k,t,e)] += n
cls = collections.Counter()
for key, n in cells.items(): cls[key[3]] += n
adults = sum(n for k, n in cls.items() if k != 6)
print("adults 20+ %d, persons %d, class counts %s" % (adults, sum(cls.values()), dict(sorted(cls.items()))))
def units(lad, lk, rk):
    agg = collections.Counter()
    for (c,b,s,k,t,e), n in cells.items():
        agg[(("L", k) + lk(c,b,s,k,t,e)) if k <= 3 else (("R",) + rk(c,b,s,k,t,e))] += n
    by = collections.Counter()
    for key, n in agg.items():
        if n <= 0: continue
        by["L%d" % key[1] if key[0] == "L" else "rest"] += math.ceil(n / lad[key[1]]) if key[0] == "L" else 1
    return sum(by.values()), dict(sorted(by.items()))
full = lambda c,b,s,k,t,e: (c,b,s,t,e)
pbs = lambda c,b,s,k,t,e: (c,b,s)
rest_full = lambda c,b,s,k,t,e: (c,b,s,k,t,e)
rest_dec = lambda c,b,s,k,t,e: (c,b,s,4 if k in (4,5) else k,t,e if b >= 3 else 0)
rest_dec20 = lambda c,b,s,k,t,e: (c,b,s,4 if k in (4,5) else k,t,e if b >= 4 else 0)
for name, a in [
 ("A full key, 10/10/100/1,000", ([10,10,100,1000], full, rest_full)),
 ("B the declared coarsening (two lowest classes merged; employment dropped under 15), ladder at the full key", ([10,10,100,1000], full, rest_dec)),
 ("C B, employment dropped under 20", ([10,10,100,1000], full, rest_dec20)),
 ("D C + ladder keyed pref x band x sex, 10/10/100/1,000", ([10,10,100,1000], pbs, rest_dec20)),
 ("E C + ladder keyed pref x band x sex, 10/30/100/3,000", ([10,30,100,3000], pbs, rest_dec20)),
 ("F C + ladder keyed pref x band x sex, 30/30/100/3,000", ([30,30,100,3000], pbs, rest_dec20)),
 ("G C + ladder keyed pref x band x sex x type, 10/30/100/3,000", ([10,30,100,3000], lambda c,b,s,k,t,e:(c,b,s,t), rest_dec20)),
]:
    tot, by = units(*a)
    print("%-100s %7d %s" % (name, tot, by))
agg = collections.Counter()
for (c,b,s,k,t,e), n in cells.items():
    if k > 3: agg[rest_dec20(c,b,s,k,t,e)] += n
sz = sorted(agg.values())
print("rest cells (C)", len(sz), "median", sz[len(sz)//2], "under 100:", sum(1 for x in sz if x < 100), "mean %.0f" % (sum(sz)/len(sz)))
