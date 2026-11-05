# Sections c2, c3, c6 and c7 of people.step (people.gd 1253-1304 at cd165891), PROVISIONAL: the REL builder's S1-S4 replace this
# file (PERSONS_PORT_PLAN §7). It calls the modules already at parity on modern (act, rel, grp: REL 459/459), in step's order, so
# the whole month (Q-1) can run before S1-S4 land. Why not wait: the persons port is the critical path (D482)
from core.gd import fdiv, maxf
from core.gdsort import sort_custom
from people import act, grp, loop_c, rel


def _locals(p, ctx, env):
    # step's locals of c1 when a test starts from a dump that does not hold them: the empty dicts and the env's plain reads
    for k in ("counts", "dec_counts", "ref_counts"):
        ctx.setdefault(k, {})
    ctx.setdefault("ur", float(env.get("unemployment_rate", float(p.spec["unemployment_rate_start"]["value"]))))
    ctx.setdefault("f", float(p.spec["job_finding_rate_month"]["value"]))
    ctx.setdefault("yoy_true", float(env.get("food_price_yoy", 0.0)))


def sec_c2(p, ctx, env):
    _locals(p, ctx, env)
    counts, dec_counts, ref_counts = ctx["counts"], ctx["dec_counts"], ctx["ref_counts"]
    for i in range(p.n):
        ch = act.choose(p, i, p.month)
        a = int(ch["action"])
        act.apply(p, i, a, p.month)
        if a == act.A_FOUND:
            grp.found_movement(p, i, counts)
        p.last_action[i] = a
        p._count_decision(dec_counts, a, int(ch["top_drive"]), str(ch["modulated_by"]), i)
        for r in ch["refused"]:
            rk = "%d|%s" % (int(r[0]), str(r[1]))
            ref_counts[rk] = int(ref_counts.get(rk, 0)) + 1
        if p.pid[i] in p.trace_pids:
            raise NotImplementedError("the decision trace (trace_pids non-empty) is S1's")


def sec_c3(p, ctx, env):
    _locals(p, ctx, env)
    counts = ctx["counts"]
    rel.interact(p, counts)
    rel.learn(p, {"food_price_yoy": ctx["yoy_true"], "unemployment_rate": ctx["ur"]}, counts)
    grp.step(p, counts)
    ur = ctx["ur"]
    ctx["s"] = loop_c._mean_finding(p, ctx["f"]) * ur / maxf(1e-6, 1.0 - ur)


def _ranks(p):
    # people.gd 1005
    by = {}
    for i in range(p.n):
        if p.pref[i] not in by:
            by[p.pref[i]] = []
        by[p.pref[i]].append(i)
    for code in by:
        idx = by[code]
        sort_custom(idx, lambda a, b: p.income[a] < p.income[b] if p.income[a] != p.income[b] else p.pid[a] < p.pid[b])
        tot = 0.0
        for i in idx:
            tot += p.weight[i]
        acc = 0.0
        for i in idx:
            acc += p.weight[i]
            p.rank[i] = fdiv(acc, tot)


def sec_c6(p, ctx, env):
    grp.refresh_weights(p)
    _ranks(p)


def sec_c7(p, ctx, env):
    for key in ctx["dec_counts"]:
        p.decisions.append(ctx["dec_counts"][key])
    for rk in ctx["ref_counts"]:
        parts = rk.split("|")
        p.refusals.append({"month": p.month, "action": act.ACTIONS[int(parts[0])], "why": parts[1],
                           "count": int(ctx["ref_counts"][rk])})
    for kind in ctx["counts"]:
        c = ctx["counts"][kind]
        p.events.append({"month": p.month, "kind": kind, "count": int(c["n"]), "weight": float(c["w"]),
                         "mean_move": float(c["move"]) / maxf(1.0, float(c["n"])), "why": str(c["why"])})
