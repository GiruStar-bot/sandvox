extends RefCounted
## The common actor specification (BLUEPRINT_v2 1; E-Phase 0): every computed actor, in every layer, is this shape. An actor owns stocks,
## reads the world state each month, computes its plan by stated rules (labelled S/D/T, never fitted), and writes outputs with a reason
## code. Goods, money and contracts are never mixed: each moves through its own ledger in the world state (world_state.gd), and the
## actor only posts offers, bids and payments; the ledgers close. Subclasses implement plan(), and may implement settle() (after the
## markets) and close_month().
## Every output is logged as [month, actor id, what, value, rule, reason] so the chronicle can say why a number moved (principle D).
const CANON = preload("res://sim/modern/canon.gd")
var id: String = ""
var kind: String = ""              # industry | market | finance | household_group | government | prefecture | organ | foreign
var jurisdiction: String = "JPN"   # JPN | prefecture code | a foreign entity key
var stocks: Dictionary = {}        # name -> float (capacity, inventory by commodity, money, debt, land, labour, ...)
var params: Dictionary = {}        # the rules' parameters with their labels: name -> {"value", "label", "source"}
var log: Array = []                # [month, id, what, value, rule, reason]


func setup(spec: Dictionary) -> void:
	id = String(spec["id"])
	kind = String(spec["kind"])
	jurisdiction = String(spec.get("jurisdiction", "JPN"))
	stocks = (spec.get("stocks", {}) as Dictionary).duplicate(true)
	params = (spec.get("params", {}) as Dictionary).duplicate(true)


func p(name: String) -> float:
	return float((params[name] as Dictionary)["value"])


func note(month: int, what: String, value: float, rule: String, reason: String) -> void:
	log.append([month, id, what, value, rule, reason])


## Step 2 of the month (BLUEPRINT_v2 1): read the world state, compute production, demand, offers and bids; post them to the world
func plan(_world: RefCounted, _month: int) -> void:
	pass


## Step 4-5: after the markets cleared, take what was traded, update own stocks and accounts
func settle(_world: RefCounted, _month: int) -> void:
	pass


## The month's fixed cost: the IO's (S), its wage part scaled by the labour market's wage index when one runs (world.env.wage_index;
## people off it is absent and the cost is the IO's). Why the wage part follows the index: labour owns the wage, and a maker pricing on
## its cost would otherwise price on the 2020 wage (V090: the cost-plus target 2.4% low at ten years)
func fixed_cost(world: RefCounted) -> float:
	var fixed: float = float(stocks.get("fixed_costs_bn_month", 0.0))
	if params.has("wage_share_of_fixed") and world.env.has("wage_index"):
		fixed *= 1.0 + p("wage_share_of_fixed") * (float(world.env["wage_index"]) - 1.0)
	return fixed


## Step 5b (E5): the month's fixed costs (wages, other inputs: S from the IO table) go out; when the cash would fall below the working
## floor the actor asks the bank for the shortfall plus the floor; what it cannot borrow it does not pay (the bank records the default)
func pay_fixed_and_finance(world: RefCounted, month: int, bank: RefCounted, monthly_revenue: float) -> void:
	var fixed: float = fixed_cost(world)
	if fixed <= 0.0:
		return
	var floor_: float = fixed * float(stocks.get("working_floor_months", 1.0))
	var cash: float = float(world.cash.get(id, 0.0))
	if cash - fixed < floor_ and bank != null:
		var got: float = bank.request_loan(world, month, id, floor_ + fixed - cash, monthly_revenue)
		note(month, "loan_request", floor_ + fixed - cash, "cash below the working floor (T: one month of fixed costs)", "got %.1f" % got)
	cash = float(world.cash.get(id, 0.0))
	var paid: float = clampf(cash, 0.0, fixed)
	if paid > 0.0:
		world.pay(id, "other_sectors_and_households", paid, "fixed costs of " + id)
	if paid < fixed:
		note(month, "arrears", fixed - paid, "cash short", "ARREARS")
		stocks["arrears"] = float(stocks.get("arrears", 0.0)) + fixed - paid


func to_dict() -> Dictionary:
	return {"id": id, "kind": kind, "jurisdiction": jurisdiction, "stocks": stocks.duplicate(true), "log": log.duplicate(true)}


func from_dict(d: Dictionary) -> void:
	stocks = (d["stocks"] as Dictionary).duplicate(true)
	log = (d.get("log", []) as Array).duplicate(true)
