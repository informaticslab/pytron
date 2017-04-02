import hashlib
from construct import *
from binascii import hexlify

d = Struct(
    "fields" / RawCopy(Struct(
        "a" / Byte,
        "b" / Byte,
    )),
    "checksum" / Checksum(Bytes(1), lambda data: sum(bytearray(data)) % 256, this.fields.data),
)
msg = d.build(dict(fields=dict(value=dict(a=0x11,b=0x22))))

print("data = {}".format(hexlify(msg)))
