# The people object the start writes into: every variable and constant of people.gd at cd165891, generated from its declarations
# (START_PORT_PLAN §1). A packed array is a PArr (PStr for strings), which keeps its Godot kind for the digest; Array, Dictionary
# and the scalars are their Python twins
import math

from core.digest import Packed, PackedStr


class PArr(list):
    # A Godot packed array: a list with its kind; resize fills with the kind's zero, as Godot does. Why not core.digest.Packed: the
    # ported code appends, resizes and indexes in place as GDScript does, so the kind travels with a list
    __slots__ = ("kind",)

    def __init__(self, kind, values=()):
        super().__init__(values)
        self.kind = kind

    def size(self):
        return len(self)

    def resize(self, n):
        if n < len(self):
            del self[n:]
        else:
            self.extend([0.0 if self.kind in ("f64", "f32") else 0] * (n - len(self)))

    def append_array(self, other):
        self.extend(other)

    def duplicate(self):
        return PArr(self.kind, self)


class PStr(PackedStr):
    def size(self):
        return len(self)

    def append_array(self, other):
        self.extend(other)

    def duplicate(self):
        return PStr(self)


class P:
    # people.gd's constants
    TRAITS = ["risk_tolerance", "patience", "sociability", "trust_in_others", "competitiveness", "cooperativeness", "authority_attitude", "openness", "fairness", "future_orientation"]
    EMOTIONS = ["joy", "sadness", "anger", "anxiety", "fear", "relief", "hope", "loneliness", "discontent", "trust"]
    DRIVES = ["survival_safety", "economic_security", "belonging", "recognition", "autonomy", "growth", "enjoyment", "family", "contribution", "change"]
    D_SURVIVAL = 0
    D_SECURITY = 1
    D_BELONGING = 2
    D_RECOGNITION = 3
    D_AUTONOMY = 4
    D_GROWTH = 5
    D_ENJOYMENT = 6
    D_FAMILY = 7
    D_CONTRIBUTION = 8
    D_CHANGE = 9
    DREAMS = ["start_business", "have_family", "become_expert", "financial_freedom", "contribute_locally", "become_known", "stable_life", "change_society"]
    EMPLOYMENT = ["not_in_labour_force", "regular", "non_regular", "unemployed", "student", "retired"]
    F_REST = 1
    F_SOCIALISED = 2
    F_SUPPORTED = 4
    F_MOVED = 8
    F_DREAM = 16
    F_JOINED = 32
    F_FOUNDED = 64
    EMP_NONE = 0
    EMP_REGULAR = 1
    EMP_NONREGULAR = 2
    EMP_UNEMPLOYED = 3
    EMP_STUDENT = 4
    EMP_RETIRED = 5
    PENSION_AGE = 65
    HOUSEHOLD = ["single", "couple", "couple_children", "single_parent", "other"]
    HK_SINGLE = 0
    HK_COUPLE = 1
    HK_COUPLE_CHILDREN = 2
    HK_SINGLE_PARENT = 3
    HK_OTHER = 4
    MALE = 0
    FEMALE = 1
    GRADE_GOOD = 0
    GRADE_FAIR = 1
    GRADE_POOR = 2
    GRADE_LIMITED = 3
    GRADE_CARE = 4
    R_HEAD = 0
    R_PARTNER = 1
    R_CHILD = 2
    R_PARENT = 3
    R_OTHER = 4
    EDUCATION = ["high_school_or_less", "vocational_junior_college", "university_or_more"]
    NT = 10
    NE = 10
    ND = 10
    K_MEM = 8
    AGES = 101
    SEXES = 2
    MOVE_KEEP = 0.5
    AGE_BANDS = [15, 30, 45, 65]

    def __init__(self):
        self.spec = {}
        self.state = "JPN"
        self.seed_v = 1
        self.base_year = 2024
        self.n = 0
        self.month = 0
        self.price_index = 1.0
        self.pension = {"new": 1.0, "old": 1.0, "carry": 0.0, "jan": [], "jan_prev": [], "log": []}
        self.wage_index = 1.0
        self.food_plan_start = math.nan
        self.food_elasticity = 0.0
        self.error = ""
        self.pid = PArr("i64")
        self.pref = PArr("i32")
        self.k_in_pref = PArr("i32")
        self.age = PArr("i32")
        self.sex = PArr("i32")
        self.weight = PArr("f64")
        self.hh_kind = PArr("i32")
        self.hh_size = PArr("f64")
        self.education = PArr("i32")
        self.employment = PArr("i32")
        self.health = PArr("i32")
        self.income = PArr("f64")
        self.pay_factor = PArr("f64")
        self.assets = PArr("f64")
        self.debt = PArr("f64")
        self.skill = PArr("f64")
        self.rank = PArr("f64")
        self.traits = PArr("f64")
        self.lam = PArr("f64")
        self.dw = PArr("f64")
        self.emo = PArr("f64")
        self.emo_base = PArr("f64")
        self.dd = PArr("f64")
        self.basket = PArr("f64")
        self.pref_leisure = PArr("f64")
        self.pref_social = PArr("f64")
        self.pol_interest = PArr("f64")
        self.dream_kind = PArr("i32")
        self.dream_importance = PArr("f64")
        self.dream_progress = PArr("f64")
        self.dream_status = PArr("i32")
        self.dream_blocked = PArr("i32")
        self.q_income = PArr("f64")
        self.q_price = PArr("f64")
        self.q_job = PArr("f64")
        self.mem_month = PArr("i32")
        self.mem_kind = PArr("i32")
        self.mem_val = PArr("f64")
        self.mem_head = PArr("i32")
        self.member_of = PArr("i32")
        self.union_cover = PArr("i32")
        self.groups = []
        self.group_influence = True
        self.contact_news = True
        self.contact_renewal = True
        self.group_log = []
        self.contact_idx = PArr("i32")
        self.contact_kind = PArr("i32")
        self.contact_trust = PArr("f64")
        self.contact_last = PArr("i32")
        self.met = PArr("i32")
        self.belief = PArr("f64")
        self.belief_known = PArr("i32")
        self.belief_source = PArr("i32")
        self.belief_month = PArr("i32")
        self.plan = PArr("i32")
        self.search = PArr("i32")
        self.flags = PArr("i32")
        self.q_act = PArr("f64")
        self.last_action = PArr("i32")
        self.pressure_prev = PArr("f64")
        self.decisions = []
        self.refusals = []
        self.events = []
        self.trace_pids = []
        self.trace = []
        self.cohort = PArr("f64")
        self.qx = PArr("f64")
        self.pref_codes = []
        self.pref_pop = {}
        self.tiers = False
        self.tier_k = 0
        self.tr_spec = {}
        self.tr_k = 4
        self.tr_units = 0
        self.tr_key = PArr("i32")
        self.tr_count = PArr("i64")
        self.tr_age_counts = PArr("i64")
        self.tr_never_married = PArr("f64")
        self.tr_married_apart = PArr("f64")
        self.tr_tier_size = PArr("i32")
        self.tr_residual = PArr("f64")
        self.tr_margins = {}
        self.tr_mix_off = PArr("i64")
        self.tr_mix_code = PArr("i32")
        self.tr_mix_n = PArr("i64")
        self.tr_pt_code = PArr("i32")
        self.tr_indiv_code = PArr("i32")
        self.tr_pt_off = PArr("i64")
        self.tr_pt_mass = PArr("i64")
        self.tr_pt_age = PArr("i64")
        self.tr_hh_keys = PStr()
        self.tr_hm_off = PArr("i64")
        self.tr_hm_pt = PArr("i32")
        self.tr_hm_role = PArr("i32")
        self.tr_hm_n = PArr("i64")
        self.tr_cp_hh = PArr("i32")
        self.tr_cp_w = PArr("i32")
        self.tr_cp_h = PArr("i32")
        self.tr_cp_n = PArr("i64")
        self.tr_pt_ms = PArr("i64")
        self.tr_nh_hh = {}
        self.tr_nh_couples = {}
        self.tr_couples = {}
        self.tr_points = {}
        self.tr_hh = {}
        self.tr_instruments = {}
        self.tr_instrument_factor = {}
        self.tr_indiv_unit = PArr("i32")
        self.tr_pt_id = PArr("i64")
        self.tr_pt_jan = PArr("i64")
        self.tr_pt_old = PArr("i64")
        self.tr_pt_next = 0
        self.tr_kb = PArr("i64")
        self.tr_class_lines = PArr("f64")
        self.tr_c = PArr("f64")
        self.tr_pt_q = PArr("i32")
        self.tr_pt_muq = PArr("f64")
        self.tr_pt_mug = PArr("f64")
        self.tr_cp_cap = {}
        self.tr_pt_rem = {}
        self.tr_pt_ag = PArr("i64")
        self.tr_pt_jg = PArr("i64")
        self.tr_pt_og = PArr("i64")
        self.tr_pt_T = PArr("i64")
        self.tr_phi = {}
        self.tr_pension = {}
        self.tr_pension_kind = {}
        self.households = False
        self.hh_spec = {}
        self.hh_n = 0
        self.hh_id = PArr("i32")
        self.hh_type = PArr("i32")
        self.hh_pref = PArr("i32")
        self.hh_weight = PArr("f64")
        self.hh_members = []
        self.hh_role = PArr("i32")
        self.partner = PArr("i32")
        self.ever_married = PArr("i32")
        self.ever_left = PArr("i32")
        self.union_month = PArr("i32")
        self.last_birth = PArr("i32")
        self.births_n = PArr("i32")
        self.next_k = {}
        self.life_log = []
        self.lc_dying = PArr("i32")
        self.lc_t22b = {}
        self.health_class = PArr("i32")
        self.lc_c = PArr("f64")
        self.lc_qcut = PArr("f64")
        self.rone_on = False
        self.rone_log = []
        self.lc_c_band = 0
        self.lc_expected = PArr("f64", [0, 0, 0, 0, 0, 0, 0, 0])
        self.lc_deaths = PArr("i32", [0, 0, 0, 0, 0, 0, 0, 0])
        self.lc_births = []
        self.lc_nm_short = PArr("f64")
        self.intends_marry = PArr("i32")
        self.intended_kids = PArr("i32")


def to_tree(v):
    # A value as core/digest hashes it: PArr to Packed, recursively through arrays and dictionaries (insertion order kept)
    if isinstance(v, PArr):
        return Packed(v.kind, list(v))
    if isinstance(v, PackedStr):
        return PackedStr(v)
    if isinstance(v, list):
        return [to_tree(x) for x in v]
    if isinstance(v, dict):
        return {k: to_tree(x) for k, x in v.items()}
    return v


def from_tree(v):
    # The inverse, for a state read back from start_trace.gd's typed tree
    if isinstance(v, Packed):
        # Why tolist and not list: list() of a NumPy array holds NumPy scalars, whose int64 overflows in the keyed draws' products
        return PArr(v.kind, v.a.tolist() if hasattr(v.a, "tolist") else list(v.a))
    if isinstance(v, PackedStr):
        return PStr(v)
    if isinstance(v, list):
        return [from_tree(x) for x in v]
    if isinstance(v, dict):
        return {k: from_tree(x) for k, x in v.items()}
    return v
