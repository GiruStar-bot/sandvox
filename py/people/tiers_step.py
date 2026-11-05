# Section c8 of people.step (people.gd 1305-1307): TR.step on the persons' object, through the ported tiers month (py/tiers/month.py,
# P2 at parity). Why a copy into month.St and back, not the month on P: St holds tr_points as typed arrays and the month is written
# on St; the copy is exact (each value keeps its kind), and the month's parity rows already cover St
from tiers import month as tmonth
from tiers import state
from tiers.start.p import from_tree, to_tree


def sec_c8(p, ctx, env):
    if p.tiers:
        tree = {k: to_tree(getattr(p, k)) for k in list(vars(p)) if k.startswith("tr_") and k != "tr_margins"}
        for k in state.SAVE_SCALARS:
            tree[k] = getattr(p, k)
        s = tmonth.St(tree)
        tmonth.step(s)
        for k in s.fields():
            setattr(p, k, from_tree(s.field(k)))
        # Why every key St wrote and not "t22" alone: the month also keeps t22_q_means in tr_margins (tiers.gd 6563)
        for k, v in s.tr_margins.items():
            p.tr_margins[k] = from_tree(v)
    p.month += 1
