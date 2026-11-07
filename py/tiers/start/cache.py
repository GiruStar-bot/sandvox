# Opt-in cache for tiers start builds, keyed by everything the build reads.
#
# Why (v4.1 audit, suite-speed fix): the start build is deterministic but
# slow (full 2025 build ~480 s; the 06_class prefix ~68 s), and several
# tools/tests rebuild the identical state from the identical inputs on
# every run. Like ccache, this is sound only because the key covers ALL
# inputs: every data file create.inputs* reads and every source file that
# can influence the build. Any change to data or code changes the key and
# forces a rebuild; there is no other invalidation path to get wrong.
#
# Safety rules:
#   - Opt-in only. A caller that exists to verify the build itself
#     (test_start_2025) must NOT use this: loading a cached state would
#     make its digest check circular.
#   - Callers must still verify the returned state with their own checks
#     (test_country compares stage hashes against the shipped oracle
#     dumps, which is a stronger check than the build itself).
#   - A corrupt or unreadable cache entry is treated as a miss, never an
#     error: the build is always the fallback.
import hashlib
import os
import pickle

_HERE = os.path.dirname(os.path.abspath(__file__))  # py/tiers/start
_PY = os.path.dirname(os.path.dirname(_HERE))  # py
_ROOT = os.path.dirname(_PY)  # repository root
_CACHE_DIR = os.path.join(_ROOT, "outputs", "cache", "start_build")


def _hash_file(h, path):
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)


def build_key(inputs_kind, upto_stage, variant=""):
    """SHA-256 over the build's code and data inputs.

    inputs_kind: "inputs" (people.create's inputs, 2024 spec) or
    "inputs_2025" (the 2025-01-01 start). upto_stage: a build.NAMES entry
    such as "06_class" or "18_t21" (the full build).
    """
    h = hashlib.sha256()
    h.update(inputs_kind.encode("utf-8"))
    h.update(b"\0")
    h.update(upto_stage.encode("utf-8"))
    h.update(b"\0")
    h.update(variant.encode("utf-8"))
    # Code: the whole tiers/start package plus the core/country modules the
    # stages import. Over-inclusive on purpose: a false rebuild is cheap
    # insurance against a stale state.
    code_dirs = [
        _HERE,
        os.path.join(_PY, "core"),
        os.path.join(_PY, "country"),
    ]
    for d in code_dirs:
        for name in sorted(os.listdir(d)):
            if name.endswith(".py"):
                _hash_file(h, os.path.join(d, name))
    # Data: the country tree create.py reads country manifests from.
    data_root = os.path.join(_ROOT, "data", "modern")
    for dirpath, dirnames, filenames in os.walk(data_root):
        dirnames.sort()
        for name in sorted(filenames):
            _hash_file(h, os.path.join(dirpath, name))
    return h.hexdigest()


def get_or_build(inputs_kind, upto_stage, builder, variant=""):
    """Return (p, ctx) for the requested partial/full start build.

    builder() must perform the real build and return (p, ctx); it is
    called on a cache miss and its result is stored. On a hit the stored
    state is returned without running any stage code.
    """
    key = build_key(inputs_kind, upto_stage, variant)
    path = os.path.join(_CACHE_DIR, "%s_%s_%s_%s.pkl" % (inputs_kind, upto_stage, variant or "default", key[:16]))
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                stored_key, p, ctx = pickle.load(f)
            if stored_key == key:
                return p, ctx
        except Exception:
            pass  # unreadable entry: fall through to a rebuild
    p, ctx = builder()
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump((key, p, ctx), f, protocol=4)
        os.replace(tmp, path)
    except Exception:
        pass  # caching is an optimisation; failing to store is not an error
    return p, ctx
