"""The start's own-flow rule for the storable food goods (the PM's rulings on TO_PM 126 (a) and on M038b; math-reports e7673fa7, 620e8168).
The start state is made consistent with the model's own month-0 flows, not with published flows that the model's other inputs do not
reproduce (D):
- a private import good's in-transit cargo (soybeans, vegetables): food manufacturing's bid at capacity (capacity x coefficient x
  domestic share) + the held final demand - the domestic crop / 12, never below 0. State-traded goods (wheat, the MA rice) keep their
  published flows: the state imports to cover the gap whatever the margin (国家貿易).
- rice's held final demand: the crop's monthly use, crop x (1 - reserve_share) / 12, less food manufacturing's bid at capacity. The
  trading houses import no rice for the market (the MA rice goes to the state's stock), so the crop is all its market has.
- wheat's, soybeans' and vegetables' held final demand: (the crop x (1 - reserve_share) + the year's imports) / 12, less food
  manufacturing's bid (wheat's imports are the state's in transit x 12; soybeans' and vegetables' are the published year, imports_t_yr).
- the start inventory of each crop: the last harvest is the model's own crop (area x yield), sold over the node's months after the
  reserve, plus the farmers' reserve.
  python3 -I tools/modern/start_flows.py            (from the repository root; rewrites trading_house_jpn.json, final_demand_jpn.json and start_inventory_jpn.json)
Why not the published flows (the first form): with the purge's in-window prices, the published soybean imports ran 9% above the model's
need (the surplus cut the next orders and the market was short a lead month later), and rice's final demand, backed out of the old
crop's split, took 5.1% more than the crop held before the harvest (C1: food fill 0.951 in months 9-11)."""
import json, os

DM = os.path.join(os.getcwd(), "data/modern/econ")


def load(f):
    return json.load(open(os.path.join(DM, f), encoding="utf-8"))


def save(f, d):
    open(os.path.join(DM, f), "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1, separators=(",", ": ")))


def main():
    th = load("trading_house_jpn.json")
    fm = load("food_manufacturing_jpn.json")
    fdd = load("final_demand_jpn.json")
    fd = fdd["monthly"]
    cf = load("crop_farming_jpn.json")["crops"]
    cap = float(fm["stocks"]["capacity_bn_jpy_month"])

    def bid(c):
        inp = fm["inputs"].get(c, {})
        return cap * float(inp.get("coef", 0.0)) * float(inp.get("domestic_share", 1.0))

    def crop(c):
        return float(cf[c]["area_ha"]) * float(cf[c]["yield_t_ha"]) if c in cf else 0.0

    r = cf["rice"]
    use = crop("rice") * (1.0 - float(r["reserve_share"])) / 12.0
    fd["rice"]["value"] = round(use - bid("rice"), 3)
    fd["rice"]["label"] = "D"
    fd["rice"]["source"] = ("D: the start rule from the model's own flows (the PM's ruling on M038b, math-reports 620e8168): the crop's monthly use, "
                            "crop %.0f t (crop_farming_jpn.json: 令和6年産 主食用, MAFF published 2024-12-10) x (1 - reserve_share %.2f, T: crop_farming_jpn.json, "
                            "set in 1d15aa4f) / 12 = %.0f t, less food manufacturing's bid at capacity %.1f bn (%.0f t); tools/modern/start_flows.py. "
                            "It replaces the old crop's split (0.48528) carried onto the new crop" % (crop("rice"), float(r["reserve_share"]), use, cap, bid("rice")))
    print("rice final demand %.0f t/month (use %.0f - bid %.0f)" % (fd["rice"]["value"], use, bid("rice")))
    w = cf["wheat"]
    imp = 12.0 * float(th["goods"]["wheat"]["start_in_transit_t"])
    fd["wheat"]["value"] = round((crop("wheat") * (1.0 - float(w["reserve_share"])) + imp) / 12.0 - bid("wheat"), 3)
    fd["wheat"]["label"] = "D"
    fd["wheat"]["source"] = ("D: the start rule from the model's own flows (the PM, TO_E 21:11 item 2): (the crop %.0f t (crop_farming_jpn.json: 令和6年産, MAFF "
                             "published 2024-11-26) x (1 - reserve_share %.2f, T) + the state's imports %.0f t/yr (trading_house_jpn.json's wheat in transit x 12: "
                             "MAFF 食料需給表 令和5年度, published 2024-08-08)) / 12, less food manufacturing's bid at capacity (%.0f t); "
                             "tools/modern/start_flows.py. The 1.006 Mt it replaces matched no release (R96e: NF)" % (crop("wheat"), float(w["reserve_share"]), imp, bid("wheat")))
    print("wheat final demand %.0f t/month" % fd["wheat"]["value"])
    for c, crop_ed, imp_ed, was in (("soybeans", "令和5年産, MAFF published 2024-04-10", "財務省 貿易統計 2023 確定, published 2024-11-13",
                                     "The 3.3 Mt it replaces matched no release (R96e)"),
                                    ("vegetables", "令和5年産 出荷量, MAFF published 2024-12-23", "MAFF 食料需給表 令和5年度 野菜 輸入量, published 2024-08-08; R96i",
                                     "It replaces (11.0 + 2.7 Mt) / 12 less a bid at the pre-purge coefficient (R96i: imports 2.777 Mt)")):
        s_imp = float(th["goods"][c]["imports_t_yr"])
        r_c = float(cf[c]["reserve_share"])
        fd[c]["value"] = round((crop(c) * (1.0 - r_c) + s_imp) / 12.0 - bid(c), 3)
        fd[c]["label"] = "D"
        fd[c]["source"] = ("D: the start rule from the model's own flows (the PM, TO_E 21:11 item 2): (the crop %.0f t (crop_farming_jpn.json: %s) x "
                           "(1 - reserve_share %.2f, T) + the year's imports %.0f t (trading_house_jpn.json's imports_t_yr: %s)) / 12, less food "
                           "manufacturing's bid at capacity (%.0f t); tools/modern/start_flows.py. %s" % (crop(c), crop_ed, r_c, s_imp, imp_ed, bid(c), was))
        print("%s final demand %.0f t/month" % (c, fd[c]["value"]))
    inv_doc = load("start_inventory_jpn.json")
    inv = inv_doc["inventory"]
    for c, months in (("rice", 9), ("wheat", 6), ("soybeans", 10), ("vegetables", 9)):
        last = crop(c)
        r_share = float(cf[c].get("reserve_share", 0.0))
        inv[c]["last_harvest"] = round(last, 3)
        inv[c]["value"] = round(last * (1.0 - r_share) * months / 12.0 + r_share * last, 3)
        inv[c]["label"] = "D"
        inv[c]["source"] = ("D: the start rule from the model's own crop (the PM, TO_E 21:11 items 1(b), 2): the last harvest = crop_farming_jpn.json's area x "
                            "yield (%.0f t, its in-window edition), %d of 12 months still to sell (the node's months, T) after the reserve, plus the farmers' "
                            "reserve (reserve_share %.2f x the last harvest, ISS_AUDIT.md §8.2 item 4); tools/modern/start_flows.py" % (last, months, r_share))
        print("%s start inventory %.0f t (last harvest %.0f)" % (c, inv[c]["value"], last))
    save("start_inventory_jpn.json", inv_doc)
    for c, g in th["goods"].items():
        if g.get("state_trading") or g.get("to_state_stock") or not g.get("start_in_transit_t"):
            continue
        final = float(fd.get(c, {}).get("value", 0.0))
        need = max(0.0, bid(c) + final - crop(c) / 12.0)
        if int(g.get("lead_months", 1)) != 1:
            raise SystemExit("%s: lead_months %s; the rule fills one month's arrival" % (c, g.get("lead_months")))
        g["start_in_transit_t"] = round(need, 3)
        g["start_in_transit_source"] = ("D: the model's own month-0 import need (the start rule; the PM's ruling on TO_PM 126): food manufacturing's bid at "
                                        "capacity %.1f bn (%.0f t) + the held final demand (%.0f t) - the crop / 12 (%.0f t); tools/modern/start_flows.py. "
                                        "It replaces the published import flow, which ran above this need (M038)" % (cap, bid(c), final, crop(c) / 12.0))
        print("%s start in transit %.0f t (bid %.0f + final %.0f - crop / 12 %.0f)" % (c, need, bid(c), final, crop(c) / 12.0))
    save("trading_house_jpn.json", th)
    save("final_demand_jpn.json", fdd)


if __name__ == "__main__":
    main()
