# Row Q-nan's helper part (PERSONS_PORT_PLAN §7, M042 §2b): core.gd's fdiv and fsqrt and core.detmath's NaN give the bits Godot gives
# on x86-64 (read from Godot 4.7.2 on this box: 0.0 / 0.0, INF - INF, sqrt(-1.0) and NAN are all 0xFFF8000000000000; 1.0 / -0.0
# is -inf)
import struct

from common import Kit
from core import detmath
from core.gd import default_nan, fdiv, fsqrt


def bits(v):
    return struct.unpack("<Q", struct.pack("<d", v))[0]


def main():
    k = Kit("py/tests/test_qnan.py")
    nan_bits = 0xFFF8000000000000
    k.check(bits(default_nan()) == nan_bits, "Q-nan default NaN is 0xFFF8000000000000, as Godot's NAN")
    k.check(bits(fdiv(0.0, 0.0)) == nan_bits, "Q-nan fdiv(0.0, 0.0) gives Godot's 0.0 / 0.0 bits")
    k.check(fdiv(1.0, 0.0) == float("inf") and fdiv(1.0, -0.0) == float("-inf") and fdiv(-1.0, 0.0) == float("-inf"),
            "Q-nan fdiv by a signed zero gives the signed infinity")
    k.check(bits(fsqrt(-1.0)) == nan_bits and str(fsqrt(-0.0)) == "-0.0", "Q-nan fsqrt(-1.0) is Godot's NaN; fsqrt(-0.0) is -0.0")
    k.check(bits(detmath.log(-1.0)) == nan_bits and detmath.log(0.0) == float("-inf"),
            "Q-nan detmath.log(-1.0) is Godot's NAN, log(0.0) is -inf (det_math.gd 108)")
    k.check(bits(detmath.sin(float("inf"))) == nan_bits and bits(detmath.cos(float("inf"))) == nan_bits,
            "Q-nan detmath.sin and cos of inf are Godot's NAN (det_math.gd 224, 231)")
    k.finish()


if __name__ == "__main__":
    main()
