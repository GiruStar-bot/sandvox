# Hygiene track G: parameter provenance, the FY2024 budget-line
# identity, and the feedback-params loader contract.
#   python py/tests/test_feedback_params.py
# - Every numeric feedback parameter now carries a provenance entry
#   (S = published anchor, T = calibrated tuning constant, internal =
#   model definition) in the file's _provenance section.
# - The FY2024 budget lines in jpn_laws.json previously summed to
#   108,571.7 bn against a 112,571.7 bn total; the 4,000.0 bn of
#   unitemized official categories is now an explicit line, the lines
#   sum exactly, and the CLI's core-operations bucket includes it
#   (25y baseline Debt/GDP 328.3 -> 334.0: the state really spends
#   this money; the model was dropping it).
# - The loader contract is pinned: file values merge over the code
#   defaults by section, unknown sections are ignored, overrides win
#   over the file, and defaults are never mutated.
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Kit, ROOT  # noqa: E402  (puts py/ on the path)

import agent_env  # noqa: E402,F401  (puts the repo root on the path)
import run_simulation as RS  # noqa: E402

SECTIONS = ("fertility", "migration", "fiscal_and_jgb", "persons_replenishment")


def main():
    k = Kit("py/tests/test_feedback_params.py")

    fp_path = os.path.join(ROOT, "data", "modern", "jpn", "feedback_params.json")
    fp = json.load(open(fp_path, encoding="utf-8"))
    prov = fp.get("_provenance", {})
    missing = []
    for sec in SECTIONS:
        for name, val in fp[sec].items():
            if isinstance(val, (int, float)):
                e = prov.get(sec, {}).get(name)
                if not e or e.get("label") not in ("S", "T", "internal") or not e.get("basis"):
                    missing.append("%s.%s" % (sec, name))
    k.check(not missing, "G every feedback parameter carries provenance (missing: %s)" % (missing or "none"))

    laws = json.load(open(os.path.join(ROOT, "data", "modern", "polity", "jpn_laws.json"), encoding="utf-8"))
    lines = laws["laws"]["budget_fy2024"]["lines_bn_jpy"]
    named = sum(v for kk, v in lines.items() if kk != "total")
    k.check(abs(named - lines["total"]) < 0.05 and lines.get("unitemized") == 4000.0,
            "G FY2024 budget lines sum exactly to the total (%.1f == %.1f, unitemized %.1f)"
            % (named, lines["total"], lines.get("unitemized", -1)))

    base = RS.load_feedback_params()
    k.check(all(sec in base for sec in SECTIONS)
            and base["persons_replenishment"]["min_sample_ratio"] == 0.6
            and base["persons_replenishment"]["min_sample_abs"] == 20.0,
            "G defaults+file load with the replenishment parameters the P6 trigger reads")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        json.dump({"fertility": {"tfr_floor": 0.70}, "nonsense_section": {"x": 1.0}}, tf)
        tmp = tf.name
    try:
        custom = RS.load_feedback_params(params_path=tmp)
    finally:
        os.unlink(tmp)
    k.check(custom["fertility"]["tfr_floor"] == 0.70 and "nonsense_section" not in custom
            and RS.load_feedback_params()["fertility"]["tfr_floor"] == base["fertility"]["tfr_floor"],
            "G a params file overrides by section, unknown sections are ignored, defaults are not mutated")

    over = RS.load_feedback_params(overrides={"fiscal_and_jgb": {"jgb_max": 0.09}})
    k.check(over["fiscal_and_jgb"]["jgb_max"] == 0.09
            and RS.load_feedback_params()["fiscal_and_jgb"]["jgb_max"] == base["fiscal_and_jgb"]["jgb_max"],
            "G explicit overrides win over the file and leave the defaults intact")

    k.finish()


if __name__ == "__main__":
    main()
