# The project's test convention for the Python side: ok / FAIL lines and one RESULT JSON (tools/test/test_kit.gd)
import hashlib
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


class Kit:
    def __init__(self, name):
        self.name = name
        self.passed = 0
        self.failed = 0
        self.failures = []
        self.t0 = time.perf_counter()

    def check(self, ok, label):
        if ok:
            self.passed += 1
            print("ok   " + label, flush=True)
        else:
            self.failed += 1
            self.failures.append(label)
            print("FAIL " + label, flush=True)

    def finish(self):
        el = (time.perf_counter() - self.t0) * 1000.0
        print("RESULT " + json.dumps({"file": self.name, "passed": self.passed, "failed": self.failed, "checks": self.passed + self.failed,
                                      "failures": self.failures[:50], "elapsed_ms": round(el, 1)}), flush=True)
        sys.exit(1 if self.failed else 0)


def peak_mb():
    # The process's peak resident memory (PY_TRIAL_PLAN §5): ru_maxrss on Linux, the peak working set on Windows
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return pmc.PeakWorkingSetSize / 2 ** 20
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def f_bits(xs):
    return list(struct.unpack("<%dq" % len(xs), struct.pack("<%dd" % len(xs), *xs)))


def i64_bytes(xs):
    return struct.pack("<%dq" % len(xs), *xs)


def sha_i64(xs):
    return hashlib.sha256(i64_bytes(xs)).hexdigest()
