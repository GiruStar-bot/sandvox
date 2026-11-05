# Row S0-m's first half (START_PORT_PLAN §2): the Python start written as oracle_dump.gd writes m00 (every tr_* field but
# tr_margins, hh_spec and the scalars, as a typed tree), so run_month.py can step the Python start with PY_RESUME=<dir>
#   START_DATA_ROOT=<cd165891 tree> python py/tests/start_to_s0.py <dir>
import json
import os
import sys

import common  # noqa: F401  (puts py/ on the path)
from core import digest
from tiers import state
from tiers.start import create
from tiers.start.p import to_tree


def main():
    d = sys.argv[1]
    os.makedirs(d, exist_ok=True)
    p = create.create()
    names = sorted(k for k in vars(p) if k.startswith("tr_") and k != "tr_margins")
    files = [0]
    tree = {n: digest.enc(to_tree(getattr(p, n)), d, files) for n in names}
    for k in state.SAVE_SCALARS:
        tree[k] = digest.enc(to_tree(getattr(p, k)), d, files)
    with open(os.path.join(d, "state.json"), "w", encoding="utf-8") as f:
        json.dump(tree, f)
    dg, hs = state.digest({n: to_tree(getattr(p, n)) for n in names})
    with open(os.path.join(d, "..", os.path.basename(d) + ".sha.txt"), "w", encoding="utf-8") as f:
        f.write("".join("%s %s\n" % (n, hs[n]) for n in sorted(hs)))
    print("S0 written to %s, tiers digest %s" % (d, dg))


if __name__ == "__main__":
    main()
