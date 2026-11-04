extends RefCounted
## Representative persons of a state (ISS Phase 1; ISS_PHASE0_SURVEY.md 5). N persons per prefecture, each with a weight, drawn by keyed
## hashes from the 2024 cohort (age x sex), the prefecture populations and the shares in data/modern/people/<state>_people_2024.json.
## Three separate layers, each a struct of arrays so N can grow without a design change:
##   traits  (stable): ten traits in 0..1, loss aversion; drive weights (composed once a year from age and traits)
##   states  (change): attributes (household, education, employment, income, assets, debt, health, skill, rank), emotions (ten, 0..1,
##           each decaying toward the person's baseline), drive deficits (0..1), preferences, the dream (kind, importance, progress)
##   memory  (own view): the last K events with their valence, expectations Q (income, prices, job) learned at 0.3 with loss aversion
## Ownership (survey 2): the cohort owns births/deaths/ages (persons follow its hazards by keyed draw); the economy owns wages, prices and
## jobs (here the held unemployment rate and the wage tables stand in until Phase 5: persons RECEIVE them); persons own everything inner.
## Phase 4 (groups.gd): classes read from attributes vs groups joined, founded or left; start groups from published rates; movements
## emerge from discontented persons and their contacts, act (petitions) and dissolve; members feel the group and the group reads them.
## Phase 3 (relations.gd): contacts with trust, interactions that move both sides, help asked and given or refused, and beliefs about
## public facts learned from the register, from contacts (credibility x trust, delay, noise) or from one's own case; prices are felt as believed.
## Phase 2 (actions.gd): each month the person chooses one action by candidates -> feasibility -> score -> one keyed softmax draw, and
## the action changes only what the person owns; the payoff is learned from the month's change of drive pressure (q_act).
## Nothing inner is observable from outside the module except the weighted aggregates of summary(). Every draw is keyed(seed, tag, pid,
## month) so one seed repeats and seeds differ; no RandomNumberGenerator, no hash(). Every emotional move names its event and the trait that
## scaled it (the event log, bounded: aggregate rows per month plus full rows for the pinned sample).
const KEYED = preload("res://sim/earth_core/keyed.gd")
const DM = preload("res://sim/api/det_math.gd")
const CANON = preload("res://sim/modern/canon.gd")
const ACT = preload("res://sim/modern/people/actions.gd")
const REL = preload("res://sim/modern/people/relations.gd")
const GRP = preload("res://sim/modern/people/groups.gd")
const LAB = preload("res://sim/modern/econ/labour.gd")
const HH = preload("res://sim/modern/people/households.gd")
const LC = preload("res://sim/modern/people/life_course.gd")
const SV = preload("res://sim/modern/people/state_view.gd")
const TR = preload("res://sim/modern/people/tiers.gd")

const TRAITS := ["risk_tolerance", "patience", "sociability", "trust_in_others", "competitiveness", "cooperativeness", "authority_attitude", "openness", "fairness", "future_orientation"]
const EMOTIONS := ["joy", "sadness", "anger", "anxiety", "fear", "relief", "hope", "loneliness", "discontent", "trust"]
const DRIVES := ["survival_safety", "economic_security", "belonging", "recognition", "autonomy", "growth", "enjoyment", "family", "contribution", "change"]
const D_SURVIVAL := 0        # the indices of DRIVES
const D_SECURITY := 1
const D_BELONGING := 2
const D_RECOGNITION := 3
const D_AUTONOMY := 4
const D_GROWTH := 5
const D_ENJOYMENT := 6
const D_FAMILY := 7
const D_CONTRIBUTION := 8
const D_CHANGE := 9
const DREAMS := ["start_business", "have_family", "become_expert", "financial_freedom", "contribute_locally", "become_known", "stable_life", "change_society"]
const EMPLOYMENT := ["not_in_labour_force", "regular", "non_regular", "unemployed", "student", "retired"]
const F_REST := 1            # the bits of flags: what the person did this month (actions.apply sets them)
const F_SOCIALISED := 2
const F_SUPPORTED := 4
const F_MOVED := 8
const F_DREAM := 16
const F_JOINED := 32
const F_FOUNDED := 64
const EMP_NONE := 0          # the indices of EMPLOYMENT
const EMP_REGULAR := 1
const EMP_NONREGULAR := 2
const EMP_UNEMPLOYED := 3
const EMP_STUDENT := 4
const EMP_RETIRED := 5
const PENSION_AGE := 65       # the public pension by entitlement from this age with tiers on (§12.9 M1)
const HOUSEHOLD := ["single", "couple", "couple_children", "single_parent", "other"]
const HK_SINGLE := 0        # the indices of HOUSEHOLD: a person's household kind, and with households on its household's type
const HK_COUPLE := 1        # (households.TYPES, the same order; 5 is life_course.INSTITUTION)
const HK_COUPLE_CHILDREN := 2
const HK_SINGLE_PARENT := 3
const HK_OTHER := 4
const MALE := 0
const FEMALE := 1
const GRADE_GOOD := 0       # health: the grades 1-4 held as 0..3 (life_course.gd; households off uses 0..2)
const GRADE_FAIR := 1
const GRADE_POOR := 2
const GRADE_LIMITED := 3     # grade 4 without care need (4a, T2.2c)
const GRADE_CARE := 4        # grade 4 with care need (4b, T2.2c: the LTCI recipients)
const R_HEAD := 0           # the indices of life_course.ROLES
const R_PARTNER := 1
const R_CHILD := 2
const R_PARENT := 3
const R_OTHER := 4
const EDUCATION := ["high_school_or_less", "vocational_junior_college", "university_or_more"]
const NT := 10
const NE := 10
const ND := 10
const K_MEM := 8
const AGES := 101
const SEXES := 2

var spec: Dictionary = {}
var state: String = "JPN"
var seed_v: int = 1
var base_year: int = 2024
var n: int = 0
var month: int = 0
var price_index: float = 1.0
var pension: Dictionary = {"new": 1.0, "old": 1.0, "carry": 0.0, "jan": [], "jan_prev": [], "log": []}   # R68's indexation (M002 G1)
var wage_index: float = 1.0        # the economy's (received each month; the yearly pay follows it)
var food_plan_start: float = NAN   # the start's weighted food consumption plan (the scale's base)
var food_elasticity: float = 0.0   # the food products' demand elasticity (the economy's commodities.json: one source)
var error: String = ""
# attributes
var pid := PackedInt64Array()
var pref := PackedInt32Array()
var k_in_pref := PackedInt32Array()
var age := PackedInt32Array()
var sex := PackedInt32Array()
var weight := PackedFloat64Array()
var hh_kind := PackedInt32Array()
var hh_size := PackedFloat64Array()
var education := PackedInt32Array()
var employment := PackedInt32Array()
var health := PackedInt32Array()      # 0 good, 1 fair, 2 poor
var income := PackedFloat64Array()    # nominal, 万円 a month
var pay_factor := PackedFloat64Array()  # the job's own pay against the table (labour.gd writes it at a job change; 1 at a new job)
var assets := PackedFloat64Array()
var debt := PackedFloat64Array()
var skill := PackedFloat64Array()     # 0..100
var rank := PackedFloat64Array()      # weighted income rank within the prefecture, 0..1
# traits
var traits := PackedFloat64Array()    # n x NT
var lam := PackedFloat64Array()
var dw := PackedFloat64Array()        # drive weights n x ND
# states
var emo := PackedFloat64Array()       # n x NE
var emo_base := PackedFloat64Array()
var dd := PackedFloat64Array()        # drive deficits n x ND
var basket := PackedFloat64Array()    # n x 4: food, housing, leisure, other
var pref_leisure := PackedFloat64Array()
var pref_social := PackedFloat64Array()
var pol_interest := PackedFloat64Array()
var dream_kind := PackedInt32Array()  # -1 none
var dream_importance := PackedFloat64Array()
var dream_progress := PackedFloat64Array()
var dream_status := PackedInt32Array()   # 0 active, 1 achieved, 2 abandoned
var dream_blocked := PackedInt32Array()  # months without progress
# memory
var q_income := PackedFloat64Array()
var q_price := PackedFloat64Array()
var q_job := PackedFloat64Array()
var mem_month := PackedInt32Array()   # n x K_MEM
var mem_kind := PackedInt32Array()
var mem_val := PackedFloat64Array()
var mem_head := PackedInt32Array()
# groups (Phase 4): memberships per person, the groups themselves, their log
var member_of := PackedInt32Array()       # n x GRP.M, -1 empty
var union_cover := PackedInt32Array()     # 1 when the person's workplace has a union (groups.gd draw_cover)
var groups: Array = []                    # dictionaries (see groups.gd _new_group)
var group_influence: bool = true          # the members' convergence toward the group (off only in causal tests)
var contact_news: bool = true             # beliefs passed on by contacts (off only in causal tests)
var contact_renewal: bool = true          # the yearly refill of contacts (off only in causal tests)
var group_log: Array = []                 # {month, group, kind: founded|petition|wage_demand|dissolved, pref, members, why}
# relations and information (Phase 3): contacts in the sample, beliefs about public facts
var contact_idx := PackedInt32Array()     # n x REL.C, -1 empty
var contact_kind := PackedInt32Array()
var contact_trust := PackedFloat64Array()
var contact_last := PackedInt32Array()
var met := PackedInt32Array()
var belief := PackedFloat64Array()        # n x REL.NF
var belief_known := PackedInt32Array()
var belief_source := PackedInt32Array()   # 0 register, 1 contact, 2 own experience
var belief_month := PackedInt32Array()
# decisions (Phase 2): what the person owns of its action
var plan := PackedInt32Array()        # 0 thrift, 1 usual, 2 splurge (the month's consumption plan)
var search := PackedInt32Array()      # 0 none, 1 looking for a job, 2 looking to change
var flags := PackedInt32Array()       # the month's F_ bits below
var q_act := PackedFloat64Array()     # n x NA: the person's learned payoff of each action
var last_action := PackedInt32Array()
var pressure_prev := PackedFloat64Array()
var decisions: Array = []  # per month: {"month", "action", "count", "weight", "top_drives": {drive: count}, "modulated": {emotion: count}}
var refusals: Array = []   # per month: {"month", "action", "why", "count"}
# log
var events: Array = []     # per month: {"month", "kind", "count", "weight", "mean_move", "why"}
var trace_pids: Array = [] # the pinned sample (full rows)
var trace: Array = []      # [month, pid, kind, emotion, move, why]
var cohort := PackedFloat64Array()
var qx := PackedFloat64Array()
var pref_codes: Array = []
var pref_pop: Dictionary = {}   # prefecture code -> its published population (the weights are re-scaled to it every month)
# the tiered population (ISS_TIERED_POPULATION.md §12, T1): set before create; off allocates nothing, no key in the save or digest
var tiers: bool = false
var tier_k: int = 0                         # the points per bundle on average (P = tier_k x U); 0 takes the spec's k_points (T1s-g sets 4, 8, 16)
var tr_spec: Dictionary = {}
var tr_k: int = 4
var tr_units: int = 0                          # bundles
var tr_key := PackedInt32Array()           # per bundle: pref, band, sex, class, type, employment (tiers.KEY_STRIDE)
var tr_count := PackedInt64Array()         # per bundle: the persons it covers
var tr_age_counts := PackedInt64Array()    # per bundle: its single ages (tiers.AGE_SLOTS: a band's five, the 85+ band's 85..100)
var tr_never_married := PackedFloat64Array()
var tr_married_apart := PackedFloat64Array()     # §12.12 (6): each unit's married-but-living-apart share of its persons
var tr_tier_size := PackedInt32Array()     # per bundle: the ladder's unit size (0: one per cell)
var tr_residual := PackedFloat64Array()    # the fit's residuals (T1s-h)
var tr_margins: Dictionary = {}            # the start's integer targets of (0) and (1), built and read at the start only (T1s-l)
var tr_mix_off := PackedInt64Array()       # the mix of unit u is tr_mix_off[u] .. tr_mix_off[u + 1] - 1: (class, type, employment) codes and counts
var tr_mix_code := PackedInt32Array()
var tr_mix_n := PackedInt64Array()
var tr_pt_code := PackedInt32Array()       # each point's combination (class x 36 + type x 6 + employment)
var tr_indiv_code := PackedInt32Array()    # each individual's combination
var tr_pt_off := PackedInt64Array()        # the points of unit u are tr_pt_off[u] .. tr_pt_off[u + 1] - 1
var tr_pt_mass := PackedInt64Array()       # each point's integer mass (Σ over a unit = its count)
var tr_pt_age := PackedInt64Array()        # §14.2c (1): each point's mass at each single age of its unit (tiers.AGE_SLOTS a point)
var tr_hh_keys := PackedStringArray()      # the household-bundles' keys sorted: the index tr_hm_* and tr_cp_* read
var tr_hm_off := PackedInt64Array()        # §14.2c (3): household-bundle h's point masses are tr_hm_off[h] .. tr_hm_off[h + 1] - 1
var tr_hm_pt := PackedInt32Array()
var tr_hm_role := PackedInt32Array()
var tr_hm_n := PackedInt64Array()
var tr_cp_hh := PackedInt32Array()         # §14.2c (4): the couple points: household-bundle, wife point, husband point, mass
var tr_cp_w := PackedInt32Array()
var tr_cp_h := PackedInt32Array()
var tr_cp_n := PackedInt64Array()
var tr_pt_ms := PackedInt64Array()         # §14.2c (6): each point's mass by marital state (never, married, widowed, divorced)
var tr_nh_hh: Dictionary = {}              # §12.12 (9): "pref|householder band|class" of type 4 -> [[husband unit, wife unit, kind, n]]
var tr_nh_couples: Dictionary = {}         # §12.12 (9): "pref|husband band|wife band|kind" (kind 0 child, 1 parent) -> the non-head couples
var tr_couples: Dictionary = {}            # §12.12: "pref|husband band|wife band|type" (R77 bands 0-14) -> the start's couples
var tr_points: Dictionary = {}             # field name -> packed array of the points x stride (each unit's sample persons)
var tr_hh: Dictionary = {}                 # the household-bundles: key -> {count, members {bundle: {role: count}}}
var tr_instruments: Dictionary = {}        # instrument -> per holder (the points, then the individuals), int64 yen
var tr_instrument_factor: Dictionary = {}
var tr_indiv_unit := PackedInt32Array()    # per individual: the bundle it was drawn from
var tr_pt_id := PackedInt64Array()         # §14.6 (1): each point's stable id, the key of its draws
var tr_pt_jan := PackedInt64Array()        # §14.6 (1): each (point, age)'s mass at the year's January
var tr_pt_old := PackedInt64Array()        # §14.6 (1): each (point, age)'s mass not yet aged this year
var tr_pt_next: int = 0                    # the next new point's id
var tr_kb := PackedInt64Array()            # per bundle: its point target K_b (§12.5 F2, re-targeted each January)
var tr_class_lines := PackedFloat64Array() # the start's class lines (§12.8 item 3), read when a point enters the adult bands
var tr_c := PackedFloat64Array()           # §14.6 (2): c_{a,s} of the tiers' deaths, solved once at the start
var tr_pt_q := PackedInt32Array()          # §14.6 (2): each point's equivalized-income quartile (0 the top), re-read once a month before the compression (§14.6 (6))
var tr_pt_muq := PackedFloat64Array()      # T2s-drift's stock form (TO_E 11:37): each point's booked married mass moved across quartile lines
var tr_pt_mug := PackedFloat64Array()      # ... and across grade lines (signed persons)
var tr_cp_cap: Dictionary = {}             # §14.6 (4) M025b C5: household-bundle -> its couple entries in T2.1's start table
var tr_pt_rem: Dictionary = {}             # §14.6 (4) M025 C4: (point id x 16 + age slot) x 8 + grade x 2 + class -> a merged cell's remaining births by month, until January
var tr_pt_ag := PackedInt64Array()         # M030, T2.2b: each (point, age, grade, class) cell's mass; tr_pt_age their sums
var tr_pt_jg := PackedInt64Array()         # M030: ... its mass at the year's January
var tr_pt_og := PackedInt64Array()         # M030: ... its mass not yet aged this year
var tr_pt_T := PackedInt64Array()          # M030: each point's marital x grade table (4 x 4, marital major); tr_pt_ms its rows' sums
## Why pid keys and not per-person arrays in fields(): the arrays would enter every tiers-off save and digest (T1s-f), and a pid key
## survives the life course's compaction
var tr_phi: Dictionary = {}                # pid -> the person's own factor on the table pay (§12.8 10.1)
var tr_pension: Dictionary = {}            # pid -> the person's own pension before R68's index (§12.8 10.1)
var tr_pension_kind: Dictionary = {}       # pid -> the 65+'s pension kind (§12.9 M1: tiers.PEN_*)
# households (ISS_HOUSEHOLD_REDESIGN.md, H1): set before create; off allocates nothing
var households: bool = false
var hh_spec: Dictionary = {}
var hh_n: int = 0
var hh_id := PackedInt32Array()           # per person: its household
var hh_type := PackedInt32Array()         # per household: HOUSEHOLD index
var hh_pref := PackedInt32Array()
var hh_weight := PackedFloat64Array()     # one weight per household (§3)
var hh_members: Array = []                # per household: PackedInt32Array of persons, rebuilt from hh_id
# the life course (H2, life_course.gd): per person
var hh_role := PackedInt32Array()
var partner := PackedInt32Array()
var ever_married := PackedInt32Array()
var ever_left := PackedInt32Array()
var union_month := PackedInt32Array()
var last_birth := PackedInt32Array()
var births_n := PackedInt32Array()
var next_k: Dictionary = {}               # prefecture -> newborns so far (their pid counter)
var life_log: Array = []                  # [month, pid, kind, other pid, detail, weight, sex]
var lc_dying := PackedInt32Array()        # this month's deaths, removed at the month's end
var lc_t22b: Dictionary = {}              # T2.2b (§14.6 (8)): the month's grade-transition tallies (T2s-gp, T2s-gk), January only
var health_class := PackedInt32Array()    # T2.2b (M032): per person, the health class, 0 stable, 1 mobile (households on)
var lc_c := PackedFloat64Array()          # §14.4a: the death hazard's c per single age x sex (CALIBRATED at the start)
var lc_qcut := PackedFloat64Array()       # §14.4a: the equivalized-income quartile cuts, 3 per 10-year band
var rone_on := false                      # R-one's record (a test only): never saved or digested
var rone_log: Array = []
var lc_c_band: int = 0                    # §14.4a: the single ages x sexes whose c took their band's shares (no person at the age)
var lc_expected := PackedFloat64Array([0, 0, 0, 0, 0, 0, 0, 0])   # H2s-c: the summed hazard by death band x sex
var lc_deaths := PackedInt32Array([0, 0, 0, 0, 0, 0, 0, 0])
var lc_births: Array = []                 # [month, mother's age, her weight]
var lc_nm_short := PackedFloat64Array() # §10.8 C3: per R62 band x sex, the never-married persons the start could not place (0 met)
var intends_marry := PackedInt32Array()   # per person (§10.6 A1, P): 1 yes, 0 no, -1 not yet drawn (under 18)
var intended_kids := PackedInt32Array()   # per person (§10.6 A2, P): a woman's intended number of children, -1 not drawn


func load_spec(key: String, commodities_path: String = "res://data/modern/econ/commodities.json") -> String:
	state = key
	var d: Variant = CANON.load_json("res://data/modern/people/%s_people_2024.json" % key.to_lower())
	if not (d is Dictionary):
		error = "people: no spec for " + key
		return error
	spec = d
	# Why loud and not an elasticity of 0 (the code review, 2d): without the file every food price rise would leave the persons' demand
	# unmoved, silently
	var cm: Variant = CANON.load_json(commodities_path)
	if not (cm is Dictionary) or not ((cm as Dictionary).get("commodities", {}) as Dictionary).has("food_products"):
		error = "people: no food price elasticity (%s)" % commodities_path
		push_error(error)
		return error
	food_elasticity = float(cm["commodities"]["food_products"]["demand_elasticity"])
	return ""


## The food price rise a person believes (the yearly change as told by the register or contacts; 0 when nobody told it)
func believed_food_rise(i: int) -> float:
	return belief[i * REL.NF] if belief_known[i * REL.NF] == 1 else 0.0


## The rise of the household's cost of living the person believes: the believed food price rise on the food share of its basket
## Why not max(0, the believed rise): zero-mean noise in the belief then reads as inflation, and a calm economy reads as a real fall (M002 G2)
func believed_cost_rise(i: int) -> float:
	return basket[i * 4] * believed_food_rise(i)


## The person's own price response of its food quantity: the demand elasticity on the believed yearly change. Why the yearly change
## and not the level against the start: a person knows the published change, not an index against an arbitrary base month (T)
func food_price_response(i: int) -> float:
	return DM.pow(1.0 + maxf(-0.5, believed_food_rise(i)), food_elasticity) if food_elasticity != 0.0 else 1.0


## A mover's destination: one keyed draw over the other prefectures by their population (T: gravity on population alone, until the
## 住民基本台帳人口移動報告 origin-destination flows replace it)
## With households on, a move needs a reason (§10.6 A5): "job" (unemployed, or last month a job search or change) or "family" (a family
## contact in another prefecture); "" is none. The moving unit decides (§10.7 B5): a head for its household on its own or its
## partner's job reason, a lone mover (an adult child or other member) on its own; a partner does not decide. Why last month's action
## and not the search flag: the flag is reset before the decisions
func move_reason(i: int) -> String:
	if hh_role[i] == R_PARTNER:
		return ""
	if _job_reason(i) or (hh_role[i] == R_HEAD and partner[i] >= 0 and _job_reason(partner[i])):
		return "job"
	return "family" if _kin_elsewhere(i) >= 0 else ""


func _job_reason(i: int) -> bool:
	return employment[i] == EMP_UNEMPLOYED or last_action[i] == ACT.A_SEARCH or last_action[i] == ACT.A_CHANGE


func _kin_elsewhere(i: int) -> int:
	for c: int in REL.C:
		var j: int = contact_idx[i * REL.C + c]
		if j >= 0 and contact_kind[i * REL.C + c] == REL.K_FAMILY and pref[j] != pref[i]:
			return pref[j]
	return -1


func move_destination(i: int, m: int) -> int:
	if households and move_reason(i) == "family":
		return _kin_elsewhere(i)
	var tot: float = 0.0
	for code: int in pref_pop:
		if code != pref[i]:
			tot += float(pref_pop[code])
	var x: float = u("move_to", i, m) * tot
	var acc: float = 0.0
	var last: int = pref[i]
	for code2: String in pref_codes:
		var c: int = int(code2)
		if c == pref[i]:
			continue
		acc += float(pref_pop[c])
		last = c
		if x < acc:
			return c
	return last


## A move to another prefecture (the code review, 1b): the mover leaves its old prefecture's groups, keeps its kin and each other contact
## with probability MOVE_KEEP (T, one keyed draw per contact). With households on, a head or partner moves its household with it
## (life_course.move_household); a child or other member leaves into a one-person household there; an institution resident stays.
## Why not the prefecture alone: the household's prefecture, which the rake reads, stayed behind (half-moved movers)
const MOVE_KEEP := 0.5


func move_to(i: int, dest: int, reason: String = "") -> void:
	if households:
		LC.move_household(self, i, dest, reason)
		return
	pref[i] = dest
	_moved(i, dest)


func _moved(i: int, dest: int) -> void:
	for m: int in GRP.M:
		var g: int = member_of[i * GRP.M + m]
		if g >= 0 and int(groups[g]["pref"]) != dest:
			GRP.leave(self, i, g)
	for c: int in REL.C:
		var j: int = contact_idx[i * REL.C + c]
		if j < 0 or contact_kind[i * REL.C + c] == REL.K_FAMILY or pref[j] == dest:
			continue
		if u("movekeep", i, month * REL.C + c) >= MOVE_KEEP:
			REL.unlink_slot(self, i, c)


## The sampling weights raked every month (iterative proportional fitting, 6 rounds) to the two margins the status layer owns: each
## prefecture's population (the published one, scaled by the cohort's total since the start) and the cohort's shares by age band x sex
## (0-14, 15-29, 30-44, 45-64, 65+). Why: the population counts are the cohort's and the data's (survey 2). A mover carries its origin's
## weight, and left alone the moves re-drew the map (V086: Tokyo x2.5 in 24 months); a death is replaced by a newborn, so the sample
## grew young (children 0.118 -> 0.153 in seven years against the cohort's 0.097, audit run). The prefecture step comes last, so its
## totals are exact; a cell or prefecture with no sample person keeps nobody's weight. Why every month and not once a year: between the
## yearly rakes a prefecture's total drifted by up to 35% (N = 50, year 3; V091) and every prefecture aggregate read in between (votes
## by prefecture, Phase 7) was off by that much; the rule is the same, run at every month a reader can see
func reweight(cohort_now: PackedFloat64Array, start_types: bool = false) -> void:
	# Why loud (the code review, 2d): a person of a prefecture without a published population was left out of the prefecture step
	for i0: int in n:
		if not pref_pop.has(pref[i0]):
			error = "people: prefecture %d has no population; the rake cannot scale it" % pref[i0]
			push_error(error)
			break
	var c_now: PackedFloat64Array = cohort_now if cohort_now.size() == AGES * SEXES else cohort
	var tot_start: float = 0.0
	var tot_now: float = 0.0
	for k: int in AGES * SEXES:
		tot_start += cohort[k]
		tot_now += c_now[k]
	var cell_target := PackedFloat64Array()
	cell_target.resize((AGE_BANDS.size() + 1) * SEXES)
	for a: int in AGES:
		for s: int in SEXES:
			cell_target[band_of(a) * SEXES + s] += c_now[a * SEXES + s] / tot_now
	if households:
		HH.rake(self, cell_target, tot_now / tot_start, start_types)
		return
	var pop_total: float = 0.0
	for code: int in pref_pop:
		pop_total += float(pref_pop[code])
	for r: int in 6:
		var csum := PackedFloat64Array()
		csum.resize(cell_target.size())
		var all: float = 0.0
		for i: int in n:
			csum[band_of(age[i]) * SEXES + sex[i]] += weight[i]
			all += weight[i]
		for i2: int in n:
			var cc: int = band_of(age[i2]) * SEXES + sex[i2]
			if csum[cc] > 0.0:
				weight[i2] *= cell_target[cc] * all / csum[cc]
		var now: Dictionary = {}
		for i3: int in n:
			now[pref[i3]] = float(now.get(pref[i3], 0.0)) + weight[i3]
		for i4: int in n:
			var w0: float = float(now.get(pref[i4], 0.0))
			if w0 > 0.0 and pref_pop.has(pref[i4]):
				weight[i4] *= float(pref_pop[pref[i4]]) * (tot_now / tot_start) / w0


const AGE_BANDS := [15, 30, 45, 65]


static func band_of(a: int) -> int:
	for b: int in AGE_BANDS.size():
		if a < AGE_BANDS[b]:
			return b
	return AGE_BANDS.size()


## Build the persons: n_per prefecture from the prefectures table {code: {pop_thousand}}, ages and sexes from the cohort (AGES x SEXES
## counts), deaths later by qx (yearly, by sex and age)
func create(key: String, seed: int, cohort_: PackedFloat64Array, qx_: PackedFloat64Array, prefectures: Dictionary, n_per: int = 0, year: int = 2024) -> String:
	if load_spec(key) != "":
		return error
	seed_v = seed
	base_year = year
	# Why copies: a packed array is passed by reference, and the status layer ages its cohort in place, so the persons' start cohort
	# followed it, the raking's "since the start" scale stayed 1, and a world restored from a save (which holds a copy) parted from the
	# straight run at the first year turn (audit, resume across a rake)
	cohort = cohort_.duplicate()
	qx = qx_.duplicate()
	if n_per <= 0:
		n_per = int(spec["n_per_prefecture"]["value"])
	pref_codes = prefectures.keys()
	pref_codes.sort()
	if tiers:
		return _create_tiers(prefectures)
	if households:
		return _create_households(prefectures, n_per)
	# the cohort's cumulative distribution for the joint (age, sex) draw
	var cum := PackedFloat64Array()
	cum.resize(AGES * SEXES)
	var tot: float = 0.0
	for i: int in AGES * SEXES:
		tot += cohort[i]
		cum[i] = tot
	n = pref_codes.size() * n_per
	_resize(n)
	var i: int = 0
	for code: String in pref_codes:
		var popn: float = float(prefectures[code]["pop_thousand"]) * 1000.0
		pref_pop[int(code)] = popn
		for k: int in n_per:
			var u: float = KEYED.u(seed_v, "cohort", int(code), k, 0) * tot
			var cell: int = 0
			while cell < AGES * SEXES - 1 and cum[cell] < u:
				cell += 1
			var a: int = cell / SEXES
			var s: int = cell % SEXES
			pref[i] = int(code)
			k_in_pref[i] = k
			age[i] = a
			sex[i] = s
			pid[i] = KEYED.pid(seed_v, int(code), base_year - a, s, k)
			weight[i] = popn / float(n_per)
			_draw_attributes(i)
			_draw_traits(i)
			_draw_dream(i)
			i += 1
	_ranks()
	for j: int in n:
		_compose_drives(j)
		_init_states(j)
	REL.build(self)
	GRP.seed_groups(self)
	return ""


## The start built by the tiered population (T1, §12): the units from the cohort, the prefectures and the spec's shares, fitted and
## rounded to the population; the persons layer holds the top tier's individuals only
func _create_tiers(prefectures: Dictionary) -> String:
	if TR.load_spec(self) != "":
		error = "tiers: no spec for " + state
		return error
	# Why not a copy of the life course's inputs in the tiers spec: the tiers' deaths read the persons' one source (§14.1)
	if HH.load_spec(self) != "":
		error = "tiers: no households spec for the deaths' inputs"
		return error
	for code: String in pref_codes:
		pref_pop[int(code)] = float(prefectures[code]["pop_thousand"]) * 1000.0
	TR.build_start(self, prefectures)
	for i: int in n:
		weight[i] = 1.0
	return ""


## A tiered start's person (an individual of the top tier, or a sample point in its scratch slot): the unit's employment and household
## type, then the income (the wage when negative) and the assets (kept when negative)
func tier_person(i: int, emp: int, kind: int, inc: float, ass: float) -> void:
	employment[i] = emp
	hh_kind[i] = kind
	income[i] = inc if inc >= 0.0 else wage(i)
	if ass >= 0.0:
		assets[i] = ass


## A tiered start's education given its class (§12.10 V1b): the education, the skill by _draw_attributes' rule with the person's own
## keyed term, and the pay re-read
func tier_education(i: int, d: int) -> void:
	var a: int = age[i]
	education[i] = d
	skill[i] = clampf(20.0 + 15.0 * education[i] + 0.8 * maxf(0.0, a - 22) + 10.0 * normal("skill", i), 0.0, 100.0)
	income[i] = wage(i)


## A tiered start's income drawn inside its class (§12.8 item 3, 10.1): the income, the expected income reset to it, the person's own
## level that makes wage() give it (a worker's or the unemployed's factor on the table pay at the job's own factor, a pensioner's
## pension before the index), and the assets (kept when negative)
func tier_income(i: int, inc: float, ass: float) -> void:
	income[i] = inc
	q_income[i] = inc
	var e: int = employment[i]
	if e == EMP_RETIRED or (e == EMP_NONE and tiers and age[i] >= PENSION_AGE):
		if inc > 0.0:
			tr_pension[pid[i]] = inc / pension_index(i)
		else:
			tr_pension.erase(pid[i])
	elif e == EMP_REGULAR or e == EMP_NONREGULAR or e == EMP_UNEMPLOYED:
		tr_phi.erase(pid[i])
		var pen: float = entitled(i)
		var w: float = wage(i) - pen
		if w > 0.0:
			tr_phi[pid[i]] = (inc - pen) / w
	if ass >= 0.0:
		assets[i] = ass


## A tiered start's public pension at 65+ by entitlement (§12.9 M1): its kind and its amount now (万円 a month), kept before R68's index
func tier_pension(i: int, amount: float, kind: int) -> void:
	tr_pension_kind[pid[i]] = kind
	if amount > 0.0:
		tr_pension[pid[i]] = amount / pension_index(i)
	else:
		tr_pension.erase(pid[i])


## A tiered start's wealth from the household instruments (§12.8 10.5): the person's assets and debt, 万円
func tier_wealth(i: int, ass: float, dbt: float) -> void:
	assets[i] = ass
	debt[i] = dbt


## The start built by households (H1): the households and their members first, then each member's attributes from its age and sex, the
## members linked as family, the rest of the contacts and the groups as before, and the start's rake at the household level
func _create_households(prefectures: Dictionary, n_per: int) -> String:
	if HH.load_spec(self) != "":
		error = "households: no spec for " + state
		return error
	for code: String in pref_codes:
		pref_pop[int(code)] = float(prefectures[code]["pop_thousand"]) * 1000.0
	HH.build_start(self, prefectures, n_per)
	for i: int in n:
		_draw_attributes(i)
		_draw_traits(i)
		_draw_dream(i)
	LC.start(self)
	_ranks()
	for j: int in n:
		_compose_drives(j)
		_init_states(j)
	HH.link_family(self)
	REL.build(self)
	GRP.seed_groups(self)
	reweight(PackedFloat64Array(), true)
	LC.solve_c(self)
	return ""


## The one field registry (the owner's tidy-up, item 3): every saved array of the persons, read by _resize, per_person_arrays,
## to_dict, from_dict and digest_dict, so a field cannot be saved and left out of the digest or the growth. Each row: the variable,
## its stored kind (i64, i32, f64), its stride per person (0: not per person), the value a new slot is filled with, the value a save
## without the field restores (null: the field is required)
func fields() -> Array:
	return [["pid", "i64", 1, 0, null],
		["pref", "i32", 1, 0, null], ["k_in_pref", "i32", 1, 0, null], ["age", "i32", 1, 0, null], ["sex", "i32", 1, 0, null], ["hh_kind", "i32", 1, 0, null],
		["education", "i32", 1, 0, null], ["employment", "i32", 1, 0, null], ["health", "i32", 1, 0, null], ["dream_kind", "i32", 1, 0, null],
		["dream_status", "i32", 1, 0, null], ["dream_blocked", "i32", 1, 0, null], ["mem_month", "i32", K_MEM, 0, null], ["mem_kind", "i32", K_MEM, 0, null],
		["mem_head", "i32", 1, 0, null], ["plan", "i32", 1, 0, null], ["search", "i32", 1, 0, null], ["flags", "i32", 1, 0, null],
		["last_action", "i32", 1, 0, null], ["contact_idx", "i32", REL.C, -1, null], ["contact_kind", "i32", REL.C, 0, null],
		["contact_last", "i32", REL.C, 0, null], ["met", "i32", 1, 0, null], ["belief_known", "i32", REL.NF, 0, null], ["belief_source", "i32", REL.NF, 0, null],
		["belief_month", "i32", REL.NF, 0, null], ["member_of", "i32", GRP.M, -1, null], ["union_cover", "i32", 1, 0, 0],
		["weight", "f64", 1, 0, null], ["hh_size", "f64", 1, 0, null], ["income", "f64", 1, 0, null], ["pay_factor", "f64", 1, 0, 1.0],
		["assets", "f64", 1, 0, null], ["debt", "f64", 1, 0, null], ["skill", "f64", 1, 0, null], ["rank", "f64", 1, 0, null], ["traits", "f64", NT, 0, null],
		["lam", "f64", 1, 0, null], ["dw", "f64", ND, 0, null], ["emo", "f64", NE, 0, null], ["emo_base", "f64", NE, 0, null], ["dd", "f64", ND, 0, null],
		["basket", "f64", 4, 0, null], ["pref_leisure", "f64", 1, 0, null], ["pref_social", "f64", 1, 0, null], ["pol_interest", "f64", 1, 0, null],
		["dream_importance", "f64", 1, 0, null], ["dream_progress", "f64", 1, 0, null], ["q_income", "f64", 1, 0, null], ["q_price", "f64", 1, 0, null],
		["q_job", "f64", 1, 0, null], ["mem_val", "f64", K_MEM, 0, null], ["cohort", "f64", 0, 0, null], ["qx", "f64", 0, 0, null],
		["q_act", "f64", ACT.NA, 0, null], ["pressure_prev", "f64", 1, 0, null], ["contact_trust", "f64", REL.C, 0, null], ["belief", "f64", REL.NF, 0, null]]


## The households' rows (H1, H2): the variable, its key in the save, its kind, its stride per person (0: per household or other), and
## whether the digest reads it. Why lc_expected and lc_deaths are not digested: they are H2s-c's tallies of what the months did, records
## like the life log, not what the next month reads
func household_fields() -> Array:
	return [["hh_id", "hh_id", "i32", 1, true], ["hh_role", "role", "i32", 1, true], ["partner", "partner", "i32", 1, true],
		["ever_married", "ever_married", "i32", 1, true], ["ever_left", "ever_left", "i32", 1, true], ["union_month", "union_month", "i32", 1, true],
		["last_birth", "last_birth", "i32", 1, true], ["births_n", "births_n", "i32", 1, true],
		["hh_type", "type", "i32", 0, true], ["hh_pref", "pref", "i32", 0, true], ["hh_weight", "weight", "f64", 0, true], ["lc_c", "lc_c", "f64", 0, true], ["lc_qcut", "lc_qcut", "f64", 0, true],
		["lc_expected", "lc_expected", "f64", 0, false], ["lc_deaths", "lc_deaths", "i32", 0, false],
		["lc_nm_short", "lc_nm_short", "f64", 0, false], ["intends_marry", "intends_marry", "i32", 1, true], ["intended_kids", "intended_kids", "i32", 1, true],
		["health_class", "health_class", "i32", 1, true]]


## The per-person arrays and their strides, for the life course's growth and compaction (H2). Why a list beside _resize: _resize
## clears the links of every slot, which a birth must not do to the living
func per_person_arrays() -> Array:
	var out: Array = []
	for f: Array in fields():
		if int(f[2]) > 0:
			out.append([get(String(f[0])), int(f[2])])
	for h: Array in household_fields():
		if int(h[3]) > 0:
			out.append([get(String(h[0])), int(h[3])])
	return out


func _resize(m: int) -> void:
	for f: Array in fields():
		if int(f[2]) > 0:
			var arr = get(String(f[0]))
			arr.resize(m * int(f[2]))
			if int(f[3]) != 0:
				arr.fill(int(f[3]))


## A rule's keyed draw against its rate h (§14.1, R-one): u < h; with rone_on (a test only) the operand is recorded
func below(tag: String, i: int, b: int, c: int, h: float) -> bool:
	var x: float = u(tag, i, b, c)
	if rone_on:
		rone_log.append(["draw", tag, i, h])
	return x < h


## A rate function's output, recorded with rone_on (R-one (a′)); off, it only returns v
func rone_out(name: String, v: Variant) -> Variant:
	if rone_on:
		rone_log.append(["out", name, v])
	return v


func u(tag: String, i: int, b: int = 0, c: int = 0) -> float:
	return KEYED.u(seed_v, tag, int(pid[i] & 0x7FFFFFFFFFFF), b, c)


func normal(tag: String, i: int, b: int = 0, c: int = 0) -> float:
	return KEYED.normal(seed_v, tag, int(pid[i] & 0x7FFFFFFFFFFF), b, c)


static func pick(shares: Dictionary, keys: Array, x: float) -> int:
	var acc: float = 0.0
	for j: int in keys.size():
		acc += float(shares[keys[j]])
		if x < acc:
			return j
	return keys.size() - 1


static func age_band(a: int) -> String:
	return "under_30" if a < 30 else ("30_59" if a < 60 else "60_plus")


func _draw_attributes(i: int) -> void:
	var a: int = age[i]
	# household (with households on, the person's household gives them: H1)
	if households:
		pass
	elif a < 18:
		hh_kind[i] = HK_COUPLE_CHILDREN if u("hh", i) < float(spec["household_kind_child"]["couple_children"]) else HK_SINGLE_PARENT
	else:
		hh_kind[i] = pick(spec["household_kind_shares_adult"], HOUSEHOLD, u("hh", i))
	hh_size[i] = float(spec["household_size"][HOUSEHOLD[hh_kind[i]]])
	# education (complete at 22)
	var eb: String = "22_34" if a < 35 else ("35_54" if a < 55 else "55_plus")
	education[i] = pick(spec["education_shares_by_age"][eb], EDUCATION, u("edu", i)) if a >= 22 else 0
	# employment: the labour status the economy holds at the start (participation, non-regular share, unemployment rate: S)
	var p: Dictionary = spec["participation"]
	var ur: float = float(spec["unemployment_rate_start"]["value"])
	if a < 15:
		employment[i] = EMP_NONE
	elif a < 18:
		employment[i] = EMP_STUDENT if u("stu", i) < float(spec["student_share_by_age"]["15_17"]) else _labour(i, ur)
	elif a < 22:
		var sk: String = "18_19" if a < 20 else "20_21"
		employment[i] = EMP_STUDENT if u("stu", i) < float(spec["student_share_by_age"][sk]) else _labour(i, ur)
	elif a < 65:
		var part: float = float(p["male_15_64"]) if sex[i] == MALE else float(p["female_15_64"])
		employment[i] = _labour(i, ur) if u("part", i) < part else 0
	else:
		employment[i] = _labour(i, ur) if u("part", i) < float(p["age_65_plus"]) else 5
	pay_factor[i] = 1.0
	income[i] = wage(i)
	# assets, debt, health, skill
	var ab: String = "under_30" if a < 30 else ("30_39" if a < 40 else ("40_49" if a < 50 else ("50_59" if a < 60 else "60_plus")))
	assets[i] = float(spec["assets_median_man_yen_by_age"][ab]) * DM.exp(0.8 * normal("assets", i)) if a >= 18 else 0.0
	var hl: Dictionary = spec["housing_loan"]
	debt[i] = float(hl["size_man_yen"]) * (0.5 + u("debtsz", i)) if (a >= 30 and a <= 55 and hh_kind[i] >= HK_COUPLE and hh_kind[i] <= HK_COUPLE_CHILDREN and u("debt", i) < float(hl["p_by_kind_30_55"])) else 0.0
	var hp: Dictionary = spec["health_poor_share_by_age"]
	var ppoor: float = float(hp["base"]) + float(hp["slope_per_year"]) * a
	var hu: float = u("health", i)
	health[i] = GRADE_POOR if hu < ppoor else (GRADE_FAIR if hu < ppoor * 2.5 else GRADE_GOOD)
	skill[i] = clampf(20.0 + 15.0 * education[i] + 0.8 * maxf(0.0, a - 22) + 10.0 * normal("skill", i), 0.0, 100.0) if a >= 15 else 0.0


func _labour(i: int, ur: float) -> int:
	if u("unemp", i) < ur:
		return EMP_UNEMPLOYED
	var nr: float = float(spec["non_regular_share"]["male"]) if sex[i] == MALE else float(spec["non_regular_share"]["female"])
	return EMP_NONREGULAR if u("nonreg", i) < nr else EMP_REGULAR


## R68's index of this person's pensioner group (the new pensioners' to new_until_age, then the existing pensioners')
func pension_index(i: int) -> float:
	return pension_index_at(age[i])


func pension_index_at(a: int) -> float:
	var pr: Dictionary = spec["pension_rule"]["value"]
	return float(pension["new"]) if a <= int(pr["new_until_age"]) else float(pension["old"])


## The monthly income the economy's tables give this person for its status (S wage tables; the spread T); with tiers on, the
## person's own level (§12.8 10.1)
func wage(i: int) -> float:
	var e: int = employment[i]
	if e == EMP_NONE:
		return entitled(i)
	if e == EMP_STUDENT:
		return float(spec["student_income_man_yen"]["value"])
	if e == EMP_RETIRED:
		if tiers and tr_pension.has(pid[i]):
			return float(tr_pension[pid[i]]) * pension_index(i)
		return float(spec["pension_man_yen"]["value"]) * (0.7 + 0.6 * u("pension", i)) * pension_index(i)
	var w: Dictionary = spec["wage_regular_man_yen"]
	var base: float = float(w["male"]) if sex[i] == MALE else float(w["female"])
	var curve: Dictionary = spec["wage_age_curve"]
	var a: int = age[i]
	var dec: String = str(clampi(a / 10 * 10, 20, 70))
	base *= float(curve[dec])
	base *= float(spec["wage_education_factor"][EDUCATION[education[i]]])
	base *= DM.exp(float(spec["wage_sigma"]["value"]) * normal("wage", i))
	# the skill reaches the pay (D: 賃金構造基本統計調査 勤続年数別, ~0.4% a point around 50, T) and the economy's wage index
	base *= (1.0 + 0.004 * (skill[i] - 50.0)) * wage_index
	if e == EMP_REGULAR or e == EMP_NONREGULAR:
		base *= pay_factor[i]
		if tiers:
			base *= cash_ratio(i)
	if tiers:
		base *= float(tr_phi.get(pid[i], 1.0))
	if e == EMP_NONREGULAR:
		base *= float(spec["non_regular_wage_factor"]["value"])
	elif e == EMP_UNEMPLOYED:
		base *= float(spec["unemployment_benefit_factor"]["value"])
	return base + entitled(i)


## A tiered person's own public pension at 65+ beside its status's income (§12.9 M1): its own amount at R68's index, 0 with tiers off
## or with no pension
func entitled(i: int) -> float:
	if not tiers or age[i] < PENSION_AGE:
		return 0.0
	return float(tr_pension.get(pid[i], 0.0)) * pension_index(i)


## 賃金構造 2022's annual cash earnings ÷ 12 over 所定内 at this person's 5-year band, sex and status (§12.9 M2, the PM's option A)
func cash_ratio(i: int) -> float:
	var cr: Dictionary = tr_spec["wage_cash_ratio"]["value"]
	var a: int = age[i]
	var k: int = 0 if a < 20 else mini(11, (a - 20) / 5 + 1)
	return float(cr["regular" if employment[i] == EMP_REGULAR else "non_regular"]["male" if sex[i] == MALE else "female"][k])


## The writes other modules ask of a person's own state (the tidy-up: one writer per datum, people.gd; actions, groups, relations
## and labour call these instead of writing the arrays)
func reset_choices(i: int) -> void:
	plan[i] = 1
	search[i] = 0
	flags[i] = 0


func set_search(i: int, v: int) -> void:
	search[i] = v


func set_plan(i: int, v: int) -> void:
	plan[i] = v


func add_flag(i: int, bit: int) -> void:
	flags[i] |= bit


## Assets less a cost, never below zero (an action's cost)
func spend(i: int, amount: float) -> void:
	assets[i] = maxf(0.0, assets[i] - amount)


## Assets moved by a signed amount without a floor (dues, help, support)
func add_assets(i: int, delta: float) -> void:
	assets[i] += delta


func add_skill(i: int, gain: float) -> void:
	skill[i] = minf(100.0, skill[i] + gain)


## One emotion slot (i x NE + e) moved toward a target by a rate, kept in 0..1
func pull_emotion(k: int, target: float, rate: float) -> void:
	emo[k] = clampf(emo[k] + rate * (target - emo[k]), 0.0, 1.0)


## The pay re-read from the table and the person's job (after the labour market changed the job)
func repay(i: int) -> void:
	income[i] = wage(i)


## A person's prefecture; with households on, a change is a move by the mover's rule (_moved). Why here and not in move_to alone: a
## partnering takes one partner to the other's prefecture too, and kept its old prefecture's groups (found by R1b's forced moves)
func set_pref(i: int, code: int) -> void:
	var was: int = pref[i]
	pref[i] = code
	if households and code != was:
		_moved(i, code)


## The start's persons placed by the household module (H1): n, the arrays sized, each person's prefecture, index, age, sex and pid
func place_persons(m: int) -> void:
	n = m
	_resize(n)


func place_person(i: int, code: int, kk: int, a: int, s: int) -> void:
	pref[i] = code
	k_in_pref[i] = kk
	age[i] = a
	sex[i] = s
	pid[i] = KEYED.pid(seed_v, code, base_year - a, s, kk)


## A newborn's slot appended (the life course, H2): its prefecture, a new pid from the prefecture's newborn counter k, sex 0.512 male,
## age 0; the caller places it in its household and gives it the household's weight (the rake module's set_member_weight), then calls
## draw_person and finish_person
func new_person(code: int, k: int) -> int:
	var j: int = n
	grow_persons(j + 1)
	pref[j] = code
	k_in_pref[j] = 1000000 + k
	age[j] = 0
	sex[j] = MALE if KEYED.u(seed_v, "lc_sex", code, k, 0) < 0.512 else FEMALE
	pid[j] = KEYED.pid(seed_v, code, base_year + month / 12, sex[j], 1000000 + k)
	return j


## The person's attributes from its age and sex; finish_person draws the rest (the life course sets the grade between the two)
func draw_person(i: int) -> void:
	_draw_attributes(i)


func finish_person(i: int) -> void:
	_draw_traits(i)
	_draw_dream(i)
	_compose_drives(i)
	_init_states(i)


## Every per-person array grown to m persons; the new slots' links empty
func grow_persons(m: int) -> void:
	var n0: int = n
	for e: Array in per_person_arrays():
		e[0].resize(m * int(e[1]))
	for i: int in range(n0, m):
		for c: int in REL.C:
			contact_idx[i * REL.C + c] = -1
		for g: int in GRP.M:
			member_of[i * GRP.M + g] = -1
	n = m


## The dead removed (the life course, H2): every per-person array closed up in order, the person indices (contacts, partners)
## remapped, the household members rebuilt
func remove_persons(dead: PackedByteArray) -> void:
	var n_old: int = dead.size()
	var remap := PackedInt32Array()
	remap.resize(n)
	var k: int = 0
	for i: int in n:
		if i < n_old and dead[i] == 1:
			remap[i] = -1
		else:
			remap[i] = k
			k += 1
	if k == n:
		return
	for e: Array in per_person_arrays():
		var arr = e[0]
		var s: int = int(e[1])
		for i2: int in n:
			var t: int = remap[i2]
			if t >= 0 and t != i2:
				for c: int in s:
					arr[t * s + c] = arr[i2 * s + c]
		arr.resize(k * s)
	for c2: int in contact_idx.size():
		var j: int = contact_idx[c2]
		if j >= 0:
			contact_idx[c2] = remap[j]
	for i3: int in k:
		if partner[i3] >= 0:
			partner[i3] = remap[partner[i3]]
	n = k
	HH.refresh_members(self)


func _draw_traits(i: int) -> void:
	var sd: float = float(spec["trait_sd"]["value"])
	for t: int in NT:
		traits[i * NT + t] = clampf(0.5 + sd * normal("trait", i, t), 0.02, 0.98)
	# loss aversion tied to risk tolerance (traits.gd range 1.2..3.0, mean 2.0)
	var la: Dictionary = spec["loss_aversion"]
	lam[i] = clampf(float(la["mean"]) + (0.5 - trait_of(i, "risk_tolerance")) * 1.6, float(la["range"][0]), float(la["range"][1]))
	# preferences from traits and age (T)
	pref_leisure[i] = clampf(0.3 + 0.3 * trait_of(i, "openness") + 0.2 * (1.0 - trait_of(i, "competitiveness")) + 0.05 * normal("pl", i), 0.05, 0.95)
	pref_social[i] = clampf(trait_of(i, "sociability") + 0.05 * normal("ps", i), 0.05, 0.95)
	pol_interest[i] = clampf(0.15 + 0.4 * trait_of(i, "fairness") * trait_of(i, "openness") + 0.004 * maxf(0.0, age[i] - 30) + 0.08 * normal("pi", i), 0.02, 0.98)
	# the basket: food share falls with income (Engel, D: 家計調査 食料 ~26%), housing by household kind, leisure by preference
	var food: float = 0.26
	var housing: float = 0.18 if hh_kind[i] == HK_SINGLE else 0.12
	var leisure: float = 0.08 + 0.08 * pref_leisure[i]
	basket[i * 4] = food
	basket[i * 4 + 1] = housing
	basket[i * 4 + 2] = leisure
	basket[i * 4 + 3] = maxf(0.0, 1.0 - food - housing - leisure)


func trait_of(i: int, name: String) -> float:
	return traits[i * NT + TRAITS.find(name)]


func emotion(i: int, name: String) -> float:
	return emo[i * NE + EMOTIONS.find(name)]


func drive_w(i: int, name: String) -> float:
	return dw[i * ND + DRIVES.find(name)]


func deficit(i: int, name: String) -> float:
	return dd[i * ND + DRIVES.find(name)]


func _draw_dream(i: int) -> void:
	dream_kind[i] = -1
	dream_status[i] = 0
	if age[i] < 18 or u("dream", i) >= float(spec["dream_share_adult"]["value"]):
		return
	var wts: Array = spec["dream_kind_weights_by_age"][age_band(age[i])]
	var x: float = u("dreamkind", i)
	var acc: float = 0.0
	for j: int in DREAMS.size():
		acc += float(wts[j])
		if x < acc:
			dream_kind[i] = j
			break
	if dream_kind[i] < 0:
		dream_kind[i] = DREAMS.size() - 1
	dream_importance[i] = clampf(0.4 + 0.4 * trait_of(i, "future_orientation") + 0.1 * normal("dreamimp", i), 0.1, 1.0)
	dream_progress[i] = clampf(0.3 * u("dreamprog", i), 0.0, 0.9)


## Weighted income rank within each prefecture (recognition's deficit reads it)
func _ranks() -> void:
	var by: Dictionary = {}
	for i: int in n:
		if not by.has(pref[i]):
			by[pref[i]] = []
		by[pref[i]].append(i)
	for code: int in by:
		var idx: Array = by[code]
		idx.sort_custom(func(a: int, b: int) -> bool: return income[a] < income[b] if income[a] != income[b] else pid[a] < pid[b])
		var tot: float = 0.0
		for i: int in idx:
			tot += weight[i]
		var acc: float = 0.0
		for i: int in idx:
			acc += weight[i]
			rank[i] = acc / tot


## Drive weights: the age base (T, patterned on needs.gd BASE_W) shifted by traits, plus keyed noise; sum 1, floor 0.005
func _compose_drives(i: int) -> void:
	var base: Array = spec["drive_base_by_age"][age_band(age[i])]
	var w := PackedFloat64Array()
	w.resize(ND)
	for d: int in ND:
		w[d] = float(base[d]) + 0.02 * normal("drivew", i, d)
	w[DRIVES.find("recognition")] += 0.06 * (trait_of(i, "competitiveness") - 0.5)
	w[DRIVES.find("growth")] += 0.06 * (trait_of(i, "openness") - 0.5)
	w[DRIVES.find("change")] += 0.06 * (trait_of(i, "openness") - 0.5) + 0.04 * (trait_of(i, "fairness") - 0.5)
	w[DRIVES.find("contribution")] += 0.06 * (trait_of(i, "cooperativeness") - 0.5)
	w[DRIVES.find("belonging")] += 0.06 * (trait_of(i, "sociability") - 0.5)
	w[DRIVES.find("autonomy")] += 0.06 * (trait_of(i, "risk_tolerance") - 0.5) - 0.04 * (trait_of(i, "authority_attitude") - 0.5)
	w[DRIVES.find("economic_security")] += 0.06 * (0.5 - trait_of(i, "risk_tolerance")) + 0.04 * (trait_of(i, "future_orientation") - 0.5)
	var tot: float = 0.0
	for d: int in ND:
		w[d] = maxf(0.005, w[d])
		tot += w[d]
	for d: int in ND:
		dw[i * ND + d] = w[d] / tot


## Emotional baselines from traits and the household (T); emotions start at the baseline; expectations start at today's values
func _init_states(i: int) -> void:
	var b := PackedFloat64Array()
	b.resize(NE)
	b[EMOTIONS.find("joy")] = clampf(0.4 + 0.2 * (trait_of(i, "sociability") - 0.5) + 0.2 * (trait_of(i, "openness") - 0.5), 0.05, 0.95)
	b[EMOTIONS.find("sadness")] = clampf(0.15 + 0.2 * (0.5 - trait_of(i, "patience")), 0.02, 0.9)
	b[EMOTIONS.find("anger")] = clampf(0.1 + 0.2 * (trait_of(i, "competitiveness") - 0.5) + 0.1 * (0.5 - trait_of(i, "patience")), 0.02, 0.9)
	b[EMOTIONS.find("anxiety")] = clampf(0.25 + 0.3 * (0.5 - trait_of(i, "risk_tolerance")) + 0.1 * (0.5 - trait_of(i, "trust_in_others")) + 0.1 * health[i], 0.02, 0.95)
	b[EMOTIONS.find("fear")] = clampf(0.1 + 0.2 * (0.5 - trait_of(i, "risk_tolerance")), 0.02, 0.9)
	b[EMOTIONS.find("relief")] = 0.2
	b[EMOTIONS.find("hope")] = clampf(0.4 + 0.3 * (trait_of(i, "openness") - 0.5) + 0.2 * (trait_of(i, "future_orientation") - 0.5) - 0.003 * maxf(0.0, age[i] - 40), 0.05, 0.95)
	b[EMOTIONS.find("loneliness")] = clampf(0.25 + 0.3 * (0.5 - trait_of(i, "sociability")) + (0.15 if hh_kind[i] == HK_SINGLE else 0.0), 0.02, 0.95)
	b[EMOTIONS.find("discontent")] = clampf(0.2 + 0.2 * (trait_of(i, "competitiveness") - 0.5) + 0.2 * (trait_of(i, "fairness") - 0.5) * (1.0 - rank[i]), 0.02, 0.95)
	b[EMOTIONS.find("trust")] = trait_of(i, "trust_in_others")
	for e: int in NE:
		emo_base[i * NE + e] = b[e]
		emo[i * NE + e] = b[e]
	q_income[i] = income[i]
	q_price[i] = 0.02
	q_job[i] = 1.0 if (employment[i] == EMP_REGULAR or employment[i] == EMP_NONREGULAR) else 0.0
	mem_head[i] = 0
	for k: int in K_MEM:
		mem_kind[i * K_MEM + k] = -1
	plan[i] = 1
	search[i] = 0
	flags[i] = 0
	last_action[i] = ACT.A_KEEP
	for a: int in ACT.NA:
		q_act[i * ACT.NA + a] = 0.0
	_deficits(i)
	pressure_prev[i] = pressure(i)


## The household's monthly cost of living at today's prices (S: 家計調査), per member share
func cost_of_living(i: int) -> float:
	return _cost(hh_kind[i], hh_size[i])


func _cost(hk: int, hs: float) -> float:
	var c: Dictionary = spec["consumption_man_yen_month"]
	var hh: float = float(c["single"]) if hk == HK_SINGLE else float(c["two_plus"]) + float(c["per_extra_member"]) * maxf(0.0, hs - 2.0)
	return hh * price_index


## The view's forms of cost_of_living, trait_of and believed_cost_rise (§14.1 T2.R 4″)
func _cost_v(v: RefCounted) -> float:
	return _cost(v.n("hh_kind"), v.f("hh_size"))


func _trait_v(v: RefCounted, name: String) -> float:
	return v.f("traits", TRAITS.find(name))


func _food_rise_v(v: RefCounted) -> float:
	return v.f("belief", 0) if v.n("belief_known", 0) == 1 else 0.0


## Drive deficits from the person's situation (0..1): what the situation leaves unmet, read every month
func _deficits(i: int) -> void:
	var ev := PackedFloat64Array()
	ev.resize(NE)
	for e0: int in NE:
		ev[e0] = emo[i * NE + e0]
	var d: PackedFloat64Array = deficit_values(SV.new().of_person(self, i), ev, skill[i], debt[i])
	for k: int in ND:
		dd[i * ND + k] = d[k]


## The deficits as values (T2.R 4′; T2.R 4″ the state view v): the state with its emotions ev, skill sk and debt dbt as given; reads,
## writes nothing
func deficit_values(v: RefCounted, ev: PackedFloat64Array, sk: float, dbt: float) -> PackedFloat64Array:
	var e: int = v.n("employment")
	# the cost of living as the person BELIEVES it: the believed food price rise on the food share (Phase 3/5: felt, not true)
	var cost: float = _cost_v(v)
	cost *= 1.0 + v.f("basket", 0) * _food_rise_v(v)
	# a household's income is roughly its size times a member's, for the earning ages; children and students lean on it
	var hk: int = v.n("hh_kind")
	var hh_income: float = v.f("income") * (1.0 if hk == HK_SINGLE else minf(v.f("hh_size"), 2.0)) if v.n("age") >= 22 else cost * 0.9
	var cover: float = hh_income / maxf(1e-6, cost)
	var fl: int = v.n("flags")
	var d := PackedFloat64Array()
	d.resize(ND)
	d[D_SURVIVAL] = clampf(0.15 * v.n("health") + 0.4 * maxf(0.0, 1.0 - cover), 0.0, 1.0)
	d[D_SECURITY] = clampf(0.5 * maxf(0.0, 1.2 - cover) + (0.5 if e == EMP_UNEMPLOYED else 0.0) + (0.15 if e == EMP_NONREGULAR else 0.0) + 0.1 * minf(1.0, dbt / maxf(1.0, 24.0 * v.f("income") + 1.0)), 0.0, 1.0)
	d[D_BELONGING] = clampf((0.5 if hk == HK_SINGLE else 0.2) + 0.2 * (0.5 - v.f("pref_social")) + (0.2 if e == EMP_UNEMPLOYED else 0.0) - 0.04 * v.contacts(), 0.0, 1.0)
	d[D_RECOGNITION] = clampf(1.0 - v.f("rank"), 0.0, 1.0) * (0.6 + 0.4 * _trait_v(v, "competitiveness"))
	d[D_AUTONOMY] = [0.3, 0.5, 0.6, 0.8, 0.5, 0.3][e]
	d[D_GROWTH] = clampf(1.0 - sk / 100.0, 0.0, 1.0) * (0.5 + _trait_v(v, "openness"))
	var pl: int = v.n("plan")
	d[D_ENJOYMENT] = clampf(0.7 - v.f("basket", 2) * 3.0 - 0.2 * ev[EMOTIONS.find("joy")] - (0.2 if fl & F_REST else 0.0) - (0.25 if pl == 2 else 0.0) + (0.1 if pl == 0 else 0.0), 0.0, 1.0)
	var ag: int = v.n("age")
	d[D_FAMILY] = clampf((0.7 if (ag >= 25 and ag <= 45 and hk <= HK_COUPLE) else 0.2) + (0.2 if hk == HK_SINGLE_PARENT else 0.0) - (0.3 if fl & F_SUPPORTED else 0.0), 0.0, 1.0)
	if fl & F_SOCIALISED:
		d[D_BELONGING] = maxf(0.0, d[D_BELONGING] - 0.2)
	var mem: int = v.memberships()
	d[D_BELONGING] = maxf(0.0, d[D_BELONGING] - 0.1 * mem)
	d[D_CONTRIBUTION] = maxf(0.0, 0.3 + 0.2 * (_trait_v(v, "cooperativeness") - 0.5) - 0.08 * mem)
	d[D_CHANGE] = clampf(0.3 * ev[EMOTIONS.find("discontent")] + 0.3 * ev[EMOTIONS.find("anger")] + 0.2 * (1.0 - _trait_v(v, "authority_attitude")) - (0.1 if v.in_movement() else 0.0), 0.0, 1.0)
	for k: int in ND:
		d[k] = clampf(d[k], 0.0, 1.0)
	return d


## The drive pressure a person feels: sum of weight x deficit (Phase 2 reads it to score actions)
func pressure(i: int) -> float:
	var p: float = 0.0
	for k: int in ND:
		p += dw[i * ND + k] * dd[i * ND + k]
	return p


## The pensions' yearly revision (ISS_PHASE5_ECONOMY.md M002 batch G1; R68, 国民年金法 Art 27-27-5): each January the persons' price
## index, the economy's wage index and the weighted persons 20-59 are recorded; each April the new and the existing pensioners'
## indices move by pension_revision on the year's changes (the start's first April by the published FY2024 rate), and every retired
## person's pension is repaid
func _pension_month() -> void:
	var pr: Dictionary = spec["pension_rule"]["value"]
	if month % 12 == 0:
		var insured: float = 0.0
		for i: int in n:
			if age[i] >= 20 and age[i] < 60:
				insured += weight[i]
		pension["jan_prev"] = (pension["jan"] as Array).duplicate()
		pension["jan"] = [price_index, wage_index, insured]
	if month % 12 != int(pr["revision_month_index"]):
		return
	var r: Array
	var prev: Array = pension["jan_prev"]
	var now: Array = pension["jan"]
	if prev.is_empty() or now.is_empty():
		var first: float = float(pr["first_revision"])
		r = [first, first, float(pension["carry"]), 0.0, 0.0, 0.0]
	else:
		var cpi: float = float(now[0]) / float(prev[0]) - 1.0
		var wg: float = float(now[1]) / float(prev[1]) - 1.0
		var slide: float = (float(now[2]) / float(prev[2]) - 1.0 if float(prev[2]) > 0.0 else 0.0) + float(pr["life_expectancy_slide"])
		r = pension_revision(cpi, wg, minf(0.0, slide), float(pension["carry"]))
		r.append_array([cpi, wg, slide])
	pension["new"] = float(pension["new"]) * (1.0 + float(r[0]))
	pension["old"] = float(pension["old"]) * (1.0 + float(r[1]))
	pension["carry"] = float(r[2])
	(pension["log"] as Array).append([month, r[0], r[1], r[2]])
	for i2: int in n:
		if employment[i2] == EMP_RETIRED:
			repay(i2)


## R68's rule for one April (the law as of 2024-01): the base rate of the new pensioners is the wage change; the existing pensioners'
## is the price change when wages rise faster and the wage change otherwise (the lower of the two); the macro slide (this year's,
## negative, plus the carry) applies only to a positive base rate and never takes it below 0; what it cannot take is carried, read on
## the new pensioners' rate. Returns [new rate, existing rate, carry]
static func pension_revision(cpi: float, wage: float, slide: float, carry: float) -> Array:
	var total: float = slide + carry
	var base_new: float = wage
	var base_old: float = minf(cpi, wage)
	var rate_new: float = maxf(0.0, base_new + total) if base_new > 0.0 else base_new
	var rate_old: float = maxf(0.0, base_old + total) if base_old > 0.0 else base_old
	var used: float = rate_new - base_new if base_new > 0.0 else 0.0
	return [rate_new, rate_old, minf(0.0, total - used)]


## The persons' mean finding rate this month (M002 G7): f x the search factor, weighted over the unemployed; separation at this rate x
## u / (1 - u) makes the persons' unemployment share converge to the economy's u at any search share
## Why not f alone: the share then converged to u only when 40% of the unemployed searched (4.1% with none, 1.6% with all)
func _mean_finding(f: float) -> float:
	var wu: float = 0.0
	var wf: float = 0.0
	for i: int in n:
		if employment[i] == EMP_UNEMPLOYED:
			wu += weight[i]
			wf += weight[i] * (ACT.SEARCH_BOOST if search[i] == 1 else ACT.NO_SEARCH)
	return f * wf / wu if wu > 0.0 else f


## A month's saving booked in full (ISS_TIERED_POPULATION.md §13.7, SB10): to the assets, and a shortfall beyond them to the debt
## (T: consumer credit), so the change of assets less the change of debt is the saving
## Why not half the surplus with the assets floored at 0 (before): half of every surplus and every shortfall beyond the assets vanished
func book_saving(i: int, save: float) -> void:
	var ad: PackedFloat64Array = saving_values(assets[i], debt[i], save)
	assets[i] = ad[0]
	debt[i] = ad[1]


## book_saving as values: [the assets, the debt] after a month's saving from (a0, d0); pure
static func saving_values(a0: float, d0: float, save: float) -> PackedFloat64Array:
	var a: float = a0 + save
	var d: float = d0
	if a < 0.0:
		d -= a
		a = 0.0
	return PackedFloat64Array([a, d])


## One month for every person. env: {"inflation_month": CPI rate for the month, "food_price_yoy", "unemployment_rate" (the economy's),
## "levers": [lever ids applied this month], "cohort": the status layer's age x sex counts now (the yearly raking; the start's without)}
func step(env: Dictionary) -> void:
	var infl: float = float(env.get("inflation_month", 0.02 / 12.0))
	price_index *= 1.0 + infl
	wage_index = float(env.get("wage_index", wage_index))
	_pension_month()
	var ur: float = float(env.get("unemployment_rate", float(spec["unemployment_rate_start"]["value"])))
	var f: float = float(spec["job_finding_rate_month"]["value"])
	var yoy_true: float = float(env.get("food_price_yoy", 0.0))
	var levers: Array = env.get("levers", [])
	var counts: Dictionary = {}
	var dec_counts: Dictionary = {}
	var ref_counts: Dictionary = {}
	# A every person decides on last month's state (candidates -> feasibility -> score -> one keyed draw -> own effects)
	for i: int in n:
		# 0 the decision (Phase 2): candidates -> feasibility -> score -> one keyed softmax draw -> the action's own effects
		var ch: Dictionary = ACT.choose(self, i, month)
		var act: int = int(ch["action"])
		ACT.apply(self, i, act, month)
		if act == ACT.A_FOUND:
			GRP.found_movement(self, i, counts)
		last_action[i] = act
		_count_decision(dec_counts, act, int(ch["top_drive"]), String(ch["modulated_by"]), i)
		for r: Array in ch["refused"]:
			var rk: String = "%d|%s" % [int(r[0]), String(r[1])]
			ref_counts[rk] = int(ref_counts.get(rk, 0)) + 1
		if trace_pids.has(pid[i]):
			trace.append([month, pid[i], "decision", ACT.ACTIONS[act], float(ch["u"]), "top drive %s%s, %d options" % [DRIVES[int(ch["top_drive"])] if int(ch["top_drive"]) >= 0 else "none", (" (" + String(ch["modulated_by"]) + ")") if String(ch["modulated_by"]) != "" else "", int(ch["options"])]])
	# B the month's interactions (socialize partners, family support, help asked), what people come to believe, the groups
	REL.interact(self, counts)
	REL.learn(self, {"food_price_yoy": yoy_true, "unemployment_rate": ur}, counts)
	GRP.step(self, counts)
	# Why after the decisions (G7a): they reset and set the search states the finds use; read before them, f̄ took last month's states
	# and the persons' unemployment settled at about 0.75 of u (M2-3's trace)
	var s: float = _mean_finding(f) * ur / maxf(1e-6, 1.0 - ur)
	# C what the month does to each person
	var pools: Dictionary = {}
	for i0: int in n:
		if not pools.has(pref[i0]):
			pools[pref[i0]] = []
		pools[pref[i0]].append(i0)
	for i: int in n:
		# 1 the year turns on the person's own month: age, death (the cohort's hazard), transitions of status, the contacts renewed
		if month % 12 == int(pid[i] % 12):
			_year(i, counts)
			if contact_renewal:
				REL.replenish(self, i, pools[pref[i]])
		# 2 the economy's labour market decides this person's job this month (labour.gd owns employment: survey 2)
		LAB.person_month(self, i, s, f, counts)
		apply_month_values(i, month_values(SV.new().of_person(self, i), infl, levers), counts)
	if households:
		LC.grade_birthday(self)
		LC.month(self, counts)
	reweight(env.get("cohort", PackedFloat64Array()))
	if households:
		LC.quartile_cuts(self)
	GRP.refresh_weights(self)
	_ranks()
	for key: String in dec_counts:
		decisions.append(dec_counts[key])
	for rk: String in ref_counts:
		var parts: PackedStringArray = rk.split("|")
		refusals.append({"month": month, "action": ACT.ACTIONS[int(parts[0])], "why": parts[1], "count": int(ref_counts[rk])})
	for kind: String in counts:
		var c: Dictionary = counts[kind]
		events.append({"month": month, "kind": kind, "count": int(c["n"]), "weight": float(c["w"]), "mean_move": float(c["move"]) / maxf(1.0, float(c["n"])), "why": String(c["why"])})
	if tiers:
		TR.step(self, env)
	month += 1


## Steps 3-10 of the month as values, after the year and the labour month (§14.1, T2.R 4′), on the state view v of a person or a point
## (T2.R 4″): reads the state and writes nothing; apply_month_values writes them. Why not the effects written in place (T2.R 4,
## 76bac58f): a point takes the same month's values, and no tier code writes a person's arrays
func month_values(v: RefCounted, infl: float, levers: Array) -> Dictionary:
	var ev := PackedFloat64Array()
	ev.resize(NE)
	for e: int in NE:
		ev[e] = v.f("emo", e)
	var rec: Array = []
	# 3 income received at this month's prices: the surprise against the expectation moves emotions through loss aversion
	# Why nominal against the expected nominal: the slow loss of real income to prices is felt through the cost of living in the
	# deficits; here the surprise is what the pay packet does against what the person expected it to do (a job change, a raise)
	var qi: float = v.f("q_income") * (1.0 + v.f("q_price") / 12.0)
	var surprise: float = (v.f("income") - qi) / maxf(1.0, qi) if v.n("age") >= 22 else 0.0
	if surprise < -0.02:
		_move_v(ev, rec, "sadness", 0.6 * v.f("lam") * -surprise, "income_below_expectation", "loss_aversion")
		_move_v(ev, rec, "anxiety", 0.4 * v.f("lam") * -surprise * (1.5 - _trait_v(v, "risk_tolerance")), "income_below_expectation", "risk_tolerance")
	elif surprise > 0.02:
		_move_v(ev, rec, "joy", 0.4 * surprise, "income_above_expectation", "")
		_move_v(ev, rec, "hope", 0.2 * surprise * (0.5 + _trait_v(v, "openness")), "income_above_expectation", "openness")
	# 4 prices: a food price rise bites by the food share of the basket and the cover of the cost of living. Why the belief and
	#   not the true change (Phase 3): a person feels the prices it knows about; the register, a contact or nothing told it
	var yoy: float = _food_rise_v(v)
	if yoy > 0.03:
		var bite: float = (yoy - 0.03) * v.f("basket", 0) / 0.26 * minf(2.0, _cost_v(v) / maxf(1.0, v.f("income") + 1.0))
		_move_v(ev, rec, "anxiety", 0.5 * bite * (1.5 - _trait_v(v, "risk_tolerance")), "food_price_rise", "risk_tolerance")
		_move_v(ev, rec, "discontent", 0.4 * bite, "food_price_rise", "")
		_move_v(ev, rec, "anger", 0.3 * bite * _trait_v(v, "fairness"), "food_price_rise", "fairness")
	# 5 policy events the person feels (levers applied this month)
	for lid: String in levers:
		match lid:
			"consumption_tax_rate":
				_move_v(ev, rec, "anger", 0.12 * (1.5 - _trait_v(v, "authority_attitude")), "tax_rise", "authority_attitude")
				_move_v(ev, rec, "discontent", 0.1, "tax_rise", "")
			"child_allowance":
				if v.n("hh_kind") == HK_COUPLE_CHILDREN or v.n("hh_kind") == HK_SINGLE_PARENT:
					_move_v(ev, rec, "joy", 0.1, "child_allowance", "")
					_move_v(ev, rec, "trust", 0.05, "child_allowance", "")
			"fuel_subsidy", "rice_stock_release":
				_move_v(ev, rec, "relief", 0.05, lid, "")
	# 5b a month without work erodes skill (T: -0.5 a month; the lag of unemployment into future pay)
	var sk: float = maxf(0.0, v.f("skill") - 0.5) if v.n("employment") == EMP_UNEMPLOYED else v.f("skill")
	# 6 savings and the dream
	var factor: float = [0.85, 1.0, 1.2][v.n("plan")]
	var save: float = v.f("income") - _cost_v(v) / maxf(1.0, v.f("hh_size")) * factor
	var ad: PackedFloat64Array = saving_values(v.f("assets"), v.f("debt"), save)
	var a: float = ad[0]
	var dbt: float = ad[1]
	var dream: Dictionary = _dream_values(v, save, a, ev, rec)
	# 7 loneliness rises for the single and sociable, eases with household and with having met someone this month
	if v.n("hh_kind") == HK_SINGLE and v.n("met") == 0:
		_move_v(ev, rec, "loneliness", 0.02 * v.f("pref_social"), "living_alone", "sociability")
	# 8 memory: expectations learn (memory.gd form, loss aversion when worse)
	var lr: float = float(spec["expectation_learning_rate"]["value"])
	var di: float = v.f("income") - v.f("q_income")
	var jobnow: float = 1.0 if (v.n("employment") == EMP_REGULAR or v.n("employment") == EMP_NONREGULAR) else 0.0
	# 9 decay toward the baseline, then the deficits on the month's state
	var dec: Dictionary = spec["emotion_decay_month"]
	for e2: int in NE:
		ev[e2] = clampf(ev[e2] + float(dec[EMOTIONS[e2]]) * (v.f("emo_base", e2) - ev[e2]), 0.0, 1.0)
	var d: PackedFloat64Array = deficit_values(v, ev, sk, dbt)
	# 10 the action's payoff learned from what the month did to the pressure (memory.gd form, loss aversion when worse)
	var pr: float = 0.0
	for k: int in ND:
		pr += v.f("dw", k) * d[k]
	var r: float = v.f("pressure_prev") - pr
	var la: int = v.n("last_action")
	var qa: float = v.f("q_act", la)
	return {"emo": ev, "rec": rec, "skill": sk, "assets": a, "debt": dbt, "dream": dream,
		"q_income": v.f("q_income") + lr * di * (v.f("lam") if di < 0.0 else 1.0), "q_price": v.f("q_price") + lr * (infl * 12.0 - v.f("q_price")),
		"q_job": v.f("q_job") + lr * (jobnow - v.f("q_job")) * (v.f("lam") if jobnow < v.f("q_job") else 1.0), "dd": d,
		"q_act": qa + 0.3 * (r - qa) * (v.f("lam") if r < qa else 1.0), "pressure": pr}


## month_values written by their owners: this module's arrays, the move records replayed into the counts and the trace in order,
## relations.gd's met
func apply_month_values(i: int, v: Dictionary, counts: Dictionary) -> void:
	var ev: PackedFloat64Array = v["emo"]
	for e: int in NE:
		emo[i * NE + e] = ev[e]
	for r: Array in v["rec"]:
		if String(r[0]) == "move":
			_count(counts, String(r[1]) + ":" + String(r[2]), i, float(r[3]), "scaled by " + String(r[4]) if String(r[4]) != "" else "flat")
			if trace_pids.has(pid[i]):
				trace.append([month, pid[i], String(r[1]), String(r[2]), float(r[3]), String(r[4])])
		else:
			_count(counts, String(r[1]), i, 0.0, String(r[2]))
	skill[i] = float(v["skill"])
	assets[i] = float(v["assets"])
	debt[i] = float(v["debt"])
	var dr: Dictionary = v["dream"]
	dream_progress[i] = float(dr["progress"])
	dream_blocked[i] = int(dr["blocked"])
	dream_importance[i] = float(dr["importance"])
	dream_status[i] = int(dr["status"])
	for m: Array in dr["remember"]:
		_remember(i, String(m[0]), float(m[1]))
	q_income[i] = float(v["q_income"])
	q_price[i] = float(v["q_price"])
	q_job[i] = float(v["q_job"])
	REL.clear_met(self, i)
	var d: PackedFloat64Array = v["dd"]
	for k: int in ND:
		dd[i * ND + k] = d[k]
	q_act[i * ACT.NA + last_action[i]] = float(v["q_act"])
	pressure_prev[i] = float(v["pressure"])


## _move on a value vector: the emotion clamped to [0, 1], the applied move recorded for the counts and the trace
func _move_v(ev: PackedFloat64Array, rec: Array, emotion_name: String, amount: float, why: String, scaled_by: String) -> void:
	if absf(amount) < 1e-9:
		return
	var k: int = EMOTIONS.find(emotion_name)
	var before: float = ev[k]
	ev[k] = clampf(before + amount, 0.0, 1.0)
	rec.append(["move", why, emotion_name, ev[k] - before, scaled_by])


func labour_from_rates(i: int) -> int:
	return EMP_NONREGULAR if below("nonreg2", i, month, 0, h_nonregular(sex[i])) else EMP_REGULAR


## The probability that a job taken by a person of sex s is non-regular (the persons spec's share); pure (§14.1)
func h_nonregular(s: int) -> float:
	return rone_out("h_nonregular", float(spec["non_regular_share"]["male"]) if s == MALE else float(spec["non_regular_share"]["female"]))


## The person's year: ageing; death, by the cohort's hazard with households off (the slot is reused by a newborn of the same prefecture,
## T: the sample keeps its size and weight) or by the life table with households on (life_course.dies; the dead are removed at the
## month's end, no slot is reused); the transitions at 15, 22 and 65 in both modes; the drive weights re-composed
func _year(i: int, counts: Dictionary) -> void:
	var a: int = age[i]
	if households:
		if LC.dies(self, i):
			return
	var q: float = h_death_off(a, sex[i])
	if not households and below("death", i, month, 0, q):
		_count(counts, "death", i, 0.0, "the cohort's qx (S)")
		_reborn(i)
		return
	age[i] = a + 1
	if households:
		LC.year_turn(self, i)
	if age[i] == 22 and employment[i] == EMP_STUDENT:
		_draw_attributes_education(i)
		LAB.enter_work(self, i, counts)
	elif age[i] == 15 and employment[i] == EMP_NONE:
		LC.enter_school(self, i)
	elif age[i] == 65 and (employment[i] == EMP_REGULAR or employment[i] == EMP_NONREGULAR or employment[i] == EMP_UNEMPLOYED):
		LC.retire(self, i, counts)
	elif employment[i] == EMP_REGULAR or employment[i] == EMP_NONREGULAR:
		income[i] = wage(i)   # the yearly pay: the economy's table x its wage index (Phase 5) x the skill
	skill[i] = minf(100.0, skill[i] + (0.8 if employment[i] <= EMP_NONREGULAR and employment[i] >= EMP_REGULAR else 0.2))
	_compose_drives(i)


## The year's death probability with households off: the cohort's q_x at single age a and sex s (§14.1, T2.R); pure
func h_death_off(a: int, s: int) -> float:
	return rone_out("h_death_off", qx[mini(a, AGES - 1) * SEXES + s] if qx.size() > 0 else 0.0)


func _draw_attributes_education(i: int) -> void:
	education[i] = pick(spec["education_shares_by_age"]["22_34"], EDUCATION, u("edu22", i))
	skill[i] = clampf(20.0 + 15.0 * education[i] + 10.0 * normal("skill22", i), 0.0, 100.0)


func _reborn(i: int) -> void:
	var code: int = pref[i]
	var k: int = k_in_pref[i]
	age[i] = 0
	sex[i] = KEYED.below(2, seed_v, "rebornsex", code, k, month)
	pid[i] = KEYED.pid(seed_v, code, base_year + month / 12, sex[i], 100000 + k * 64 + month % 64)
	_draw_attributes(i)
	_draw_traits(i)
	_draw_dream(i)
	_compose_drives(i)
	_init_states(i)
	REL.drop_all(self, i)
	REL.forget(self, i)
	for m: int in GRP.M:
		if member_of[i * GRP.M + m] >= 0:
			GRP.leave(self, i, member_of[i * GRP.M + m])
	GRP.clear_cover(self, i)


## An event's emotional reading, scaled by traits and loss aversion (the same event moves people differently); recorded
func event(i: int, kind: String, counts: Dictionary) -> void:
	match kind:
		"job_loss":
			_move(i, "anxiety", 0.35 * lam[i] / 2.0 * (1.5 - trait_of(i, "risk_tolerance")), kind, "risk_tolerance x loss_aversion", counts)
			_move(i, "sadness", 0.25 * lam[i] / 2.0, kind, "loss_aversion", counts)
			_move(i, "anger", 0.15 * trait_of(i, "fairness"), kind, "fairness", counts)
			_move(i, "discontent", 0.2, kind, "", counts)
			_move(i, "hope", -0.15 * (1.5 - trait_of(i, "openness")), kind, "openness", counts)
		"job_found":
			_move(i, "relief", 0.4, kind, "", counts)
			_move(i, "joy", 0.3 * (0.5 + trait_of(i, "sociability")), kind, "sociability", counts)
			_move(i, "hope", 0.2, kind, "", counts)
			_move(i, "anxiety", -0.25, kind, "", counts)
		"entered_work":
			_move(i, "hope", 0.2, kind, "", counts)
			_move(i, "anxiety", 0.1 * (1.5 - trait_of(i, "risk_tolerance")), kind, "risk_tolerance", counts)
		"retired":
			_move(i, "relief", 0.2, kind, "", counts)
			_move(i, "anxiety", 0.1 * (1.5 - trait_of(i, "future_orientation")), kind, "future_orientation", counts)
	_remember(i, kind, -1.0 if kind == "job_loss" else 1.0)


func _move(i: int, emotion_name: String, amount: float, why: String, scaled_by: String, counts: Dictionary) -> void:
	if absf(amount) < 1e-9:
		return
	var k: int = i * NE + EMOTIONS.find(emotion_name)
	var before: float = emo[k]
	emo[k] = clampf(before + amount, 0.0, 1.0)
	_count(counts, why + ":" + emotion_name, i, emo[k] - before, "scaled by " + scaled_by if scaled_by != "" else "flat")
	if trace_pids.has(pid[i]):
		trace.append([month, pid[i], why, emotion_name, emo[k] - before, scaled_by])


func move_emotion(i: int, emotion_name: String, amount: float, why: String, scaled_by: String, counts: Dictionary) -> void:
	_move(i, emotion_name, amount, why, scaled_by, counts)


func count_kind(counts: Dictionary, kind: String, i: int, move: float, why: String) -> void:
	_count(counts, kind, i, move, why)


func in_movement(i: int) -> bool:
	for m: int in GRP.M:
		var gid: int = member_of[i * GRP.M + m]
		if gid >= 0 and int(groups[gid]["kind"]) == GRP.G_MOVEMENT:
			return true
	return false


func contact_count(i: int) -> int:
	var k: int = 0
	for c: int in REL.C:
		if contact_idx[i * REL.C + c] >= 0:
			k += 1
	return k


func _count_decision(dc: Dictionary, act: int, top: int, mod: String, i: int) -> void:
	var key: String = ACT.ACTIONS[act]
	if not dc.has(key):
		dc[key] = {"month": month, "action": key, "count": 0, "weight": 0.0, "top_drives": {}, "modulated": {}}
	var row: Dictionary = dc[key]
	row["count"] = int(row["count"]) + 1
	row["weight"] = float(row["weight"]) + weight[i]
	var td: String = DRIVES[top] if top >= 0 else "none"
	row["top_drives"][td] = int(row["top_drives"].get(td, 0)) + 1
	if mod != "":
		row["modulated"][mod] = int(row["modulated"].get(mod, 0)) + 1


func _count(counts: Dictionary, kind: String, i: int, move: float, why: String) -> void:
	if not counts.has(kind):
		counts[kind] = {"n": 0, "w": 0.0, "move": 0.0, "why": why}
	var c: Dictionary = counts[kind]
	c["n"] = int(c["n"]) + 1
	c["w"] = float(c["w"]) + weight[i]
	c["move"] = float(c["move"]) + move


func _remember(i: int, kind: String, valence: float) -> void:
	var h: int = mem_head[i]
	var k: int = i * K_MEM + h
	mem_month[k] = month
	mem_kind[k] = ["job_loss", "job_found", "entered_work", "retired", "dream_achieved", "dream_abandoned", "changed_job"].find(kind)
	mem_val[k] = valence
	mem_head[i] = (h + 1) % K_MEM


## The dream as values (month_values): savings above the cost carry it toward its cost; no progress for a year erodes its importance;
## below 0.2 it is abandoned with the cause recorded; achieved at 1.0 (a person living on assets, a_new after the month's saving, is not
## blocked)
func _dream_values(v: RefCounted, save: float, a_new: float, ev: PackedFloat64Array, rec: Array) -> Dictionary:
	var out: Dictionary = {"progress": v.f("dream_progress"), "blocked": v.n("dream_blocked"), "importance": v.f("dream_importance"), "status": v.n("dream_status"), "remember": []}
	var dk: int = v.n("dream_kind")
	if dk < 0 or v.n("dream_status") != 0:
		return out
	var cost: float = float(spec["dream_cost_man_yen"][DREAMS[dk]])
	if save > 0.0:
		out["progress"] = minf(1.0, v.f("dream_progress") + (1.0 if v.n("flags") & F_DREAM else 0.5) * save / cost * (0.5 + _trait_v(v, "patience")))
		out["blocked"] = 0
	elif a_new > 6.0 * _cost_v(v):
		# living on savings is not a blocked dream (a pensioner drawing down assets, T: six months of cost as the line)
		out["blocked"] = 0
	else:
		out["blocked"] = v.n("dream_blocked") + 1
		if int(out["blocked"]) >= 12:
			out["importance"] = maxf(0.0, v.f("dream_importance") - 0.05 * (1.5 - _trait_v(v, "patience")))
	if float(out["progress"]) >= 1.0:
		out["status"] = 1
		_move_v(ev, rec, "joy", 0.5, "dream_achieved", "")
		_move_v(ev, rec, "hope", 0.3, "dream_achieved", "")
		(out["remember"] as Array).append(["dream_achieved", 2.0])
	elif float(out["importance"]) < 0.2:
		out["status"] = 2
		_move_v(ev, rec, "sadness", 0.3 * v.f("lam") / 2.0, "dream_abandoned", "loss_aversion")
		_move_v(ev, rec, "discontent", 0.2, "dream_abandoned", "")
		rec.append(["count", "dream_abandoned:" + DREAMS[dk], "no savings for %d months, patience %.2f" % [int(out["blocked"]), _trait_v(v, "patience")]])
		(out["remember"] as Array).append(["dream_abandoned", -2.0])
	return out


## What the persons supply to the economy (Phase 5): the weighted food consumption plan (the plan's factor times the person's own
## response to the believed price) against the start's, the search share of the labour force, the share of unions raising a wage demand
## this month
func food_plan() -> float:
	var tot: float = 0.0
	for i: int in n:
		if age[i] < 18:
			continue
		var factor: float = [0.85, 1.0, 1.2][plan[i]] * food_price_response(i)
		tot += weight[i] * cost_of_living(i) / price_index / maxf(1.0, hh_size[i]) * factor * basket[i * 4]
	return tot


func supply() -> Dictionary:
	if is_nan(food_plan_start):
		food_plan_start = food_plan()
	var lf: float = 0.0
	var searching: float = 0.0
	for i: int in n:
		if employment[i] >= EMP_REGULAR and employment[i] <= EMP_UNEMPLOYED:
			lf += weight[i]
			if search[i] == 1:
				searching += weight[i]
	var unions: int = 0
	var demanding: int = 0
	for g: Dictionary in groups:
		if int(g["kind"]) == GRP.G_UNION and int(g["members"]) > 0:
			unions += 1
	for r: Dictionary in group_log:
		if String(r["kind"]) == "wage_demand" and int(r["month"]) == month - 1:
			demanding += 1
	return {"search_share": searching / maxf(1.0, lf), "wage_demand_share": float(demanding) / maxf(1.0, float(unions)), "scales": {"food_products": food_plan() / maxf(1e-9, food_plan_start)}}


## Weighted quantiles of a value over a set of persons (the aggregate that keeps the distribution, survey 1.7)
func quantiles(values: PackedFloat64Array, idx: Array, qs: Array = [0.1, 0.5, 0.9]) -> Array:
	var rows: Array = []
	var tot: float = 0.0
	for i: int in idx:
		rows.append([values[i], weight[i], pid[i]])
		tot += weight[i]
	rows.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]) if float(a[0]) != float(b[0]) else int(a[2]) < int(b[2]))
	var out: Array = []
	for q: float in qs:
		var acc: float = 0.0
		var v: float = rows[rows.size() - 1][0] if rows.size() > 0 else 0.0
		for r: Array in rows:
			acc += float(r[1])
			if acc >= q * tot:
				v = float(r[0])
				break
		out.append(v)
	return out


func emotion_column(name: String) -> PackedFloat64Array:
	var e: int = EMOTIONS.find(name)
	var out := PackedFloat64Array()
	out.resize(n)
	for i: int in n:
		out[i] = emo[i * NE + e]
	return out


func deficit_column(name: String) -> PackedFloat64Array:
	var d: int = DRIVES.find(name)
	var out := PackedFloat64Array()
	out.resize(n)
	for i: int in n:
		out[i] = dd[i * ND + d]
	return out


## The only outward face: weighted aggregates per prefecture (or all), no person-level value
func summary(code: int = -1) -> Dictionary:
	var idx: Array = []
	var tot: float = 0.0
	var unemp: float = 0.0
	var lf: float = 0.0
	var dreams_active: float = 0.0
	var pres: float = 0.0
	for i: int in n:
		if code >= 0 and pref[i] != code:
			continue
		idx.append(i)
		tot += weight[i]
		if employment[i] == EMP_UNEMPLOYED:
			unemp += weight[i]
		if employment[i] >= EMP_REGULAR and employment[i] <= EMP_UNEMPLOYED:
			lf += weight[i]
		if dream_kind[i] >= 0 and dream_status[i] == 0:
			dreams_active += weight[i]
		pres += weight[i] * pressure(i)
	var out: Dictionary = {"persons": idx.size(), "population": tot, "unemployment_rate": unemp / maxf(1.0, lf), "dreams_active_share": dreams_active / maxf(1.0, tot), "pressure_mean": pres / maxf(1.0, tot)}
	var inc := PackedFloat64Array()
	inc.resize(n)
	for i: int in idx:
		inc[i] = income[i] / price_index
	out["real_income_p10_p50_p90"] = quantiles(inc, idx)
	for name: String in ["anxiety", "discontent", "hope", "joy", "trust"]:
		out[name + "_p10_p50_p90"] = quantiles(emotion_column(name), idx)
	out["economic_security_deficit_p10_p50_p90"] = quantiles(deficit_column("economic_security"), idx)
	var acts: Dictionary = {}
	for i: int in idx:
		var nm: String = ACT.ACTIONS[last_action[i]]
		acts[nm] = float(acts.get(nm, 0.0)) + weight[i] / maxf(1.0, tot)
	out["last_action_shares"] = acts
	var known: float = 0.0
	var cc: float = 0.0
	var bel := PackedFloat64Array()
	bel.resize(n)
	var known_idx: Array = []
	for i: int in idx:
		cc += weight[i] * contact_count(i)
		if belief_known[i * REL.NF] == 1:
			known += weight[i]
			bel[i] = belief[i * REL.NF]
			known_idx.append(i)
	out["contacts_mean"] = cc / maxf(1.0, tot)
	out["food_price_known_share"] = known / maxf(1.0, tot)
	out["food_price_belief_p10_p50_p90"] = quantiles(bel, known_idx) if known_idx.size() > 0 else [0.0, 0.0, 0.0]
	var mem_w: float = 0.0
	var mov_w: float = 0.0
	for i: int in idx:
		if GRP.memberships(self, i) > 0:
			mem_w += weight[i]
		if in_movement(i):
			mov_w += weight[i]
	out["in_a_group_share"] = mem_w / maxf(1.0, tot)
	out["in_a_movement_share"] = mov_w / maxf(1.0, tot)
	return out


static func _b64(arr: Variant) -> String:
	return Marshalls.raw_to_base64(arr.to_byte_array())


func to_dict() -> Dictionary:
	var packed := {"i64": {}, "i32": {}, "f64": {}}
	for f: Array in fields():
		packed[String(f[1])][String(f[0])] = _b64(get(String(f[0])))
	return {"state": state, "seed": seed_v, "base_year": base_year, "n": n, "month": month, "price_index": price_index, "wage_index": wage_index, "food_plan_start": food_plan_start, "pref_codes": pref_codes.duplicate(), "pref_pop": pref_pop.duplicate(),
		"pension": pension.duplicate(true), "i64": packed["i64"], "i32": packed["i32"], "f64": packed["f64"],
		"events": events.duplicate(true), "trace_pids": trace_pids.duplicate(), "trace": trace.duplicate(true), "decisions": decisions.duplicate(true), "refusals": refusals.duplicate(true),
		"groups": groups.duplicate(true), "group_log": group_log.duplicate(true)}.merged(_households_dict()).merged(_tiers_dict())


static func _unpack(b64: String, kind: String) -> Variant:
	var raw: PackedByteArray = Marshalls.base64_to_raw(b64)
	return raw.to_int64_array() if kind == "i64" else (raw.to_int32_array() if kind == "i32" else raw.to_float64_array())


## Why a key only when on: with households off the persons' state and digest must be the Phase 5 ones (the flag rule)
func _households_dict(numeric: bool = false) -> Dictionary:
	if not households:
		return {}
	var out := {}
	for h: Array in household_fields():
		if numeric and bool(h[4]):
			out[String(h[1])] = Array(get(String(h[0])))
		elif not numeric:
			out[String(h[1])] = _b64(get(String(h[0])))
	if numeric:
		out["life_log_n"] = life_log.size()
	else:
		out["n"] = hh_n
		out["next_k"] = next_k.duplicate()
		out["life_log"] = life_log.duplicate(true)
		out["lc_births"] = lc_births.duplicate(true)
	return {"households": out}


## Why a key only when on: with tiers off the state and digest must be the recorded ones (T1s-f)
func _tiers_dict(numeric: bool = false) -> Dictionary:
	if not tiers:
		return {}
	var out := {"n": tr_units, "k": tr_k, "key": tr_key.duplicate(), "count": tr_count.duplicate(), "age_counts": tr_age_counts.duplicate(),
		"never_married": tr_never_married.duplicate(), "pt_age": tr_pt_age.duplicate(), "hh_keys": tr_hh_keys.duplicate(),
		"hm_off": tr_hm_off.duplicate(), "hm_pt": tr_hm_pt.duplicate(), "hm_role": tr_hm_role.duplicate(), "hm_n": tr_hm_n.duplicate(),
		"cp_hh": tr_cp_hh.duplicate(), "cp_w": tr_cp_w.duplicate(), "cp_h": tr_cp_h.duplicate(), "cp_n": tr_cp_n.duplicate(),
		"pt_ms": tr_pt_ms.duplicate(), "married_apart": tr_married_apart.duplicate(), "tier_size": tr_tier_size.duplicate(), "indiv_unit": tr_indiv_unit.duplicate(),
		"instrument_factor": tr_instrument_factor.duplicate(), "pt_off": tr_pt_off.duplicate(), "pt_mass": tr_pt_mass.duplicate(),
		"mix_off": tr_mix_off.duplicate(), "mix_code": tr_mix_code.duplicate(), "mix_n": tr_mix_n.duplicate(), "pt_code": tr_pt_code.duplicate(),
		"indiv_code": tr_indiv_code.duplicate(), "phi": _pid_rows(tr_phi), "pension_own": _pid_rows(tr_pension),
		"pension_kind": _pid_rows(tr_pension_kind), "pt_id": tr_pt_id.duplicate(), "pt_jan": tr_pt_jan.duplicate(), "pt_old": tr_pt_old.duplicate(),
		"pt_next": tr_pt_next, "kb": tr_kb.duplicate(), "class_lines": tr_class_lines.duplicate(), "c": tr_c.duplicate(), "pt_q": tr_pt_q.duplicate(), "pt_muq": tr_pt_muq.duplicate(), "pt_mug": tr_pt_mug.duplicate(), "pt_rem": _rem_rows(tr_pt_rem), "cp_cap": _pid_rows(tr_cp_cap),
		"pt_ag": tr_pt_ag.duplicate(), "pt_jg": tr_pt_jg.duplicate(), "pt_og": tr_pt_og.duplicate(), "pt_T": tr_pt_T.duplicate()}
	var pts := {}
	for name: String in tr_points:
		pts[name] = tr_points[name].duplicate()
	out["points"] = pts
	var ins := {}
	for name2: String in tr_instruments:
		ins[name2] = tr_instruments[name2].duplicate()
	out["instruments"] = ins
	if numeric:
		# Why not PackedInt64Array in CANON.numeric_only: every persons-layer i64 array would enter the tiers-off digests
		for name3: String in ["count", "age_counts", "pt_off", "pt_mass", "mix_off", "mix_n", "pt_age", "hm_off", "hm_n", "cp_n", "pt_ms", "pt_id", "pt_jan", "pt_old", "kb", "pt_ag", "pt_jg", "pt_og", "pt_T"]:
			out[name3] = Array(out[name3])
		for name4: String in out["instruments"]:
			out["instruments"][name4] = Array(out["instruments"][name4])
		var hh := []
		var hk: Array = tr_hh.keys()
		hk.sort()
		for k: String in hk:
			var m: Dictionary = tr_hh[k]["members"]
			var mk: Array = m.keys()
			mk.sort()
			var row := [int(tr_hh[k]["count"])]
			for u in mk:
				for r in [0, 1, 2, 3, 4]:
					row.append(int(m[u].get(r, 0)))
			hh.append(row)
		out["households"] = hh
	else:
		out["households"] = tr_hh.duplicate(true)
		out["residual"] = tr_residual.duplicate()
		# Why not JSON-shaped rows for these (as "households" above): a save through JSON reads every number back as a float and every key
		# as a string, so the restore re-typed tr_hh's members and had no record of the couples (TO_E 07:17); the encoded variant keeps
		# each key's and value's type and its insertion order
		out["exact"] = Marshalls.variant_to_base64({"hh": tr_hh, "couples": tr_couples, "nh_couples": tr_nh_couples, "nh_hh": tr_nh_hh, "margins": tr_margins})
	return {"tiers": out}


## M025 C4's remaining months as [key, the 12 counts] rows in key order
static func _rem_rows(d: Dictionary) -> Array:
	var ks: Array = d.keys()
	ks.sort()
	var out: Array = []
	for k in ks:
		var row: Array = [int(k)]
		row.append_array(Array(d[k]))
		out.append(row)
	return out


## A pid-keyed dictionary as [pid, value] rows in pid order (the save's and the digest's one order)
static func _pid_rows(d: Dictionary) -> Array:
	var ks: Array = d.keys()
	ks.sort()
	var out: Array = []
	for k in ks:
		out.append([k, d[k]])
	return out


func from_dict(d: Dictionary) -> void:
	state = String(d["state"])
	load_spec(state)
	seed_v = int(d["seed"])
	base_year = int(d["base_year"])
	n = int(d["n"])
	month = int(d["month"])
	price_index = float(d["price_index"])
	wage_index = float(d.get("wage_index", 1.0))
	pension = (d["pension"] as Dictionary).duplicate(true)
	food_plan_start = float(d.get("food_plan_start", NAN))
	pref_pop = (d.get("pref_pop", {}) as Dictionary).duplicate()
	pref_codes = (d["pref_codes"] as Array).duplicate()
	for f: Array in fields():
		var group: Dictionary = d[String(f[1])]
		if group.has(String(f[0])):
			set(String(f[0]), _unpack(String(group[String(f[0])]), String(f[1])))
		elif f[4] == null:
			error = "people: the save has no %s" % String(f[0])
			push_error(error)
		else:
			var arr = get(String(f[0]))
			arr.resize(n * int(f[2]))
			arr.fill(f[4])
	events = (d["events"] as Array).duplicate(true)
	trace_pids = (d["trace_pids"] as Array).duplicate()
	trace = (d["trace"] as Array).duplicate(true)
	decisions = (d.get("decisions", []) as Array).duplicate(true)
	refusals = (d.get("refusals", []) as Array).duplicate(true)
	groups = (d.get("groups", []) as Array).duplicate(true)
	group_log = (d.get("group_log", []) as Array).duplicate(true)
	households = d.has("households")
	if households:
		var hd: Dictionary = d["households"]
		HH.load_spec(self)
		hh_n = int(hd["n"])
		for h: Array in household_fields():
			set(String(h[0]), _unpack(String(hd[String(h[1])]), String(h[2])))
		next_k = {}
		for kc in (hd["next_k"] as Dictionary):
			next_k[int(kc)] = int(hd["next_k"][kc])
		life_log = (hd["life_log"] as Array).duplicate(true)
		lc_births = (hd["lc_births"] as Array).duplicate(true)
		HH.refresh_members(self)
	tiers = d.has("tiers")
	if tiers:
		var td: Dictionary = d["tiers"]
		TR.load_spec(self)
		tr_units = int(td["n"])
		tr_k = int(td["k"])
		tr_key = td["key"]
		tr_count = td["count"]
		tr_age_counts = td["age_counts"]
		tr_never_married = td["never_married"]
		tr_pt_age = PackedInt64Array(td["pt_age"])
		tr_hh_keys = PackedStringArray(td["hh_keys"])
		tr_hm_off = PackedInt64Array(td["hm_off"])
		tr_hm_pt = td["hm_pt"]
		tr_hm_role = td["hm_role"]
		tr_hm_n = PackedInt64Array(td["hm_n"])
		tr_cp_hh = td["cp_hh"]
		tr_cp_w = td["cp_w"]
		tr_cp_h = td["cp_h"]
		tr_cp_n = PackedInt64Array(td["cp_n"])
		tr_pt_ms = PackedInt64Array(td["pt_ms"])
		tr_pt_id = PackedInt64Array(td["pt_id"])
		tr_pt_jan = PackedInt64Array(td["pt_jan"])
		tr_pt_old = PackedInt64Array(td["pt_old"])
		tr_pt_next = int(td["pt_next"])
		tr_kb = PackedInt64Array(td["kb"])
		tr_class_lines = PackedFloat64Array(td["class_lines"])
		tr_c = PackedFloat64Array(td["c"])
		tr_pt_q = PackedInt32Array(td["pt_q"])
		tr_pt_muq = PackedFloat64Array(td["pt_muq"])
		tr_pt_mug = PackedFloat64Array(td["pt_mug"])
		tr_cp_cap = {}
		for rc: Array in td["cp_cap"]:
			tr_cp_cap[int(rc[0])] = int(rc[1])
		tr_pt_ag = PackedInt64Array(td["pt_ag"])
		tr_pt_jg = PackedInt64Array(td["pt_jg"])
		tr_pt_og = PackedInt64Array(td["pt_og"])
		tr_pt_T = PackedInt64Array(td["pt_T"])
		tr_pt_rem = {}
		for rr: Array in td["pt_rem"]:
			tr_pt_rem[int(rr[0])] = PackedInt64Array(rr.slice(1))
		if not households:
			HH.load_spec(self)
		tr_married_apart = td["married_apart"]
		tr_tier_size = td["tier_size"]
		tr_indiv_unit = td["indiv_unit"]
		tr_pt_off = td["pt_off"]
		tr_pt_mass = td["pt_mass"]
		tr_mix_off = td["mix_off"]
		tr_mix_code = td["mix_code"]
		tr_mix_n = td["mix_n"]
		tr_pt_code = td["pt_code"]
		tr_indiv_code = td["indiv_code"]
		tr_instrument_factor = (td["instrument_factor"] as Dictionary).duplicate()
		tr_residual = td.get("residual", PackedFloat64Array())
		tr_phi = {}
		for r: Array in td["phi"]:
			tr_phi[int(r[0])] = float(r[1])
		tr_pension = {}
		for r2: Array in td["pension_own"]:
			tr_pension[int(r2[0])] = float(r2[1])
		tr_pension_kind = {}
		for r3: Array in td["pension_kind"]:
			tr_pension_kind[int(r3[0])] = int(r3[1])
		tr_points = {}
		for name: String in (td["points"] as Dictionary):
			tr_points[name] = td["points"][name]
		tr_instruments = {}
		for name2: String in (td["instruments"] as Dictionary):
			tr_instruments[name2] = td["instruments"][name2]
		tr_hh = {}
		for k: String in (td["households"] as Dictionary):
			var src: Dictionary = td["households"][k]
			var mem := {}
			for u in src["members"]:
				var rr := {}
				for r in src["members"][u]:
					rr[int(r)] = int(src["members"][u][r])
				mem[int(u)] = rr
			tr_hh[k] = {"count": int(src["count"]), "members": mem}
		if td.has("exact"):
			var ex: Dictionary = Marshalls.base64_to_variant(String(td["exact"]))
			tr_hh = ex["hh"]
			tr_couples = ex["couples"]
			tr_nh_couples = ex["nh_couples"]
			tr_nh_hh = ex["nh_hh"]
			tr_margins = ex["margins"]


## The state as numbers (for the digest: the packed arrays re-laid, strings dropped by numeric_only): every saved array and scalar (the
## code review, 2c: twenty saved arrays, the weights among them, were outside it). Why not the records (events, decisions, refusals,
## the logs, the trace): they are what the months wrote down, not what the next month reads
func digest_dict() -> Dictionary:
	var out := {"n": n, "month": month, "price_index": price_index, "wage_index": wage_index, "pension": pension.duplicate(true), "groups": groups.duplicate(true), "food_plan_start": food_plan_start, "pref_pop": pref_pop.duplicate()}
	for f: Array in fields():
		out[String(f[0])] = Array(get(String(f[0])))
	return out.merged(_households_dict(true)).merged(_tiers_dict(true))


func digest() -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(var_to_bytes(CANON.numeric_only(digest_dict())))
	return ctx.finish().hex_encode()
