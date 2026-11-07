# Roadmap P3: static indicators made dynamic (energy first), plus a wiring
# fix found on the way.
#   python py/tests/test_live_indicators.py
# - GHG emissions / net emissions / energy self-sufficiency are now derived
#   from the electricity mix in Status identities: at the initial mix they
#   reproduce the sourced 2024 values exactly, and they follow the mix when
#   the P1 energy levers move it.
# - health_fee_schedule was wired in name only: its response form added
#   the raw rate (-0.02 bn) to medical expenditure. The share_of_spending
#   form now applies the declared one-for-one share, so synergy's health
#   lever really cuts expenditure by 2% (its Debt/GDP improves ~3pt;
#   demographics are untouched - verified by ablation in the PR notes).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Kit  # noqa: E402  (puts py/ on the path)

from world.status import Status  # noqa: E402


def fresh():
    st = Status()
    err = st.load(2024, ["JPN"])
    assert not err, err
    return st


def apply(st, lid, val):
    lead = int(st.levers["JPN"]["levers"][lid]["lead_days"])
    st.set_lever("JPN", lid, val)
    for _ in range(lead + 30):
        st.step()


def main():
    k = Kit("py/tests/test_live_indicators.py")

    st = fresh()
    for _ in range(400):
        st.step()
    iv = st.ind["JPN"]
    k.check(abs(iv["ghg_emissions"] - 1135.46) < 1e-6 and abs(iv["ghg_net"] - 1085.28) < 1e-6
            and abs(iv["energy_self_sufficiency"] - 0.13) < 1e-9,
            "P3 derived energy indicators rest exactly at the sourced 2024 values")

    st = fresh()
    apply(st, "energy_mix_target_renewables", 0.40)
    iv = st.ind["JPN"]
    k.check(abs(iv["ghg_emissions"] - 1013.3) < 1.5 and abs(iv["energy_self_sufficiency"] - 0.211) < 0.002,
            "P3 renewables 0.40: GHG falls to %.1f Mt and self-sufficiency rises to %.3f"
            % (iv["ghg_emissions"], iv["energy_self_sufficiency"]))
    k.check(abs(iv["ghg_net"] - (iv["ghg_emissions"] - 50.18)) < 1.5,
            "P3 net emissions keep the initial 50.18 Mt sink (net %.1f)" % iv["ghg_net"])

    st = fresh()
    apply(st, "nuclear_restart", 3.0)
    iv = st.ind["JPN"]
    k.check(iv["ghg_emissions"] < 1135.46 and abs(iv["energy_self_sufficiency"] - 0.1381) < 0.001,
            "P3 nuclear +3: GHG falls to %.1f Mt, self-sufficiency %.4f"
            % (iv["ghg_emissions"], iv["energy_self_sufficiency"]))

    def run_fee(fee):
        st = fresh()
        if fee is not None:
            st.set_lever("JPN", "health_fee_schedule", fee)
        for _ in range(800):
            st.step()
        return st.ind["JPN"]["health_expenditure"]

    a, b = run_fee(None), run_fee(-0.02)
    k.check(abs(b / a - 0.98) < 0.001,
            "P3 health fee -2%% now moves medical expenditure one-for-one (%.1f -> %.1f bn)" % (a, b))

    k.finish()


if __name__ == "__main__":
    main()
