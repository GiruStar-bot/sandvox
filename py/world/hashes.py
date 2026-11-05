# The hash calls that decide state (WORLD_PORT_PLAN §4, row W0-h): String.sha256_buffer().decode_u32(0) / 2^32 and the views'
# Crypto.hmac_digest(SHA256, salt, msg).hex_encode().left(10)
import hashlib
import hmac


def u32(s):
    return int.from_bytes(hashlib.sha256(s.encode("utf-8")).digest()[:4], "little")


def unit(s):
    return float(u32(s)) / 4294967296.0


def token(salt, view_key, entity_key):
    return "T" + hmac.new(bytes(salt), ("modern-view|%s|%s" % (view_key, entity_key)).encode("utf-8"), hashlib.sha256).hexdigest()[:10]
