# people.create's tiers start as at cd165891 (people.gd 447-460, 506-519; modern_status.gd _init_entity's cohort and qx), up to and
# including TR.build_start
from core import detmath
from core.gd import minf
import country
from tiers.start import build, load
from tiers.start.p import PArr, P



def status_cohort_qx(key, year):
    # modern_status.gd _init_entity: the cohort from the single-age table in persons, the qx from the file's life table
    d = load.load_json(country.load(key).path("status"))
    co = PArr("f64")
    co.resize(P.AGES * P.SEXES)
    ages = d.get("cohort", {}).get("ages", [])
    unit = float(d.get("cohort", {}).get("unit_persons", 1.0))
    for a in ages:
        age = min(int(a["age"]), P.AGES - 1)
        co[age * P.SEXES] += float(a["male"]) * unit
        co[age * P.SEXES + 1] += float(a["female"]) * unit
    q = PArr("f64")
    q.resize(P.AGES * P.SEXES)
    lt = d.get("life_table", {})
    if "qx_male" in lt and "qx_female" in lt:
        for age in range(P.AGES):
            q[age * P.SEXES] = float(lt["qx_male"][min(age, len(lt["qx_male"]) - 1)])
            q[age * P.SEXES + 1] = float(lt["qx_female"][min(age, len(lt["qx_female"]) - 1)])
        return co, q
    vals = d.get("indicators", {})
    deaths_pub = float(vals.get("deaths", {}).get("value", 0.0))
    shape = PArr("f64")
    shape.resize(P.AGES * P.SEXES)
    tot = 0.0
    for age in range(P.AGES):
        for s in range(P.SEXES):
            g = 0.00008 * detmath.exp(0.095 * float(age)) * (1.0 if s == 0 else 0.6)
            g = minf(0.6, g + (0.0018 if age == 0 else 0.0))
            shape[age * P.SEXES + s] = g
            tot += g * co[age * P.SEXES + s]
    scale = deaths_pub / tot if tot > 0.0 and deaths_pub > 0.0 else 1.0
    for i in range(P.AGES * P.SEXES):
        q[i] = minf(0.95, shape[i] * scale)
    return co, q


def inputs(key="JPN", seed=1, year=2024, status_year=2024):
    # The people object as _create_tiers hands it to TR.build_start, and the prefectures table
    c = country.load(key)
    prefectures = load.load_json(c.path("regions"))["prefectures"]
    p = P()
    p.tiers = True
    p.state = key
    p.spec = load.load_json(c.path("people_spec"))
    cm = load.load_json(c.path("commodities"))
    p.food_elasticity = float(cm["commodities"]["food_products"]["demand_elasticity"])
    p.seed_v = seed
    # Why an instance value over people.gd's constant: the pension age is the country's (FRAME_PLAN §3, row F-mf)
    p.PENSION_AGE = int(c.constants["pension_age"])
    p.base_year = year
    p.cohort, p.qx = status_cohort_qx(key, status_year)
    p.pref_codes = sorted(prefectures.keys())
    p.tr_spec = load.load_json(c.path("tiers_spec"))
    p.hh_spec = load.load_json(c.path("households_spec"))
    for code in p.pref_codes:
        p.pref_pop[int(code)] = float(prefectures[code]["pop_thousand"]) * 1000.0
    return p, prefectures


def create(key="JPN", seed=1, year=2024):
    p, prefectures = inputs(key, seed, year)
    build.build_start(p, prefectures)
    for i in range(p.n):
        p.weight[i] = 1.0
    return p




def inputs_2025(key="JPN", seed=1):
    # Step (c) (START_PORT_PLAN §4): the start at 2025-01 on modern's in-window data, with rule (D)'s table in place of the status
    # cohort and its prefecture totals in place of the prefectures' pop_thousand. Why the qx from the status file still: rule (D)
    # ages the counts, and the start's own deaths read the life table the households spec carries (令和5年, R96h), as at cd165891
    p, prefectures = inputs(key, seed, 2025, status_year=2024)
    d = load.load_json(country.load(key).path("start_2025"))
    co = PArr("f64")
    co.resize(P.AGES * P.SEXES)
    for a in d["ages"]:
        age = min(int(a["age"]), P.AGES - 1)
        co[age * P.SEXES] += float(a["male"])
        co[age * P.SEXES + 1] += float(a["female"])
    p.cohort = co
    for code in prefectures:
        prefectures[code]["pop_thousand"] = float(d["prefectures"][code]["pop"]) / 1000.0
        prefectures[code]["pop_persons"] = int(d["prefectures"][code]["pop"])
    p.pref_pop = {}
    for code in p.pref_codes:
        p.pref_pop[int(code)] = float(prefectures[code]["pop_persons"])
    return p, prefectures
