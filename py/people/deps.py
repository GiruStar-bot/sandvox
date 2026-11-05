# The core primitives this port reads (CORE_GUIDE §6). Why not a copy here: a second keyed or DetMath could drift by a bit and split
# the digests for a reason no row names
from core import keyed, detmath, gd
from core import digest as _codec

canon = _codec.canon
enc = _codec.enc
Packed = _codec.Packed
PackedStr = _codec.PackedStr
load = _codec.load
read_hashes = _codec.read_hashes
_sort_key = _codec._sort_key
