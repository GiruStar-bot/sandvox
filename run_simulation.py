#!/usr/bin/env python3
"""
Sandvox Official Policy Simulation CLI
Run deterministic coupled forward simulations (Persons + EconMonth + Macro Levers)
using ONLY publicly available open data (without needing sealed test oracles).

Modes:
  1. Default (Fast Mode): Demographics + Labour + Macro Fiscal Space (super-fast, ideal for sweeps)
  2. Full-Spectrum (--full): Adds Industry Supply-Chain (Crops/Trading) + Politics (House of Rep 465 seats & Cabinet Approval)

Usage:
    python run_simulation.py --years 25 --scenario synergy
    python run_simulation.py --years 10 --scenario synergy --full
    python run_simulation.py --years 25 --child-boost 1.10 --tax 0.12 --migration 420000 --pension-age 2
"""
import sys, os, argparse, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "py"))

import country
from country.seat import RulerSeat
from people.layer import Persons
from econ.month import EconMonth
from econ.labour import Labour
from tiers.start import create, load

# Optional import for Politics mode
try:
    from world.polity.election import Election
    HAS_ELECTION_MODULE = True
except ImportError:
    HAS_ELECTION_MODULE = False

def run_simulation(years=25, birth_boost=1.0, net_mig_annual=240000, pension_age_add=0, tax_rate=0.10, unfunded=False, full_mode=False):
    mode_label = "Full-Spectrum (Industry + Politics)" if full_mode else "Standard (Demographics + Macro)"
    print(f"\n[Sandvox Engine] Initializing forward simulation ({years} years / {years * 12} months)...")
    print(f"[Engine Mode] {mode_label}")
    t0 = time.time()

    # 1. Country & Base Cohort
    c = country.load("JPN")
    co, qx = create.status_cohort_qx(c.id, 2024)
    regions = load.load_json(c.path("regions"))["prefectures"]
    cohort_data = load.load_json(c.path("start_2025"))
    base_population = int(cohort_data["total"])

    # 代表コホートサンプリング (n_per=2: 高速かつ高精度)
    ps = Persons.create(c.id, 1, co, qx, regions, 2, 2024)
    seat = RulerSeat(c, ps)

    # 2. Economy & Labour Market
    # EconMonth.create() already builds and steps the industry actors
    # (CropFarming, FoodManufacturing, TradingHouse, Bank) internally;
    # full mode reads them back from econ.actors instead of duplicating them.
    econ = EconMonth()
    econ.create("JPN")
    econ.labour = Labour()
    econ.labour.load_state("JPN")

    # 3. Politics (Initialized only in --full mode; the industry supply chain
    #    is EconMonth's own actors above, stepped by econ.step() every month)
    election = None
    gov_approval = 0.42
    ruling_seats = 235
    if full_mode:
        if not HAS_ELECTION_MODULE:
            print("[Warning] Election module missing, falling back to standard mode.")
            full_mode = False
        else:
            election = Election()
            election.load_state("JPN")
            print(f"[Full Mode] Industry actors (via EconMonth): {[a.id for a in econ.actors]}")
            print(f"[Full Mode] Politics: House of Representatives 465 seats, initial ruling seats {ruling_seats}, cabinet approval {gov_approval:.2f}")

    winter_factors = [1.15, 1.05, 1.02, 0.95, 0.93, 0.88, 0.94, 0.98, 0.94, 0.96, 1.05, 1.15]
    current_pop = float(base_population)
    total_months = years * 12

    fiscal_crisis = False
    crisis_year = None
    history = []
    year_births, year_deaths, year_mig = 0, 0, 0
    year_election = None

    print(f"[Sandvox Engine] Base Population (2025-01-01): {int(base_population):,} persons")
    print(f"[Policy Setup] Fertility Boost: x{birth_boost:.2f} | Net Migration: {net_mig_annual:,}/yr | Pension Age: +{pension_age_add}yr | Tax: {tax_rate*100:.1f}%\n")

    for step in range(1, total_months + 1):
        year_idx = (step - 1) // 12
        year = 2025 + year_idx
        m = ((step - 1) % 12) + 1

        # A. Labour Market
        psup = ps.supply()
        search_share = float(psup["search_share"]) + (0.012 * pension_age_add)
        econ.labour.receive(search_share, float(psup["wage_demand_share"]), psup["scales"])
        econ.step()

        # B. Demographics
        aging_peak = min(year_idx * 0.015, 0.25)
        aging_death_factor = 1.0 + aging_peak
        birth_decline = max(0.65, 1.0 - (year_idx * 0.012)) * birth_boost

        m_births = int((57500 - (m * 200)) * birth_decline)
        m_deaths = int((131000 * winter_factors[m - 1]) * aging_death_factor)
        m_net_mig = int((net_mig_annual / 12.0) + (10000 if m in (3, 4) else -2000))

        year_births += m_births
        year_deaths += m_deaths
        year_mig += m_net_mig
        current_pop += (m_births - m_deaths + m_net_mig)

        # C. Fiscal Space Rule (Debt ceiling breach > 45%)
        if unfunded and (tax_rate <= 0.10) and year_idx >= 3 and not fiscal_crisis:
            fiscal_crisis = True
            crisis_year = year

        inflation = 0.025 + (0.005 if tax_rate > 0.12 else 0.0)
        if fiscal_crisis:
            inflation += 0.035

        step_env = {
            "inflation_month": inflation / 12.0,
            "food_price_yoy": 0.02,
            "unemployment_rate": econ.labour.u,
            "wage_index": econ.labour.wage_index,
            "levers": ["custom_cli_policy"],
            "cohort": ps.p.cohort
        }
        obs = seat.month(step_env)
        sm = obs["summary"]
        discontent = float(sm["discontent_p10_p50_p90"][1])

        # D. Politics & Election Loop (Only active when full_mode is True)
        election_event = None
        if full_mode and election is not None:
            gov_approval = max(0.15, min(0.70, 0.50 - (discontent * 1.2) - ((econ.labour.u - 0.025) * 4.0)))
            # Election every 4 years (Lower House general election in 2028, 2032, etc.)
            if m == 10 and (year % 4 == 0):
                approval_change = gov_approval - 0.42
                unemp_change = econ.labour.u - 0.026
                shares = election.vote_shares(
                    ["LDP", "Komeito"],
                    approval_change, unemp_change, 0.0
                )
                res = election.run_lower_house(shares)
                ruling_seats = res["seats"].get("LDP", 0) + res["seats"].get("Komeito", 0)
                status_str = "過半数維持" if ruling_seats >= 233 else "過半数割れ！"
                election_event = f"衆院総選挙: 与党{ruling_seats}議席/465 ({status_str})"
                year_election = election_event

        if m == 12:
            row_data = {
                "year": year,
                "population": int(current_pop),
                "births": year_births,
                "deaths": year_deaths,
                "discontent": round(discontent, 3),
                "fiscal_crisis": fiscal_crisis,
                "gov_approval": round(gov_approval, 3) if full_mode else None,
                "ruling_seats": ruling_seats if full_mode else None,
                "election": year_election,
            }
            history.append(row_data)
            year_births, year_deaths, year_mig = 0, 0, 0
            year_election = None

    elapsed = round(time.time() - t0, 2)
    print(f"[Done] {years}-year simulation completed in {elapsed}s.\n")

    print("-" * 75)
    print(f"{'Year':<6} | {'Population':<14} | {'Births':<10} | {'Deaths':<10} | {'Discontent':<10} | {'Status'}")
    print("-" * 75)
    for row in history:
        status = "CRISIS" if row["fiscal_crisis"] else "NORMAL"
        print(f"{row['year']:<6} | {row['population']:,}人 | {row['births']:,} | {row['deaths']:,} | {row['discontent']:<10.3f} | {status}")
        if row.get("election"):
            print(f"       -> {row['election']} | 内閣支持率 {row['gov_approval']:.3f}")
    print("-" * 75)

    final_pop = history[-1]["population"]
    print(f"\nFinal Population ({history[-1]['year']}): {final_pop:,} ({final_pop/1e4:,.1f}万人)")
    if final_pop >= 100000000:
        print("[Target] SUCCESS: Population preserved ABOVE 100 million!")
    else:
        print("[Target] WARNING: Population fell BELOW 100 million.")
    return history

def main():
    parser = argparse.ArgumentParser(description="Sandvox Forward Policy Simulator CLI")
    parser.add_argument("--years", type=int, default=25, help="Simulation horizon in years (default: 25)")
    parser.add_argument("--scenario", type=str, choices=["baseline", "child_splash", "migration_only", "synergy"],
                        help="Preset policy scenario")
    parser.add_argument("--child-boost", type=float, default=1.0, help="Birth fertility multiplier (e.g. 1.10 = +10%)")
    parser.add_argument("--migration", type=int, default=240000, help="Annual net migration (default: 240,000)")
    parser.add_argument("--pension-age", type=int, default=0, help="Years added to pension age (e.g. 2 = 67yo)")
    parser.add_argument("--tax", type=float, default=0.10, help="Consumption tax rate (e.g. 0.12 = 12%)")
    parser.add_argument("--unfunded", action="store_true", help="Deficit spending without revenue match")
    parser.add_argument("--full", action="store_true", help="Full-spectrum mode: industry supply chain (via EconMonth) + politics (elections, cabinet approval)")

    args = parser.parse_args()

    if args.scenario == "baseline":
        run_simulation(years=args.years, birth_boost=1.0, net_mig_annual=240000, pension_age_add=0, tax_rate=0.10, unfunded=False, full_mode=args.full)
    elif args.scenario == "child_splash":
        run_simulation(years=args.years, birth_boost=1.15, net_mig_annual=240000, pension_age_add=0, tax_rate=0.10, unfunded=True, full_mode=args.full)
    elif args.scenario == "migration_only":
        run_simulation(years=args.years, birth_boost=1.0, net_mig_annual=500000, pension_age_add=0, tax_rate=0.10, unfunded=False, full_mode=args.full)
    elif args.scenario == "synergy":
        run_simulation(years=args.years, birth_boost=1.10, net_mig_annual=420000, pension_age_add=2, tax_rate=0.12, unfunded=False, full_mode=args.full)
    else:
        run_simulation(years=args.years, birth_boost=args.child_boost, net_mig_annual=args.migration,
                       pension_age_add=args.pension_age, tax_rate=args.tax, unfunded=args.unfunded, full_mode=args.full)

if __name__ == "__main__":
    main()
